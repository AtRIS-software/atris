#!/usr/bin/env python3
"""AtRIS end-to-end test runner.

This script can:
1. convert a downloaded NASA NRLMSIS profile into ``simulation.psf``
2. convert ``simulation.psf`` into ``simulation.gdml``
3. generate proton/alpha macro files
4. run AtRIS
"""

import argparse
import datetime as dt
import math
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Queue

from nrlmsis_to_psf import convert_nrlmsis

REQUIRED_GEANT4_ENV_VARS = (
    "G4ENSDFSTATEDATA",
    "G4LEVELGAMMADATA",
    "G4RADIOACTIVEDATA",
    "G4SAIDXSDATA",
    "G4PARTICLEXSDATA",
    "G4ABLADATA",
    "G4INCLDATA",
    "G4LEDATA",
    "G4NEUTRONHPDATA",
)
REQUIRED_GEANT4_DATA_FILES = {
    "G4ENSDFSTATEDATA": "ENSDFSTATE.dat",
}
ATRIS_PHANTOM_LOAD_RE = re.compile(r"^### AtRIS: loading (radiation|counting) response matrix for phantom (\d+) ")
ATRIS_EVENT_PROGRESS_RE = re.compile(
    r"^Processing event: (?P<event>\d+), (?P<elapsed>\d+) secoonds have passed\. "
    r"We are processing (?P<speed>[-+0-9.eE]+) primaries per second\.$"
)
GEANT4_EVENT_START_RE = re.compile(r"Event\s+(?P<event>\d+)\s+starts\b")
ATRIS_DIRECT_PROGRESS_RE = re.compile(r"^AtRIS progress: ")
GDML_VALIDATION_PREFIX = "G4GDML: VALIDATION ERROR!"
ATRIS_HEARTBEAT_SECONDS = 60.0
ATRIS_STATUS_SECONDS = 10.0
ATRIS_PROGRESS_PERCENT_STEP = 2.0
RUN_PROFILES = {
    "quick": {
        "particles": "protons",
        "numberparts": 10,
        "phantom_count": 1,
    },
    "full": {
        "particles": "both",
        "numberparts": 1000,
        "phantom_count": 32,
    },
}


def log(message):
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def warn(message):
    log(f"WARNING: {message}")


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare and run AtRIS without conda or notebook code.")
    parser.add_argument("--rootdir", help="AtRIS checkout. Overrides ATRIS_ROOT.")
    parser.add_argument(
        "--geant4-sh",
        help="Geant4 setup script. Overrides GEANT4_SH and GEANT4_INSTALL/bin/geant4.sh.",
    )
    parser.add_argument(
        "--atris-executable",
        help="AtRIS executable. Overrides ATRIS_EXECUTABLE.",
    )
    parser.add_argument(
        "--run-profile",
        choices=tuple(RUN_PROFILES),
        default="quick",
        help="Runtime preset. 'quick' is a very small run meant to finish fast; 'full' restores the old heavier defaults.",
    )
    parser.add_argument(
        "nrlmsis_output",
        type=Path,
        help="Downloaded NASA NRLMSIS text file.",
    )
    parser.add_argument(
        "--particles",
        choices=("protons", "alphas", "both"),
        default=None,
        help="Which simulations to run. Overrides the selected run profile.",
    )
    parser.add_argument(
        "--numberparts",
        type=int,
        default=None,
        help="Particles per energy bin. Overrides the selected run profile.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=int(os.environ.get("SLURM_CPUS_PER_TASK", os.cpu_count() or 1)),
        help="Number of worker threads.",
    )
    parser.add_argument("--alpha-factor", type=float, default=0.66)
    parser.add_argument("--phys-list", default="FTFP_BERT_HP")
    parser.add_argument(
        "--phantom-count",
        type=int,
        default=None,
        help="Number of phantom response files to load. Overrides the selected run profile.",
    )
    parser.add_argument(
        "--atris-console",
        choices=("summary", "full", "quiet"),
        default="summary",
        help="How much AtRIS output to mirror to the terminal. Full raw output is always written to simname.log.",
    )
    parser.add_argument("--skip-prepare", action="store_true", help="Reuse existing simulation.psf and simulation.gdml.")
    return parser.parse_args()


def apply_run_profile(args):
    profile = RUN_PROFILES[args.run_profile]
    if args.particles is None:
        args.particles = str(profile["particles"])
    if args.numberparts is None:
        args.numberparts = int(profile["numberparts"])
    if args.phantom_count is None:
        args.phantom_count = int(profile["phantom_count"])
    return args


def require_file(path, label):
    if not path.is_file():
        raise SystemExit(f"Missing {label}: {path}")


def require_executable(path, label):
    if not (path.is_file() and os.access(path, os.X_OK)):
        raise SystemExit(f"Missing {label}: {path}")


def configured_value(cli_value, env_name):
    if cli_value:
        return cli_value
    return os.environ.get(env_name)


def configured_geant4_sh(cli_value):
    if cli_value:
        return cli_value
    env_script = os.environ.get("GEANT4_SH")
    if env_script:
        return env_script
    env_install = os.environ.get("GEANT4_INSTALL")
    if env_install:
        return str(Path(env_install).expanduser() / "bin" / "geant4.sh")
    return None


def configured_path(cli_value, env_name):
    value = configured_value(cli_value, env_name)
    if value is None:
        return None
    return Path(value).expanduser().resolve()


def preflight(args, simdir):
    rootdir = configured_path(args.rootdir, "ATRIS_ROOT")
    atris_executable = configured_path(args.atris_executable, "ATRIS_EXECUTABLE")
    geant4_value = configured_geant4_sh(args.geant4_sh)
    geant4_sh = Path(geant4_value).expanduser().resolve() if geant4_value else None

    log("Checking configuration")
    if rootdir is None:
        warn("AtRIS checkout is not configured; pass --rootdir or set ATRIS_ROOT.")
    elif not rootdir.is_dir():
        warn(f"AtRIS checkout directory does not exist: {rootdir}")
    else:
        materials_path = rootdir / "atris" / "interface" / "atris.materials"
        phantom_dir = rootdir / "phantoms"
        if not args.skip_prepare and not materials_path.is_file():
            warn(f"AtRIS materials file does not exist: {materials_path}")
        if not phantom_dir.is_dir():
            warn(f"AtRIS phantom directory does not exist: {phantom_dir}")
        else:
            for index in range(args.phantom_count):
                for kind in ("radiation", "counting"):
                    path = phantom_dir / f"{kind}_phantom{index}.txt"
                    if not path.is_file():
                        warn(f"Phantom response file does not exist: {path}")

    if atris_executable is None:
        warn("AtRIS executable is not configured; pass --atris-executable or set ATRIS_EXECUTABLE.")
    elif not (atris_executable.is_file() and os.access(atris_executable, os.X_OK)):
        warn(f"AtRIS executable is missing or not executable: {atris_executable}")

    if geant4_sh is None:
        warn("Geant4 setup script is not configured; pass --geant4-sh, set GEANT4_SH, or set GEANT4_INSTALL.")
    elif not geant4_sh.is_file():
        warn(f"Geant4 setup script does not exist: {geant4_sh}")

    if args.skip_prepare:
        for filename in ("simulation.psf", "simulation.gdml"):
            path = simdir / filename
            if not path.is_file():
                warn(f"--skip-prepare requires {path}")

    log("Configuration check complete")
    return rootdir, atris_executable, geant4_sh


def load_environment_from_geant4_sh(script_path):
    command = f"source {shlex.quote(str(script_path))} >/dev/null 2>&1 && env -0"
    result = subprocess.run(
        ["bash", "-c", command],
        check=True,
        capture_output=True,
    )
    env = {}
    for entry in result.stdout.decode("utf-8", errors="replace").split("\0"):
        if not entry or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        env[key] = value
    return env


def build_runtime_environment(geant4_sh):
    runtime_env = dict(os.environ)
    script_path = Path(geant4_sh).expanduser().resolve()
    require_file(script_path, "Geant4 setup script")
    log(f"Loading Geant4 environment from {script_path}")
    runtime_env.update(load_environment_from_geant4_sh(script_path))

    data_root_raw = runtime_env.get("GEANT4_DATA_DIR")
    if data_root_raw:
        data_root = Path(data_root_raw).expanduser()
        if not data_root.is_dir():
            raise SystemExit(f"Invalid Geant4 runtime data path: GEANT4_DATA_DIR={data_root_raw}")
        return runtime_env

    missing = [name for name in REQUIRED_GEANT4_ENV_VARS if not runtime_env.get(name)]
    if missing:
        raise SystemExit(
            "Missing Geant4 runtime data environment variables: "
            + ", ".join(missing)
            + ". The selected geant4.sh must set GEANT4_DATA_DIR or the legacy G4*DATA variables."
        )
    invalid_paths = []
    for name in REQUIRED_GEANT4_ENV_VARS:
        raw_path = runtime_env[name]
        data_path = Path(raw_path).expanduser()
        if not data_path.is_dir():
            invalid_paths.append(f"{name}={raw_path} (directory not found)")
            continue
        required_file = REQUIRED_GEANT4_DATA_FILES.get(name)
        if required_file and not (data_path / required_file).is_file():
            invalid_paths.append(f"{name}={raw_path} ({required_file} not found)")
    if invalid_paths:
        raise SystemExit(
            "Invalid Geant4 runtime data paths: "
            + "; ".join(invalid_paths)
            + "."
        )
    return runtime_env


def parse_formula(formula):
    result = {}
    total = 0.0
    for element, number in re.findall(r"([A-Z][a-z]*)(\d*)", formula):
        mass_fraction = float(number or "0") / 1000.0
        result[element] = {"mass fraction": mass_fraction, "material": element}
        total += mass_fraction
    if total <= 0.0:
        raise SystemExit(f"Could not parse core formula: {formula}")
    if abs(total - 1.0) > 1e-4:
        factor = 1.0 / total
        for element in result:
            result[element]["mass fraction"] = float(result[element]["mass fraction"]) * factor
    return result


def parse_psf_header(psf_path):
    header = psf_path.read_text(encoding="utf-8").splitlines()[0].split()
    core = parse_formula(header[0].lstrip("#"))
    template = {}
    for index, material in enumerate(header[1:]):
        template[material] = {"mass fraction": 0.0, "material": material, "colidx": index}
    return core, template


def gdml_material(mat, name, temperature, density, pressure, state):
    output = [f'\t<material name="{name}" state="{state}">']
    output.append(f'\t\t<D value="{density:e}" unit="g/cm3" />')
    output.append(f'\t\t<T value="{temperature:e}" unit="K" />')
    output.append(f'\t\t<P value="{pressure:e}" unit="Pa" />')
    for entry in mat.values():
        fraction = float(entry["mass fraction"])
        material = str(entry["material"])
        if fraction != 0.0:
            output.append(f'\t\t<fraction n="{fraction:e}" ref="G4_{material}" />')
    output.append("\t</material>")
    return "\n".join(output) + "\n"


def read_numeric_psf(psf_path):
    rows = []
    for line in psf_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rows.append([float(part) for part in stripped.split()])
    return rows


def psf_to_gdml(rootdir, psf_path, gdml_path):
    log(f"Converting {psf_path.name} to {gdml_path.name}")
    core, template = parse_psf_header(psf_path)
    rows = read_numeric_psf(psf_path)
    materials = []
    geometry = []
    structure = []

    for row in rows:
        sdid = int(row[6])
        material_name = f"material{sdid}"
        solid_name = f"solid{sdid}"
        is_core = row[10] == 1.0
        if is_core:
            materials.append(gdml_material(core, material_name, row[7], row[8], row[9], "solid"))
        else:
            atmosphere = {}
            for material, entry in template.items():
                atmosphere[material] = {
                    "material": material,
                    "mass fraction": row[int(entry["colidx"]) + 11],
                }
            materials.append(gdml_material(atmosphere, material_name, row[7], row[8], row[9], "gas"))

        delta_phi = row[3] - row[2]
        delta_theta = row[5] - row[4]
        delta_phi_text = "TWOPI" if abs(delta_phi - 2.0 * math.pi) < 0.01 else f"{delta_phi}"
        delta_theta_text = "PI" if abs(delta_theta - math.pi) < 0.01 else f"{delta_theta}"
        geometry.append(
            '\t<sphere name="{name}" rmin="{rmin:f}" rmax="{rmax:f}" startphi="{startphi:.4f}" deltaphi="{dphi}" '
            'starttheta="{starttheta:.4f}" deltatheta="{dtheta}" lunit="km" aunit="rad"/>\n'.format(
                name=solid_name,
                rmin=row[0],
                rmax=row[1],
                startphi=row[2],
                dphi=delta_phi_text,
                starttheta=row[4],
                dtheta=delta_theta_text,
            )
        )
        structure.append((f"volume{sdid}", material_name, solid_name, sdid))

    world = rows[-1][1] + 100.0
    materials_path = rootdir / "atris" / "interface" / "atris.materials"
    require_file(materials_path, "AtRIS materials file")
    attris_materials = materials_path.read_text(encoding="utf-8")

    pieces = [
        # Avoid remote schema validation on batch nodes; Geant4 can parse the GDML without it.
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n<gdml>\n\n',
        '<define>\n\t<constant name="PI" value="1.*pi"/>\n\t<constant name="TWOPI" value="2.*pi"/>'
        '\n\t<position name="center"/>\n\t<rotation name="identity"/>\n</define>\n',
        "<materials>\n",
        attris_materials,
    ]
    pieces.extend(materials)
    pieces.append("</materials>\n")
    pieces.append("<solids>\n")
    pieces.append(f'\t<box name="WorldBox" x="{world * 2:f}" y="{world * 2:f}" z="{world * 2:f}" lunit="km"/>\n')
    pieces.extend(geometry)
    pieces.append("</solids>\n")
    pieces.append("<structure>\n")
    for volume_name, material_name, solid_name, sdid in structure:
        pieces.append(
            '\t<volume name="{volume}">\n\t\t<materialref ref="{material}"/>\n\t\t<solidref ref="{solid}"/>'
            '\n\t\t<auxiliary auxtype="SensDet" auxvalue="{sdid}"/>\n\t</volume>\n'.format(
                volume=volume_name,
                material=material_name,
                solid=solid_name,
                sdid=sdid,
            )
        )
    pieces.append('\t<volume name="World">\n\t\t<materialref ref="Vacuum"/>\n\t\t<solidref ref="WorldBox"/>\n')
    for volume_name, _, _, _ in structure:
        pieces.append(
            '\t\t<physvol>\n\t\t\t<volumeref ref="{volume}"/>\n\t\t\t<positionref ref="center"/>'
            '\n\t\t</physvol>\n'.format(volume=volume_name)
        )
    pieces.append("\t</volume>\n</structure>\n")
    pieces.append('<setup name="Exoplanet" version="1.0">\n\t<world ref="World"/>\n</setup>\n</gdml>\n')
    gdml_path.write_text("".join(pieces), encoding="utf-8")
    log(f"Wrote {gdml_path}")


def numeric_rows(path):
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                rows.append([float(parts[0]), float(parts[1])])
            except ValueError:
                continue
    return rows


def radius_from_psf(psf_path):
    rows = numeric_rows(psf_path)
    if len(rows) < 2:
        raise SystemExit(f"Could not parse enough numeric rows from {psf_path}")
    return rows[-2][1] + 0.001


def logspace_powers(start, stop, count):
    if count < 2:
        return [10**start]
    step = (stop - start) / (count - 1)
    return [10 ** (start + step * index) for index in range(count)]


def write_bins(path, values):
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(f"{value:.9f}\n")


def write_macro(path, bins, radius_km, particle, threads, event_count):
    seed1 = random.randint(31, 999999)
    seed2 = random.randint(31, 999999)
    progress_modulo = max(1, event_count // 250)
    lines = [
        f"/run/numberOfThreads {threads}",
        "/control/cout/useBuffer false",
        "/run/initialize",
        "/run/verbose 2",
        f"/run/printProgress {progress_modulo}",
        f"/gps/particle {particle}",
        "/gps/ene/type User",
        "/gps/hist/type energy",
        f"/gps/hist/point {bins[0]:.9f} 0.000000000",
    ]
    for value in bins[1:]:
        lines.append(f"/gps/hist/point {value:.9f} 1.000000000")
    lines.extend(
        [
            "/gps/pos/type Surface",
            "/gps/pos/shape Sphere",
            "/gps/pos/centre 0 0 0 m",
            f"/gps/pos/radius {radius_km:.3f} km",
            "/gps/ang/type cos",
            "/gps/ang/mintheta 0 deg",
            "/gps/ang/maxtheta 90 deg",
            "/gps/number 1",
            "/run/setCut 100. m",
            "/run/particle/dumpCutValues",
            f"/random/setSeeds {seed1} {seed2}",
            f"/run/beamOn {event_count}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_phantoms(rootdir, simdir, phantom_count):
    phantom_dir = rootdir / "phantoms"
    if not phantom_dir.is_dir():
        raise SystemExit(f"Missing phantom directory: {phantom_dir}")
    log(f"Copying {phantom_count} phantom response pair(s) from {phantom_dir} to {simdir}")
    for index in range(phantom_count):
        for kind in ("radiation", "counting"):
            path = phantom_dir / f"{kind}_phantom{index}.txt"
            require_file(path, "phantom response file")
            shutil.copy2(path, simdir / path.name)
    log("Copied phantom files")


def generate_macros(simdir, numberparts, threads, alpha_factor, particles):
    selected = {
        "protons": ("protons",),
        "alphas": ("alphas",),
        "both": ("protons", "alphas"),
    }[particles]
    log(
        f"Generating input files for {', '.join(selected)} with "
        f"numberparts={numberparts}, threads={threads}"
    )
    radius_km = radius_from_psf(simdir / "simulation.psf")
    base_bins = logspace_powers(0.0, 6.0, 121)
    event_counts = {}

    for name in selected:
        if name == "protons":
            bins = base_bins
            particle = "proton"
            events = len(bins) * numberparts
        else:
            bins = [value * 4.0 for value in base_bins]
            particle = "alpha"
            events = len(bins) * int(numberparts * alpha_factor)
        shutil.copy2(simdir / "simulation.gdml", simdir / f"{name}.gdml")
        write_bins(simdir / f"{name}.bins", bins)
        write_macro(simdir / f"{name}.mac", bins, radius_km, particle, threads, events)
        event_counts[name] = events

    log(f"Generated input files for {', '.join(selected)}")
    return event_counts


def should_report_phantom_progress(phantom_index, phantom_count):
    if phantom_count <= 8:
        return True
    checkpoints = {0, phantom_count - 1}
    step = max(1, phantom_count // 4)
    checkpoints.update(range(step - 1, phantom_count, step))
    return phantom_index in checkpoints


def should_echo_atris_line(line):
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("-------- EEEE", "***", "Backtrace:", "[PID=", ": Aborted")):
        return True
    keywords = (
        "G4Exception",
        "Fatal Exception",
        "CAUGHT SIGNAL",
        "Traceback",
        "Error",
        "ERROR",
        "Warning",
        "WARNING",
        "Aborted",
        "SIGABRT",
    )
    if any(keyword in stripped for keyword in keywords):
        return True
    important_prefixes = (
        "### Incorrect use!",
        "### AtRIS: proceeding to load ",
        "### AtRIS: nrofdetectors has been determined",
        "### AtRIS: Generating detbins",
        "### AtRIS: read ",
        "### AtRIS: Starting the simulation",
        "### AtRIS: the simulation has completed",
        "### AtRIS: The logfile has been sucessfully closed",
        "### AtRIS: opening file:",
    )
    return stripped.startswith(important_prefixes)


def extract_atris_progress_event(line):
    stripped = line.strip()
    if ATRIS_DIRECT_PROGRESS_RE.match(stripped):
        match = re.search(r"event\s+(?P<event>\d+)\b", stripped)
        if match:
            return int(match.group("event"))
        return None
    match = ATRIS_EVENT_PROGRESS_RE.match(stripped)
    if match:
        return int(match.group("event"))
    geant_match = GEANT4_EVENT_START_RE.search(stripped)
    if geant_match:
        return int(geant_match.group("event"))
    return None


def should_emit_progress(
    progress_event,
    total_events,
    last_logged_event,
):
    if progress_event <= 0:
        return False
    if last_logged_event < 0:
        return True
    if total_events and total_events > 0:
        current_percent = (100.0 * progress_event) / total_events
        previous_percent = (100.0 * last_logged_event) / total_events
        if progress_event >= total_events:
            return True
        return current_percent - previous_percent >= ATRIS_PROGRESS_PERCENT_STEP
    return progress_event > last_logged_event


def format_atris_progress(line, total_events=None):
    stripped = line.strip()
    if ATRIS_DIRECT_PROGRESS_RE.match(stripped):
        event = extract_atris_progress_event(stripped)
        if event is None:
            return stripped
        if total_events:
            fraction = min(max(event / total_events, 0.0), 1.0)
            return f"AtRIS progress: event {event}/{total_events} ({fraction:.1%})"
        return f"AtRIS progress: event {event}"
    match = ATRIS_EVENT_PROGRESS_RE.match(stripped)
    if not match:
        geant_match = GEANT4_EVENT_START_RE.search(stripped)
        if not geant_match:
            return None
        event = int(geant_match.group("event"))
        if total_events:
            fraction = min(max(event / total_events, 0.0), 1.0)
            return f"AtRIS progress: event {event}/{total_events} ({fraction:.1%})"
        return f"AtRIS progress: event {event}"
    event = int(match.group("event"))
    if total_events:
        fraction = min(max(event / total_events, 0.0), 1.0)
        prefix = f"AtRIS progress: event {event}/{total_events} ({fraction:.1%})"
    else:
        prefix = f"AtRIS progress: event {event}"
    return f"{prefix}, elapsed {match.group('elapsed')}s, {match.group('speed')} primaries/s"


def enqueue_stream_lines(stream, queue):
    try:
        for line in stream:
            queue.put(line)
    finally:
        queue.put(None)


def run_atris(
    simdir,
    atris_executable,
    runtime_env,
    phys_list,
    simname,
    phantom_count,
    atris_console,
    total_events=None,
):
    command = [str(atris_executable), phys_list, simname, "-1", str(phantom_count)]
    log_path = simdir / f"{simname}.log"
    log(
        f"Starting AtRIS run for {simname}; full raw output will be written to {log_path.name} "
        f"(console mode: {atris_console})"
    )
    phantom_load_started = False
    gdml_validation_count = 0
    simulation_started = False
    simulation_start_time = None
    last_visible_output_time = time.monotonic()
    last_status_time = 0.0
    last_status_log_size = 0
    max_progress_event_seen = -1
    last_progress_time = None
    last_progress_logged_event = -1

    def emit_summary_log(message, timestamp=None):
        nonlocal last_visible_output_time
        log(message)
        last_visible_output_time = time.monotonic() if timestamp is None else timestamp

    with log_path.open("w", encoding="utf-8", buffering=1) as handle:
        process = subprocess.Popen(
            command,
            cwd=simdir,
            env=runtime_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        queue = Queue()
        reader = threading.Thread(target=enqueue_stream_lines, args=(process.stdout, queue), daemon=True)
        reader.start()
        while True:
            try:
                queued_line = queue.get(timeout=1.0)
            except Empty:
                now = time.monotonic()
                if (
                    atris_console == "summary"
                    and simulation_started
                    and process.poll() is None
                    and now - last_status_time >= ATRIS_STATUS_SECONDS
                ):
                    try:
                        log_size = log_path.stat().st_size
                    except OSError:
                        log_size = 0
                    elapsed = int(now - simulation_start_time) if simulation_start_time is not None else 0
                    if max_progress_event_seen > 0 and last_progress_time is not None and now - last_progress_time >= ATRIS_STATUS_SECONDS:
                        if total_events:
                            fraction = min(max(max_progress_event_seen / total_events, 0.0), 1.0)
                            progress_text = f"{max_progress_event_seen}/{total_events} ({fraction:.1%})"
                        else:
                            progress_text = str(max_progress_event_seen)
                        stalled_for = int(now - last_progress_time)
                        message = (
                            f"AtRIS status: {progress_text}; "
                            f"no new progress for {stalled_for:>3}s; "
                            f"{log_path.name} is {log_size} bytes"
                        )
                        emit_summary_log(message, now)
                        last_status_time = now
                        last_status_log_size = log_size
                    elif max_progress_event_seen <= 0:
                        message = (
                            f"AtRIS status: no event progress yet; "
                            f"{elapsed:>4}s elapsed; {log_path.name} is {log_size} bytes"
                        )
                        emit_summary_log(message, now)
                        last_status_time = now
                        last_status_log_size = log_size
                continue
            if queued_line is None:
                break
            line = queued_line
            now = time.monotonic()
            handle.write(line)
            handle.flush()
            if atris_console == "full":
                print(line, end="", flush=True)
                continue
            stripped = line.strip()
            match = ATRIS_PHANTOM_LOAD_RE.match(stripped)
            if match:
                phantom_index = int(match.group(2))
                if not phantom_load_started:
                    emit_summary_log("AtRIS is loading phantom response files", now)
                    phantom_load_started = True
                if match.group(1) == "radiation" and should_report_phantom_progress(phantom_index, phantom_count):
                    emit_summary_log(f"Phantom response load progress: {phantom_index + 1}/{phantom_count}", now)
                continue
            if stripped.startswith(GDML_VALIDATION_PREFIX):
                gdml_validation_count += 1
                if atris_console == "summary" and gdml_validation_count == 1:
                    emit_summary_log(
                        f"Geant4 is reporting GDML schema validation warnings; raw details are in {log_path.name}",
                        now,
                    )
                continue
            if atris_console == "summary" and stripped == "### AtRIS: Starting the simulation":
                simulation_started = True
                simulation_start_time = now
                last_status_time = now
                try:
                    last_status_log_size = log_path.stat().st_size
                except OSError:
                    last_status_log_size = 0
                if gdml_validation_count:
                    emit_summary_log(
                        f"Suppressed {gdml_validation_count} GDML validation warning lines from the terminal",
                        now,
                    )
                emit_summary_log(f"AtRIS entered the simulation phase; raw output is streaming to {log_path.name}", now)
            if atris_console == "summary":
                progress_event = extract_atris_progress_event(line)
                if progress_event is not None and progress_event <= max_progress_event_seen:
                    continue
                progress_message = format_atris_progress(line, total_events)
                if progress_message:
                    if progress_event is not None:
                        max_progress_event_seen = progress_event
                        last_progress_time = now
                        if not should_emit_progress(progress_event, total_events, last_progress_logged_event):
                            continue
                        last_progress_logged_event = progress_event
                    emit_summary_log(progress_message, now)
                    continue
            if atris_console == "summary" and should_echo_atris_line(line):
                print(line, end="", flush=True)
                last_visible_output_time = now
        reader.join(timeout=1.0)
        return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)
    log(f"Finished AtRIS run for {simname}")


def main():
    args = parse_args()
    simdir = Path.cwd().resolve()

    args = apply_run_profile(args)
    log(f"Simulation directory: {simdir}")
    log(
        "Run settings: "
        f"profile={args.run_profile}, particles={args.particles}, "
        f"numberparts={args.numberparts}, phantom_count={args.phantom_count}, threads={args.threads}"
    )
    rootdir, atris_executable, geant4_sh = preflight(args, simdir)
    if rootdir is not None:
        log(f"Root directory: {rootdir}")

    if args.skip_prepare:
        log("Skipping geometry preparation and reusing existing simulation.psf/simulation.gdml")
        require_file(simdir / "simulation.psf", "simulation.psf")
        require_file(simdir / "simulation.gdml", "simulation.gdml")
    else:
        psf_path = convert_nrlmsis(args.nrlmsis_output)
        if rootdir is None:
            raise SystemExit(
                "Cannot convert simulation.psf to simulation.gdml: "
                "pass --rootdir or set ATRIS_ROOT."
            )
        log("Starting geometry preparation")
        psf_to_gdml(rootdir, psf_path, simdir / "simulation.gdml")
        log("Geometry preparation complete")

    if rootdir is None:
        raise SystemExit("Cannot copy phantom files: pass --rootdir or set ATRIS_ROOT.")
    copy_phantoms(rootdir, simdir, args.phantom_count)
    event_counts = generate_macros(
        simdir,
        args.numberparts,
        args.threads,
        args.alpha_factor,
        args.particles,
    )

    if atris_executable is None:
        raise SystemExit(
            "Cannot start AtRIS: pass --atris-executable or set ATRIS_EXECUTABLE."
        )
    require_executable(atris_executable, "AtRIS executable")
    if geant4_sh is None:
        raise SystemExit(
            "Cannot start AtRIS: pass --geant4-sh, set GEANT4_SH, or set GEANT4_INSTALL."
        )
    runtime_env = build_runtime_environment(geant4_sh)
    log(f"AtRIS executable: {atris_executable}")

    run_order = {
        "protons": ("protons",),
        "alphas": ("alphas",),
        "both": ("protons", "alphas"),
    }[args.particles]
    log(f"Run order: {', '.join(run_order)}")
    for simname in run_order:
        run_atris(
            simdir,
            atris_executable,
            runtime_env,
            args.phys_list,
            simname,
            args.phantom_count,
            args.atris_console,
            event_counts.get(simname),
        )

    log("Finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())

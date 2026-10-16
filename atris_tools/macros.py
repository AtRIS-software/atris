"""Generate proton and alpha source macros and energy-bin files."""
import argparse
import logging
import os
from pathlib import Path
import random
import shutil

import numpy as np

from .cli import HelpFormatter, add_logging_arguments, add_version_argument, configure_logging
from .psf import OUTER_RADIUS, load_psf


def read_macro(filename):
    """Read command settings and ordered GPS histogram points."""
    settings = {}
    energy_points = []
    with Path(filename).open() as macro:
        for line in macro:
            fields = line.split("#", 1)[0].split()
            if not fields:
                continue
            command, *values = fields
            if command == "/gps/hist/point":
                energy_points.append((float(values[0]), float(values[1])))
            else:
                settings[command] = " ".join(values)
    return settings, np.asarray(energy_points).reshape(-1, 2)


GENERATED_INPUTS = (
    "protons.mac",
    "protons.bins",
    "protons.gdml",
    "alphas.mac",
    "alphas.bins",
    "alphas.gdml",
)
DEFAULT_PARTICLES_PER_BIN = 5000
DEFAULT_ALPHA_FACTOR = 0.66
logger = logging.getLogger(__name__)


def refuse_existing_inputs(output_dir):
    existing = [
        filename
        for filename in GENERATED_INPUTS
        if os.path.lexists(os.path.join(output_dir, filename))
    ]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing AtRIS inputs: " + ", ".join(existing)
        )


def generate_macros(
    particles_per_bin=DEFAULT_PARTICLES_PER_BIN,
    alpha_factor=DEFAULT_ALPHA_FACTOR,
    run_directory=".",
    random_seed=None,
    energy_min_power=0.0,
    energy_max_power=6.0,
    energy_points=121,
):
    """Write proton/alpha source inputs and return the paths actually written."""
    if energy_points < 2:
        raise ValueError("energy_points must be at least 2")
    directory = Path(run_directory).resolve()
    if not directory.is_dir():
        raise FileNotFoundError("Run directory does not exist: " + str(directory))
    refuse_existing_inputs(directory)
    rng = random.Random(random_seed) if random_seed is not None else random
    base_bins = 10**np.linspace(energy_min_power, energy_max_power, energy_points)
    # Start one metre outside the last physical shell, inside the stop volume.
    radius_km = load_psf(directory / "simulation.psf")[-2, OUTER_RADIUS] + 0.001
    for stem, particle, energy_factor, per_bin in (
        ("protons", "proton", 1, particles_per_bin),
        ("alphas", "alpha", 4, int(particles_per_bin * alpha_factor)),
    ):
        bins = base_bins * energy_factor
        seed1, seed2 = rng.randint(31, 999999), rng.randint(31, 999999)
        points = f"/gps/hist/point {bins[0]:.17e} {0.0:.17e}\n"
        points += "".join(f"/gps/hist/point {energy:.17e} {1.0:.17e}\n" for energy in bins[1:])
        macro = f"""/run/initialize
/run/verbose 2
/gps/particle {particle}
/gps/ene/type User
/gps/hist/type energy
{points}/gps/pos/type Surface
/gps/pos/shape Sphere
/gps/pos/centre 0 0 0 m
/gps/pos/radius {radius_km:.17e} km
/gps/ang/type cos
/gps/ang/mintheta 0 deg
/gps/ang/maxtheta 90 deg
/gps/number 1
/run/setCut 100. m
/run/particle/dumpCutValues
/random/setSeeds {seed1} {seed2}
/run/beamOn {int(len(bins) * per_bin)}
"""
        shutil.copy2(directory / "simulation.gdml", directory / f"{stem}.gdml")
        np.savetxt(directory / f"{stem}.bins", bins)
        (directory / f"{stem}.mac").write_text(macro)
    return tuple(directory / name for name in GENERATED_INPUTS)


def main():
    """Run the AtRIS macro-generation command."""
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Generate the proton and alpha macros, energy grids, and geometry "
            "copies needed to run AtRIS."
        ),
        epilog=(
            "RUN_DIRECTORY must already contain simulation.psf and "
            "simulation.gdml. This command does not run AtRIS or stage phantom "
            "responses. It writes protons/alphas .mac, .bins, and .gdml files "
            "and refuses to overwrite any of them. The proton event count is "
            "PARTICLES_PER_BIN multiplied by ENERGY_POINTS; the alpha count "
            "uses ALPHA_FACTOR per energy point. Alpha energies are four times "
            "the corresponding proton grid values."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        default=".",
        metavar="RUN_DIRECTORY",
        help="Prepared run directory (default: current directory).",
    )
    parser.add_argument(
        "--particles-per-bin",
        type=int,
        default=DEFAULT_PARTICLES_PER_BIN,
        metavar="COUNT",
        help="Number of proton histories per energy point (default: %(default)s).",
    )
    parser.add_argument(
        "--alpha-factor",
        type=float,
        default=DEFAULT_ALPHA_FACTOR,
        metavar="FACTOR",
        help=(
            "Alpha histories per energy point as a fraction of the proton "
            "count; the result is truncated to an integer (default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        metavar="SEED",
        help="Seed for reproducible Geant4 seed pairs (default: random).",
    )
    parser.add_argument(
        "--energy-min-power",
        type=float,
        default=0.0,
        metavar="POWER",
        help=(
            "Base-10 exponent of the minimum proton energy in MeV "
            "(default: 0, or 1 MeV)."
        ),
    )
    parser.add_argument(
        "--energy-max-power",
        type=float,
        default=6.0,
        metavar="POWER",
        help=(
            "Base-10 exponent of the maximum proton energy in MeV "
            "(default: 6, or 1 TeV)."
        ),
    )
    parser.add_argument(
        "--energy-points",
        type=int,
        default=121,
        metavar="COUNT",
        help=(
            "Number of logarithmically spaced energy points, including both "
            "endpoints (default: 121)."
        ),
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)
    logger.debug(
        "Generating inputs with %i particles per bin, %i energy points, "
        "and alpha factor %.3g",
        args.particles_per_bin,
        args.energy_points,
        args.alpha_factor,
    )
    generate_macros(
        args.particles_per_bin,
        args.alpha_factor,
        args.run_directory,
        args.random_seed,
        args.energy_min_power,
        args.energy_max_power,
        args.energy_points,
    )
    logger.info(
        "Generated proton and alpha input files in %s",
        os.path.abspath(args.run_directory),
    )


if __name__ == "__main__":
    main()

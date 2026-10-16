"""Read ROOT ntuples, interface/step records and bounded shower summaries."""

from collections import Counter, defaultdict
from pathlib import Path
import random

import numpy as np
import uproot


INTERFACE_COLUMNS = (
    "pdg",
    "interface",
    "angle",
    "kinetic_energy",
    "source_energy",
)
INTERFACE_DTYPE = np.dtype(
    [
        ("pdg", np.int32),
        ("interface", np.int32),
        ("angle", np.int32),
        ("kinetic_energy", np.float64),
        ("source_energy", np.float64),
    ]
)
INTERFACE_FIELDS = (
    "pdg",
    "interface_id",
    "angle_degrees",
    "kinetic_energy_MeV",
    "primary_energy_MeV",
)
STEP_FIELDS = (
    "event_id",
    "track_id",
    "parent_id",
    "step_id",
    "pdg",
    "detector_id",
    "pre_x_km",
    "pre_y_km",
    "pre_z_km",
    "post_x_km",
    "post_y_km",
    "post_z_km",
    "pre_kinetic_energy_MeV",
    "post_kinetic_energy_MeV",
    "energy_deposit_MeV",
    "nonionizing_energy_deposit_MeV",
    "step_length_m",
    "global_time_ns",
    "primary_energy_MeV",
    "creator_process",
    "step_process",
)
ENERGY_SAMPLE_LIMIT = 100_000


def read_interface_records(filename):
    """Read interface records from one AtRIS mode-0 or mode-1 ROOT file."""
    root_records = read_ntuple(filename, "interfaces", INTERFACE_FIELDS)
    records = np.empty(root_records.size, dtype=INTERFACE_DTYPE)
    for target, source in zip(INTERFACE_COLUMNS, INTERFACE_FIELDS):
        records[target] = root_records[source]
    return records


def read_interface_output(prefix):
    """Read the ROOT interface output belonging to a simulation prefix."""
    root_path = Path(str(prefix) + ".root")
    if not root_path.is_file():
        raise FileNotFoundError("No interface output found in %s" % root_path)
    return read_interface_records(root_path), root_path


def _tree(root_file, tree_name, field_names):
    if tree_name not in root_file:
        raise ValueError(
            "%s does not contain the %s ntuple"
            % (Path(root_file.file_path).name, tree_name)
        )
    tree = root_file[tree_name]
    missing = [name for name in field_names if name not in tree]
    if missing:
        raise ValueError(
            "%s ntuple is missing columns: %s"
            % (tree_name, ", ".join(missing))
        )
    return tree


def _structured_records(arrays, field_names):
    columns = [np.asarray(arrays[name]) for name in field_names]
    size = len(columns[0]) if columns else 0
    dtype = [
        (name, object if values.dtype.kind == "O" else values.dtype)
        for name, values in zip(field_names, columns)
    ]
    records = np.empty(size, dtype=dtype)
    for name, values in zip(field_names, columns):
        records[name] = values
    return records


def read_ntuple(filename, tree_name, field_names):
    """Read a complete Geant4 ROOT ntuple into a structured array."""
    path = Path(filename)
    with uproot.open(path) as root_file:
        tree = _tree(root_file, tree_name, field_names)
        arrays = tree.arrays(field_names, library="np")
    return _structured_records(arrays, field_names)


def ntuple_fields(filename, tree_name):
    """Return the branch names stored in a ROOT ntuple."""
    with uproot.open(filename) as root_file:
        return tuple(_tree(root_file, tree_name, ()).keys())


def iterate_ntuple(filename, tree_name, field_names, step_size="100 MB"):
    """Yield bounded chunks from a Geant4 ROOT ntuple."""
    path = Path(filename)
    with uproot.open(path) as root_file:
        tree = _tree(root_file, tree_name, field_names)
        for arrays in tree.iterate(
            field_names,
            step_size=step_size,
            library="np",
        ):
            yield _structured_records(arrays, field_names)


def has_ntuple(filename, tree_name):
    """Return whether a ROOT file contains the named ntuple."""
    with uproot.open(filename) as root_file:
        return tree_name in root_file


def iterate_step_records(filename):
    """Yield bounded record arrays from one AtRIS mode-1 ROOT file."""
    return iterate_ntuple(filename, "steps", STEP_FIELDS)


def process_name(value):
    """Return a process name read from a ROOT string column."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def read_step_trace(filename, sample_limit=ENERGY_SAMPLE_LIMIT):
    """Stream a mode-1 trace into aggregate counts and a bounded sample."""
    path = Path(filename)
    random_generator = random.Random(0)
    particle_counts = Counter()
    process_counts = Counter()
    event_counts = Counter()
    detector_counts = Counter()
    detector_deposit = defaultdict(float)
    energy_sample = []
    positive_energy_rows = 0
    row_count = 0
    first_event = None
    last_event = None

    for records in iterate_step_records(path):
        for row in records:
            event_id = int(row["event_id"])
            pdg = int(row["pdg"])
            detector_id = int(row["detector_id"])
            kinetic_energy = float(row["post_kinetic_energy_MeV"])
            energy_deposit = float(row["energy_deposit_MeV"])
            if not np.isfinite(kinetic_energy) or not np.isfinite(energy_deposit):
                raise ValueError(
                    "%s has non-finite numeric data in record %i"
                    % (path.name, row_count)
                )

            row_count += 1
            first_event = (
                event_id if first_event is None else min(first_event, event_id)
            )
            last_event = (
                event_id if last_event is None else max(last_event, event_id)
            )
            event_counts[event_id] += 1
            particle_counts[pdg] += 1
            process_counts[process_name(row["step_process"]) or "unknown"] += 1
            detector_counts[detector_id] += 1
            detector_deposit[detector_id] += energy_deposit

            if kinetic_energy <= 0 or sample_limit <= 0:
                continue
            positive_energy_rows += 1
            sample_row = (detector_id, kinetic_energy)
            if len(energy_sample) < sample_limit:
                energy_sample.append(sample_row)
                continue
            replacement = random_generator.randrange(positive_energy_rows)
            if replacement < sample_limit:
                energy_sample[replacement] = sample_row

    if not row_count:
        raise ValueError(path.name + " contains no step records")
    return {
        "path": path,
        "row_count": row_count,
        "first_event": first_event,
        "last_event": last_event,
        "event_counts": event_counts,
        "particle_counts": particle_counts,
        "process_counts": process_counts,
        "detector_counts": detector_counts,
        "detector_deposit": detector_deposit,
        "energy_sample": energy_sample,
        "positive_energy_rows": positive_energy_rows,
    }

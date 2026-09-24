"""Read binary transport-step records written by AtRIS output mode 1."""

import numpy as np

from .binary_output import STEP_RECORDS, read_records


STEP_DTYPE = np.dtype(
    [
        ("event_id", np.int32),
        ("track_id", np.int32),
        ("parent_id", np.int32),
        ("step_id", np.int32),
        ("pdg", np.int32),
        ("detector_id", np.int32),
        ("pre_x_km", np.float64),
        ("pre_y_km", np.float64),
        ("pre_z_km", np.float64),
        ("post_x_km", np.float64),
        ("post_y_km", np.float64),
        ("post_z_km", np.float64),
        ("pre_kinetic_energy_MeV", np.float64),
        ("post_kinetic_energy_MeV", np.float64),
        ("energy_deposit_MeV", np.float64),
        ("nonionizing_energy_deposit_MeV", np.float64),
        ("step_length_m", np.float64),
        ("global_time_ns", np.float64),
        ("primary_energy_MeV", np.float64),
        ("creator_process", "S64"),
        ("step_process", "S64"),
    ]
)


def read_step_records(filename):
    """Memory-map one native AtRIS mode-1 step file."""
    return read_records(filename, STEP_RECORDS, STEP_DTYPE)


def process_name(value):
    """Decode one fixed-width process name from a step record."""
    return bytes(value).partition(b"\0")[0].decode("utf-8")

"""Download and convert NRLMSIS atmosphere data for AtRIS."""

import datetime
import hashlib
import io
import json
import logging
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np


PHI_URL = "https://cosmicrays.oulu.fi/phi/Phi_mon_2017.txt"
NRLMSIS_API_URL = "https://kauai.ccmc.gsfc.nasa.gov/instantrun/api/nrlmsis"
NRLMSIS_MAX_ROWS = 150
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/104.0.0.0 Safari/537.36"
)
logger = logging.getLogger(__name__)


def _to_utc_datetime_string(year, month, day, hour):
    hour_int = int(hour)
    minute_float = (hour - hour_int) * 60.0
    minute_int = int(minute_float)
    second = int(round((minute_float - minute_int) * 60.0))
    timestamp = datetime.datetime(
        year,
        month,
        day,
        hour_int,
        minute_int,
        0,
        tzinfo=datetime.timezone.utc,
    )
    timestamp += datetime.timedelta(seconds=second)
    return timestamp.isoformat().replace("+00:00", "Z")


def _nrlmsis_payload(
    year,
    month,
    day,
    hour,
    longitude,
    latitude,
    hmin,
    hmax,
    deltah,
):
    version = os.environ.get("NRLMSIS_VERSION", "NRLMSIS2")
    return {
        "version": version,
        "timeType": "ut",
        "coordinateType": "geo",
        "datetime": _to_utc_datetime_string(year, month, day, hour),
        "lat": float(latitude),
        "lon": float(longitude),
        "height": max(float(hmax), 100.0),
        "profileType": 1,
        "start": float(hmin),
        "stop": float(hmax),
        "step": float(deltah),
        "fdaily": -1,
        "f3month": -1,
        "ap": -1,
    }


def _nrlmsis_cache_path(payload):
    cache_key = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache_dir = os.path.join(os.getcwd(), ".nrlmsis-cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, cache_key + ".txt")


def _round_altitude(value):
    return round(float(value), 10)


def _expected_nrlmsis_rows(start, stop, step):
    return int(round((float(stop) - float(start)) / float(step))) + 1


def _nrlmsis_chunk_ranges(hmin, hmax, deltah):
    if float(deltah) <= 0.0:
        raise ValueError("deltah must be positive")
    expected_rows = _expected_nrlmsis_rows(hmin, hmax, deltah)
    if expected_rows <= NRLMSIS_MAX_ROWS:
        return [(_round_altitude(hmin), _round_altitude(hmax))]

    chunk_span = float(deltah) * float(NRLMSIS_MAX_ROWS - 1)
    ranges = []
    start = float(hmin)
    while start <= float(hmax) + 1e-9:
        stop = min(float(hmax), start + chunk_span)
        ranges.append((_round_altitude(start), _round_altitude(stop)))
        start = stop + float(deltah)
    return ranges


def _fetch_nrlmsis_output(payload):
    api_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://kauai.ccmc.gsfc.nasa.gov",
        "Referer": "https://kauai.ccmc.gsfc.nasa.gov/instantrun/nrlmsis/",
    }
    request = Request(
        NRLMSIS_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=api_headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            response_text = response.read().decode("utf-8")
    except HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        try:
            response_data = json.loads(response_text)
        except ValueError:
            response_data = {}
        message = (
            response_data.get("error")
            or response_data.get("message")
            or response_text
        )
        raise RuntimeError("CCMC NRLMSIS API request failed: %s" % message) from exc
    try:
        response_data = json.loads(response_text)
    except ValueError as exc:
        raise RuntimeError("CCMC NRLMSIS API returned a non-JSON response.") from exc
    output_url = response_data.get("txt")
    if not output_url:
        raise RuntimeError("CCMC NRLMSIS API response did not include an output URL.")
    request = Request(output_url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def _load_nrlmsis_content(payload):
    cache_path = _nrlmsis_cache_path(payload)
    if os.path.exists(cache_path):
        logger.debug("Using cached NRLMSIS response from %s", cache_path)
        with open(cache_path, "r", encoding="utf-8") as cache_file:
            return cache_file.read()

    content = _fetch_nrlmsis_output(payload)
    with open(cache_path, "w", encoding="utf-8") as cache_file:
        cache_file.write(content)
    logger.debug("Cached NRLMSIS response to %s", cache_path)
    return content


def _parse_nrlmsis_output(content):
    return np.loadtxt(io.StringIO(content), skiprows=1, ndmin=2)


def get_atmosphere(
    year,
    month,
    day,
    hour,
    longitude,
    latitude,
    hmin=0,
    hmax=100,
    deltah=1,
):
    chunk_ranges = _nrlmsis_chunk_ranges(hmin, hmax, deltah)
    parameters = _nrlmsis_payload(
        year,
        month,
        day,
        hour,
        longitude,
        latitude,
        hmin,
        hmax,
        deltah,
    )
    logger.info(
        "Requesting NRLMSIS atmosphere from %.3f to %.3f km at %.3f km steps",
        hmin,
        hmax,
        deltah,
    )
    logger.debug("NRLMSIS request parameters: %s", parameters)
    if len(chunk_ranges) > 1:
        logger.info(
            "Splitting NRLMSIS request into %i chunks for the CCMC row limit",
            len(chunk_ranges),
        )

    chunks = []
    for chunk_start, chunk_stop in chunk_ranges:
        payload = _nrlmsis_payload(
            year,
            month,
            day,
            hour,
            longitude,
            latitude,
            chunk_start,
            chunk_stop,
            deltah,
        )
        logger.debug(
            "Requesting NRLMSIS chunk %.3f to %.3f km",
            chunk_start,
            chunk_stop,
        )
        content = _load_nrlmsis_content(payload)
        chunk_data = _parse_nrlmsis_output(content)
        expected_rows = _expected_nrlmsis_rows(chunk_start, chunk_stop, deltah)
        if chunk_data.shape[0] != expected_rows:
            raise RuntimeError(
                "CCMC NRLMSIS response row count mismatch for chunk "
                "%.3f..%.3f km: expected %i rows, got %i"
                % (
                    chunk_start,
                    chunk_stop,
                    expected_rows,
                    chunk_data.shape[0],
                )
            )
        chunks.append(chunk_data)

    merged = np.vstack(chunks)
    first_indices = np.unique(merged[:, 5], return_index=True)[1]
    merged = merged[first_indices]
    merged = merged[np.argsort(merged[:, 5], kind="stable")]
    expected_total_rows = _expected_nrlmsis_rows(hmin, hmax, deltah)
    if merged.shape[0] != expected_total_rows:
        raise RuntimeError(
            "Merged CCMC NRLMSIS response row count mismatch: expected %i "
            "rows, got %i" % (expected_total_rows, merged.shape[0])
        )
    return merged


def nrlm_reformer(nrlmsis_data):
    if nrlmsis_data.shape[1] >= 28:
        columns = [5, 8, 9, 10, 12, 13, 15, 16, 17, 18]
    else:
        columns = [5, 8, 9, 10, 11, 12, 14, 15, 16, 17]
    return nrlmsis_data[:, columns]


def nrml2psf(data):
    altitude = data[:, 0]
    temperature = data[:, 5]
    density = data[:, 4]
    nitrogen = data[:, 2] + 0.5 * data[:, 9]
    oxygen = data[:, 3] + 0.5 * data[:, 1]
    helium = data[:, 6]
    argon = data[:, 7]
    hydrogen = data[:, 8]

    sheet_count = data.shape[0]
    output = np.zeros((sheet_count, 16))
    earth_radius = 6371000
    thickness = data[1:, 0] - data[:-1, 0]
    thickness *= 1000
    thickness = np.append(thickness, thickness[-1])
    bottom_altitudes = earth_radius + altitude * 1000
    top_altitudes = bottom_altitudes + thickness

    boltzmann_constant = 1.38064852e-23
    oxygen_pressure = oxygen * boltzmann_constant * 1000000 * temperature
    nitrogen_pressure = nitrogen * boltzmann_constant * 1000000 * temperature
    argon_pressure = argon * boltzmann_constant * 1000000 * temperature
    helium_pressure = helium * boltzmann_constant * 1000000 * temperature
    hydrogen_pressure = hydrogen * boltzmann_constant * 1000000 * temperature
    total_pressure = (
        oxygen_pressure
        + nitrogen_pressure
        + argon_pressure
        + helium_pressure
        + hydrogen_pressure
    )

    atomic_mass_unit = 1.66054e-24
    oxygen_mass = oxygen * (2 * 15.9994) * atomic_mass_unit
    nitrogen_mass = nitrogen * (2 * 14.0067) * atomic_mass_unit
    argon_mass = argon * 39.948 * atomic_mass_unit
    helium_mass = helium * 4.0026 * atomic_mass_unit
    hydrogen_mass = hydrogen * 1.008 * atomic_mass_unit
    total_mass = (
        oxygen_mass + nitrogen_mass + argon_mass + helium_mass + hydrogen_mass
    )

    output[:, 0] = bottom_altitudes / 1000.0
    output[:, 1] = top_altitudes / 1000.0
    output[:, 3] = 2 * np.pi
    output[:, 5] = np.pi
    output[:, 6] = np.arange(2, sheet_count + 2)
    output[:, 7] = temperature
    output[:, 8] = density
    output[:, 9] = total_pressure
    output[:, 11] = nitrogen_mass / total_mass
    output[:, 12] = oxygen_mass / total_mass
    output[:, 13] = argon_mass / total_mass
    output[:, 14] = helium_mass / total_mass
    output[:, 15] = hydrogen_mass / total_mass

    logger.debug("Writing simulation.psf")
    number_format = "%e %e %e %e %e %e %i %e %e %e %e %e %e %e %e %e"
    np.savetxt("simulation.psf", output, fmt=number_format)
    with open("simulation.psf", "r") as psf_file:
        atmosphere_lines = psf_file.readlines()

    crust_thickness = 20 / 1000.0
    earth_radius_km = earth_radius / 1000.0
    atmosphere_top = (top_altitudes[-1] + 1) / 1000.0
    reference_temperature = 293.15
    reference_pressure = 101325
    reference_density = 2.7
    with open("simulation.psf", "w") as psf_file:
        psf_file.write("#O478Si284Al84Fe52Ca37Na28Mg15 N O Ar He H\n")
        psf_file.write(
            number_format
            % (
                0,
                earth_radius_km - crust_thickness,
                0,
                2 * np.pi,
                0,
                np.pi,
                0,
                reference_temperature,
                reference_density,
                reference_pressure,
                1.0,
                0,
                0,
                0,
                0,
                0,
            )
        )
        psf_file.write("\n")
        psf_file.write(
            number_format
            % (
                earth_radius_km - crust_thickness,
                earth_radius_km,
                0,
                2 * np.pi,
                0,
                np.pi,
                1,
                reference_temperature,
                reference_density,
                reference_pressure,
                1.0,
                0,
                0,
                0,
                0,
                0,
            )
        )
        psf_file.write("\n")
        psf_file.writelines(atmosphere_lines)
        psf_file.write(
            number_format
            % (
                atmosphere_top,
                atmosphere_top + crust_thickness,
                0,
                2 * np.pi,
                0,
                np.pi,
                sheet_count + 2,
                reference_temperature,
                reference_density,
                reference_pressure,
                1.0,
                0,
                0,
                0,
                0,
                0,
            )
        )
        psf_file.write("\n")


def convert_phi(phi):
    return 1.025 * phi + 24.18


def load_array(url, rowstoskip=7):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        content = response.read().decode("utf-16")
    values = []
    for line in content.split("\n"):
        columns = line.split()
        if len(columns) == 2:
            values.append([float(value) for value in columns])
    return np.array(values)


def find_phi(year, month, day, hour):
    year_start = datetime.date(year, 1, 1)
    event_date = datetime.date(year, month, day)
    elapsed = event_date - year_start + datetime.timedelta(hours=hour)
    year_fraction = elapsed / datetime.timedelta(days=365.25)
    event_year = year + year_fraction
    phi_values = load_array(PHI_URL)
    index = np.absolute(phi_values[:, 0] - event_year).argmin()
    converted_phi = convert_phi(phi_values[index, 1])
    logger.info(
        "Solar modulation parameter: %.2f MV "
        "(Herbst conversion of Usoskin values)",
        converted_phi,
    )
    with open("sim_phi", "w") as phi_file:
        phi_file.write(
            "# Solar modulation parameter phi in MV, obtained from Usoskin, "
            "modified by Herbst.\n"
        )
        phi_file.write("%.2f\n" % converted_phi)
    return converted_phi

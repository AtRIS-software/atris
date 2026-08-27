import json
import shutil
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import numpy as np
import pytest

from atris_tools import simtools


FIXTURE = Path(__file__).parents[1] / "fixtures" / "minimal"


def nrlmsis_content(rows):
    lines = ["header"]
    lines.extend(" ".join(str(value) for value in row) for row in rows)
    return "\n".join(lines) + "\n"


def nrlmsis_row(altitude, marker):
    row = np.arange(28, dtype=float)
    row[5] = altitude
    row[8] = marker
    return row


class Response:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.content


def test_process_psf_and_phantoms_return_numpy_data(tmp_path, monkeypatch):
    geometry, detector_count = simtools.process_psf(FIXTURE / "simulation.psf")

    assert detector_count == 2
    assert geometry.keys() == {"sdid", "volume/cm3", "inn_surface/cm2"}
    np.testing.assert_array_equal(geometry["sdid"], [0, 1])
    assert all(isinstance(values, np.ndarray) for values in geometry.values())

    shutil.copy2(FIXTURE / "phantoms.txt", tmp_path)
    monkeypatch.chdir(tmp_path)
    phantoms = simtools.process_phantoms(1)
    np.testing.assert_allclose(phantoms, [[14094.7550, 1413.72]])


def test_nrlmsis_parser_and_reformer_use_numpy_arrays():
    rows = [nrlmsis_row(0.0, 10.0), nrlmsis_row(1.0, 11.0)]
    atmosphere = simtools._parse_nrlmsis_output(nrlmsis_content(rows))

    assert isinstance(atmosphere, np.ndarray)
    np.testing.assert_allclose(atmosphere, rows)
    np.testing.assert_allclose(
        simtools.nrlm_reformer(atmosphere),
        atmosphere[:, [5, 8, 9, 10, 12, 13, 15, 16, 17, 18]],
    )


def test_nrlmsis_chunks_keep_first_duplicate_and_sort(monkeypatch):
    chunks = {
        0.0: nrlmsis_content([
            nrlmsis_row(0.0, 10.0),
            nrlmsis_row(1.0, 11.0),
        ]),
        1.0: nrlmsis_content([
            nrlmsis_row(1.0, 99.0),
            nrlmsis_row(2.0, 12.0),
        ]),
    }
    monkeypatch.setattr(
        simtools,
        "_nrlmsis_chunk_ranges",
        lambda hmin, hmax, step: [(0.0, 1.0), (1.0, 2.0)],
    )
    monkeypatch.setattr(
        simtools,
        "_load_nrlmsis_content",
        lambda payload: chunks[payload["start"]],
    )

    atmosphere = simtools.get_atmosphere(
        2026,
        8,
        27,
        12.0,
        10.0,
        20.0,
        hmin=0.0,
        hmax=2.0,
        deltah=1.0,
    )

    np.testing.assert_allclose(atmosphere[:, 5], [0.0, 1.0, 2.0])
    np.testing.assert_allclose(atmosphere[:, 8], [10.0, 11.0, 12.0])


def test_fetch_nrlmsis_output_posts_json_and_downloads_text(monkeypatch):
    calls = []

    def open_url(request, timeout):
        calls.append((request, timeout))
        if len(calls) == 1:
            return Response(b'{"txt": "https://example.test/atmosphere.txt"}')
        return Response(b"header\n1 2 3\n")

    monkeypatch.setattr(simtools, "urlopen", open_url)
    payload = {"version": "NRLMSIS2", "start": 0.0, "stop": 1.0}

    content = simtools._fetch_nrlmsis_output(payload)

    api_request, api_timeout = calls[0]
    output_request, output_timeout = calls[1]
    assert api_request.full_url == simtools.NRLMSIS_API_URL
    assert api_request.get_method() == "POST"
    assert json.loads(api_request.data) == payload
    assert api_timeout == 120
    assert output_request.full_url == "https://example.test/atmosphere.txt"
    assert output_request.get_method() == "GET"
    assert output_timeout == 120
    assert content == "header\n1 2 3\n"


def test_fetch_nrlmsis_output_reports_api_error(monkeypatch):
    def open_url(request, timeout):
        raise HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {},
            BytesIO(b'{"error": "Rate limit exceeded"}'),
        )

    monkeypatch.setattr(simtools, "urlopen", open_url)

    with pytest.raises(RuntimeError, match="Rate limit exceeded"):
        simtools._fetch_nrlmsis_output({"version": "NRLMSIS2"})


def test_load_array_downloads_utf16_data(monkeypatch):
    content = "2026.0 500.0\n2026.5 550.0\n".encode("utf-16")
    monkeypatch.setattr(
        simtools,
        "urlopen",
        lambda request, timeout: Response(content),
    )

    values = simtools.load_array("https://example.test/phi.txt")

    np.testing.assert_allclose(values, [[2026.0, 500.0], [2026.5, 550.0]])

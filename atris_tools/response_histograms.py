"""Read AtRIS response histograms from Geant4 CSV or ROOT output."""

import os
import re
from pathlib import Path
import tempfile

import numpy as np
import uproot
from uproot.writing.identify import to_TAxis, to_TH1x, to_TH2x


PRIMARY_HISTOGRAM = "h1.1"
IONIZATION_HISTOGRAM = "h2.ion"
ROOT_STATISTICS = (
    "fEntries",
    "fTsumw",
    "fTsumw2",
    "fTsumwx",
    "fTsumwx2",
    "fTsumwy",
    "fTsumwy2",
    "fTsumwxy",
)


def csv_histogram_path(prefix, name):
    """Return Geant4's CSV path for a named H1 or H2 histogram."""
    histogram_type = name.split(".", 1)[0]
    return Path(str(prefix) + "_" + histogram_type + "_" + name + ".csv")


def response_output_format(prefix):
    """Return the unambiguous response-histogram format for a prefix."""
    prefix = Path(prefix)
    csv_exists = csv_histogram_path(prefix, PRIMARY_HISTOGRAM).is_file()
    root_exists = Path(str(prefix) + ".root").is_file()
    if csv_exists and root_exists:
        raise ValueError(
            "Both CSV and ROOT response output exist for " + prefix.name
        )
    if csv_exists:
        return "csv"
    if root_exists:
        return "root"
    return None


def _csv_lines(path):
    lines = path.read_text().splitlines()
    column_index = next(
        index for index, line in enumerate(lines) if not line.startswith("#")
    )
    return lines, column_index


def read_csv_histogram(path):
    """Read a Geant4 CSV histogram header, columns, and bin table."""
    path = Path(path)
    lines, column_index = _csv_lines(path)
    data = np.loadtxt(path, delimiter=",", skiprows=column_index + 1)
    return lines[:column_index], lines[column_index], np.atleast_2d(data)


def csv_histogram_axes(path):
    """Read histogram axis edges from a Geant4 CSV header."""
    axes = []
    for line in Path(path).read_text().splitlines():
        if line.startswith("#axis edges "):
            axes.append(np.fromstring(line[len("#axis edges ") :], sep=" "))
        elif line.startswith("#axis fixed "):
            fields = line.split()
            axes.append(
                np.linspace(
                    float(fields[3]),
                    float(fields[4]),
                    int(fields[2]) + 1,
                )
            )
        elif not line.startswith("#"):
            break
    if not axes:
        raise ValueError("No histogram axes found in " + str(path))
    return axes


def read_root_histograms(path):
    """Read all H1 and H2 objects from a ROOT response file."""
    histograms = {}
    with uproot.open(path) as root_file:
        for name, class_name in root_file.classnames(cycle=False).items():
            if not class_name.startswith(("TH1", "TH2")):
                continue
            source = root_file[name]
            variances = source.variances(flow=True)
            histograms[name] = {
                "class": class_name,
                "title": source.title,
                "values": np.asarray(source.values(flow=True), dtype=float),
                "variances": (
                    None
                    if variances is None
                    else np.asarray(variances, dtype=float)
                ),
                "axes": [
                    {
                        "edges": np.asarray(axis.edges(), dtype=float),
                        "title": source.member(
                            "fXaxis" if index == 0 else "fYaxis"
                        ).member("fTitle"),
                    }
                    for index, axis in enumerate(source.axes)
                ],
                "statistics": {
                    statistic: float(source.member(statistic))
                    for statistic in (
                        ROOT_STATISTICS
                        if len(source.axes) == 2
                        else ROOT_STATISTICS[:5]
                    )
                },
            }
    if PRIMARY_HISTOGRAM not in histograms:
        raise ValueError(
            "%s does not contain %s" % (Path(path).name, PRIMARY_HISTOGRAM)
        )
    return histograms


def _copy_root_histograms(histograms):
    return {
        name: {
            "class": histogram["class"],
            "title": histogram["title"],
            "values": histogram["values"].copy(),
            "variances": (
                None
                if histogram["variances"] is None
                else histogram["variances"].copy()
            ),
            "axes": [
                {"edges": axis["edges"].copy(), "title": axis["title"]}
                for axis in histogram["axes"]
            ],
            "statistics": histogram["statistics"].copy(),
        }
        for name, histogram in histograms.items()
    }


def _validate_root_histograms(reference, current, path):
    if current.keys() != reference.keys():
        raise ValueError("ROOT response histogram sets differ: " + str(path))
    for name, first in reference.items():
        other = current[name]
        if (
            other["class"] != first["class"]
            or other["title"] != first["title"]
            or other["values"].shape != first["values"].shape
            or len(other["axes"]) != len(first["axes"])
        ):
            raise ValueError("ROOT histogram differs: %s in %s" % (name, path))
        if (other["variances"] is None) != (first["variances"] is None):
            raise ValueError("ROOT histogram differs: %s in %s" % (name, path))
        for first_axis, other_axis in zip(first["axes"], other["axes"]):
            if (
                first_axis["title"] != other_axis["title"]
                or not np.array_equal(first_axis["edges"], other_axis["edges"])
            ):
                raise ValueError(
                    "ROOT histogram axes differ: %s in %s" % (name, path)
                )


def combine_root_histograms(source_paths, observe=None):
    """Add compatible ROOT response histograms and their statistics."""
    reference = read_root_histograms(source_paths[0])
    total = _copy_root_histograms(reference)
    if observe is not None:
        observe(1, reference, total)

    for count, path in enumerate(source_paths[1:], start=2):
        current = read_root_histograms(path)
        _validate_root_histograms(reference, current, path)
        for name, histogram in current.items():
            combined = total[name]
            combined["values"] += histogram["values"]
            if combined["variances"] is not None:
                combined["variances"] += histogram["variances"]
            for statistic, value in histogram["statistics"].items():
                combined["statistics"][statistic] += value
        if observe is not None:
            observe(count, current, total)
    return total


def root_histogram_data(histogram):
    """Return a ROOT histogram in the table layout used by post-processing."""
    values = histogram["values"]
    if values.ndim == 1:
        return np.column_stack((values, values))
    sums = values.ravel(order="F")
    return np.column_stack((np.zeros(sums.size), sums))


def _root_axis(axis, name):
    edges = axis["edges"]
    return to_TAxis(
        name,
        axis["title"],
        len(edges) - 1,
        edges[0],
        edges[-1],
        edges,
    )


def _writable_root_histogram(histogram):
    statistics = histogram["statistics"]
    values = histogram["values"].ravel(order="F")
    variances = histogram["variances"]
    common = {
        "fName": None,
        "fTitle": histogram["title"],
        "data": values,
        "fEntries": statistics["fEntries"],
        "fTsumw": statistics["fTsumw"],
        "fTsumw2": statistics["fTsumw2"],
        "fTsumwx": statistics["fTsumwx"],
        "fTsumwx2": statistics["fTsumwx2"],
        "fSumw2": (
            None if variances is None else variances.ravel(order="F")
        ),
        "fXaxis": _root_axis(histogram["axes"][0], "xaxis"),
    }
    if len(histogram["axes"]) == 1:
        return to_TH1x(**common)
    return to_TH2x(
        **common,
        fYaxis=_root_axis(histogram["axes"][1], "yaxis"),
        fTsumwy=statistics["fTsumwy"],
        fTsumwy2=statistics["fTsumwy2"],
        fTsumwxy=statistics["fTsumwxy"],
    )


def write_root_histograms(path, histograms):
    """Write response histograms to one ROOT file atomically."""
    path = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=path.name + ".",
        suffix=".tmp",
    )
    os.close(descriptor)
    try:
        with uproot.recreate(temporary_name) as root_file:
            for name, histogram in histograms.items():
                root_file[name] = _writable_root_histogram(histogram)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


class ResponseHistogramReader:
    """Expose equivalent response data from CSV files or one ROOT file."""

    def __init__(self, prefix):
        self.prefix = Path(prefix)
        self.format = response_output_format(self.prefix)
        if self.format is None:
            raise FileNotFoundError(
                "No response histogram output found for " + str(self.prefix)
            )
        self._root_file = None

    def __enter__(self):
        if self.format == "root":
            self._root_file = uproot.open(str(self.prefix) + ".root")
            if PRIMARY_HISTOGRAM not in self._root_file:
                self._root_file.close()
                self._root_file = None
                raise ValueError(
                    "%s.root does not contain %s"
                    % (self.prefix.name, PRIMARY_HISTOGRAM)
                )
        return self

    def __exit__(self, exception_type, exception, traceback):
        if self._root_file is not None:
            self._root_file.close()
            self._root_file = None

    def _root(self):
        if self._root_file is None:
            raise RuntimeError("ResponseHistogramReader is not open")
        return self._root_file

    def names(self):
        if self.format == "root":
            root_file = self._root()
            return {
                name
                for name, class_name in root_file.classnames(cycle=False).items()
                if class_name.startswith(("TH1", "TH2"))
            }

        pattern = re.compile(
            "^"
            + re.escape(self.prefix.name)
            + r"_(h[12])_(h[12]\..+)\.csv$"
        )
        return {
            match.group(2)
            for path in self.prefix.parent.glob(self.prefix.name + "_h*.csv")
            if (match := pattern.match(path.name)) is not None
        }

    def axes(self, name):
        if self.format == "root":
            histogram = self._root()[name]
            return [np.asarray(axis.edges()) for axis in histogram.axes]
        return csv_histogram_axes(csv_histogram_path(self.prefix, name))

    def data(self, name):
        """Return bins in the table layout consumed by post-processing."""
        if self.format == "csv":
            return read_csv_histogram(
                csv_histogram_path(self.prefix, name)
            )[2]

        histogram = self._root()[name]
        values = np.asarray(histogram.values(flow=True), dtype=float)
        if len(histogram.axes) == 1:
            if name == PRIMARY_HISTOGRAM:
                entries = float(histogram.member("fEntries"))
                if not np.isclose(values.sum(), entries):
                    raise ValueError(
                        "%s.root contains a weighted %s histogram; per-bin "
                        "primary counts are unavailable"
                        % (self.prefix.name, PRIMARY_HISTOGRAM)
                    )
            return np.column_stack((values, values))
        if len(histogram.axes) == 2:
            sums = values.ravel(order="F")
            return np.column_stack((np.zeros(sums.size), sums))
        raise ValueError(
            "Unsupported response histogram dimension for " + name
        )

    def phantom_count(self):
        indexes = {
            int(match.group(1))
            for name in self.names()
            if (match := re.fullmatch(r"h2\.dos(\d+)", name)) is not None
        }
        if indexes and indexes != set(range(max(indexes) + 1)):
            raise ValueError("Phantom response histogram indexes are not contiguous")
        return len(indexes)

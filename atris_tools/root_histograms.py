"""Combine ROOT response histograms without merging their ntuples."""

import os
from pathlib import Path
import tempfile

import numpy as np
import uproot
from uproot.writing.identify import to_TAxis, to_TH1x, to_TH2x

from .response_histograms import PRIMARY_HISTOGRAM


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


def _copy_histograms(histograms):
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


def _validate_histograms(reference, current, path):
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
    total = _copy_histograms(reference)
    if observe is not None:
        observe(1, reference, total)

    for count, path in enumerate(source_paths[1:], start=2):
        current = read_root_histograms(path)
        _validate_histograms(reference, current, path)
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


def _writable_histogram(histogram):
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


def read_root_metadata(path):
    """Read optional AtRIS run metadata without constraining histograms."""
    with uproot.open(path) as root_file:
        if "metadata" not in root_file:
            return None
        tree = root_file["metadata"]
        arrays = tree.arrays(library="np")
        metadata = {}
        for name in tree.keys():
            values = np.asarray(arrays[name])
            if values.dtype.kind == "O":
                values = np.asarray(values.tolist(), dtype=str)
            metadata[name] = values
        return metadata


def combine_root_metadata(source_paths):
    """Concatenate metadata fields shared by the available ROOT chunks."""
    records = [
        metadata
        for path in source_paths
        if (metadata := read_root_metadata(path)) is not None
    ]
    if not records:
        return None
    fields = set.intersection(*(set(record) for record in records))
    if not fields:
        return None
    return {
        name: np.concatenate([record[name] for record in records])
        for name in sorted(fields)
    }


def write_root_histograms(path, histograms, metadata=None):
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
                root_file[name] = _writable_histogram(histogram)
            if metadata:
                root_file["metadata"] = metadata
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)

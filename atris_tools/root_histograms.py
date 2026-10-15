"""Combine ROOT response histograms without merging their ntuples."""

import os
from pathlib import Path
import tempfile

import numpy as np
import uproot
from uproot.writing.identify import to_TAxis, to_TH1x, to_TH2x

from .response_histograms import PRIMARY_HISTOGRAM, read_root_histogram


def _read_metadata(root_file):
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


def read_root_file(path):
    """Read response histograms and optional metadata from one ROOT file."""
    histograms = {}
    with uproot.open(path) as root_file:
        for name, class_name in root_file.classnames(cycle=False).items():
            if not class_name.startswith(("TH1", "TH2")):
                continue
            histograms[name] = read_root_histogram(root_file[name])
        metadata = _read_metadata(root_file)
    if PRIMARY_HISTOGRAM not in histograms:
        raise ValueError(
            "%s does not contain %s" % (Path(path).name, PRIMARY_HISTOGRAM)
        )
    return histograms, metadata


def combine_root_histograms(source_paths, observe=None):
    """Add compatible ROOT histograms and concatenate available metadata."""
    total, metadata = read_root_file(source_paths[0])
    metadata_records = [] if metadata is None else [metadata]
    if observe is not None:
        observe(1, total, total)

    for count, path in enumerate(source_paths[1:], start=2):
        current, metadata = read_root_file(path)
        if current.keys() != total.keys():
            raise ValueError("ROOT response histogram sets differ: " + str(path))
        for name, histogram in current.items():
            total[name].add(histogram, "%s in %s" % (name, path))
        if metadata is not None:
            metadata_records.append(metadata)
        if observe is not None:
            observe(count, current, total)

    if not metadata_records:
        return total, None
    fields = set.intersection(*(set(record) for record in metadata_records))
    if not fields:
        return total, None
    combined_metadata = {
        name: np.concatenate([record[name] for record in metadata_records])
        for name in sorted(fields)
    }
    return total, combined_metadata


def _root_axis(edges, title, name):
    return to_TAxis(
        name,
        title,
        len(edges) - 1,
        edges[0],
        edges[-1],
        edges,
    )


def _writable_histogram(histogram):
    variances = histogram.variances
    common = {
        "fName": None,
        "fTitle": histogram.title,
        "data": histogram.values.ravel(order="F"),
        "fSumw2": None if variances is None else variances.ravel(order="F"),
        "fXaxis": _root_axis(histogram.axes[0], histogram.axis_titles[0], "xaxis"),
        **histogram.statistics,
    }
    if len(histogram.axes) == 1:
        return to_TH1x(**common)
    return to_TH2x(
        **common,
        fYaxis=_root_axis(histogram.axes[1], histogram.axis_titles[1], "yaxis"),
    )


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

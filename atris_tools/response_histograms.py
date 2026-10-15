"""Read AtRIS response histograms from Geant4 CSV or ROOT output."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import uproot


PRIMARY_HISTOGRAM = "h1.1"
IONIZATION_HISTOGRAM = "h2.ion"
TOTAL_DEPOSITION_HISTOGRAM = "h2.edep"
BIN_ENTRIES = 0
BIN_SUM_WEIGHTS = 1
PLANE_SUM_PREFIX = "#planes_Sxyw "
ATRIS_ANNOTATION_PREFIX = "#annotation atris."
ROOT_STATISTICS = (
    "fEntries", "fTsumw", "fTsumw2", "fTsumwx", "fTsumwx2",
    "fTsumwy", "fTsumwy2", "fTsumwxy",
)


@dataclass
class Histogram:
    """Bin values, edges and available squared-weight sums, including flow bins.

    ROOT statistics and CSV annotations retain format-specific information;
    missing uncertainty information is represented by None, not inferred.
    """

    values: np.ndarray
    axes: list[np.ndarray]
    variances: np.ndarray | None = None
    title: str = ""
    axis_titles: tuple[str, ...] = ()
    statistics: dict[str, float] = field(default_factory=dict)
    root_class: str | None = None
    annotations: tuple[str, ...] = ()
    bin_statistics: np.ndarray | None = None
    columns: tuple[str, ...] = ()
    value_column: int = BIN_SUM_WEIGHTS
    plane_sum: float | None = None

    def __str__(self):
        lines = ["Histogram" + (": " + self.title if self.title else ""),
                 f"Value shape: {self.values.shape}"]
        if self.axes:
            for index, axis in enumerate(self.axes):
                label = (self.axis_titles[index] if index < len(self.axis_titles) else "") or f"Axis {index}"
                extent = (f"{len(axis) - 1:,} {'bin' if len(axis) == 2 else 'bins'} "
                          f"from {axis[0]:g} to {axis[-1]:g}"
                          if len(axis) >= 2 else "bin edges unavailable")
                lines.append(f"{label}: {extent}")
            lines.append("Values include underflow and overflow bins")
        else:
            lines.append("Bin edges unavailable")
        lines.append("Squared-weight sums: " + ("available" if self.variances is not None else "unavailable"))
        return "\n".join(lines)

    def __post_init__(self):
        if self.bin_statistics is not None:
            if self.bin_statistics.shape[-1] != len(self.columns):
                raise ValueError("Histogram bin statistics do not match its columns")
            self.values = self.bin_statistics[..., self.value_column]
            self.variances = (self.bin_statistics[..., self.columns.index("Sw2")]
                              if self.value_column == BIN_SUM_WEIGHTS and "Sw2" in self.columns else None)
        if self.axes and self.values.shape != tuple(len(axis) + 1 for axis in self.axes):
            raise ValueError("Histogram values do not match its axes and flow bins")
        if self.variances is not None and self.variances.shape != self.values.shape:
            raise ValueError("Histogram squared-weight sums do not match its values")

    @property
    def entries(self):
        """Per-bin fill counts when recorded; ROOT does not supply these."""
        return None if self.bin_statistics is None else self.bin_statistics[..., BIN_ENTRIES]

    def add(self, other, description):
        """Add compatible bin statistics in place without changing geometry."""
        if (self.root_class != other.root_class or self.title != other.title
                or self.values.shape != other.values.shape
                or len(self.axes) != len(other.axes)
                or self.statistics.keys() != other.statistics.keys()
                or self.columns != other.columns or self.value_column != other.value_column
                or (self.bin_statistics is None) != (other.bin_statistics is None)
                or (self.plane_sum is None) != (other.plane_sum is None)
                or comparable_header(self.annotations) != comparable_header(other.annotations)
                or (self.variances is None) != (other.variances is None)):
            raise ValueError("Histogram differs: " + description)
        if self.axis_titles != other.axis_titles or any(
                not np.array_equal(first, second) for first, second in zip(self.axes, other.axes)):
            raise ValueError("Histogram axes differ: " + description)
        if self.bin_statistics is not None:
            self.bin_statistics += other.bin_statistics
        else:
            self.values += other.values
            if self.variances is not None:
                self.variances += other.variances
        for name, value in other.statistics.items():
            self.statistics[name] += value
        if self.plane_sum is not None:
            self.plane_sum += other.plane_sum

    def write_csv(self, output):
        """Write all recorded bin statistics to an open text stream."""
        if self.bin_statistics is None:
            raise ValueError("CSV requires per-bin entries and moments absent from ROOT")
        for line in self.annotations:
            if line.startswith(PLANE_SUM_PREFIX) and self.plane_sum is not None:
                line = PLANE_SUM_PREFIX + "%.17g" % self.plane_sum
            output.write(line + "\n")
        output.write(",".join(self.columns) + "\n")
        data = self.bin_statistics.swapaxes(0, 1) if len(self.axes) == 2 else self.bin_statistics
        np.savetxt(output, data.reshape(-1, len(self.columns)), delimiter=",",
                   fmt=["%.0f"] + ["%.17e"] * (len(self.columns) - 1))


def comparable_header(header):
    return [line for line in header
            if not line.startswith((PLANE_SUM_PREFIX, ATRIS_ANNOTATION_PREFIX))]


def read_root_histogram(source):
    """Keep ROOT bin data, axis labels and accumulated statistics together."""
    variances = source.variances(flow=True) if len(source.member("fSumw2")) else None
    return Histogram(
        values=np.asarray(source.values(flow=True), dtype=float),
        axes=[np.asarray(axis.edges(), dtype=float) for axis in source.axes],
        variances=None if variances is None else np.asarray(variances, dtype=float),
        title=source.title,
        axis_titles=tuple(source.member(name).member("fTitle")
                          for name in ("fXaxis", "fYaxis")[:len(source.axes)]),
        statistics={name: float(source.member(name)) for name in
                    (ROOT_STATISTICS if len(source.axes) == 2 else ROOT_STATISTICS[:5])},
        root_class=source.classname,
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


def read_csv_histogram(path):
    """Read every Geant4 CSV bin statistic into the shared histogram model.

    Missing axes remain an empty list; no bin edges are invented.
    """
    path = Path(path)
    lines = path.read_text().splitlines()
    column_index = next(index for index, line in enumerate(lines) if not line.startswith("#"))
    header = lines[:column_index]
    columns = tuple(column.strip() for column in lines[column_index].split(","))
    data = np.loadtxt(path, delimiter=",", skiprows=column_index + 1, ndmin=2)
    axes = _csv_axes(header)
    if axes:
        shape = tuple(len(axis) + 1 for axis in axes)
        if len(shape) not in (1, 2) or data.shape != (np.prod(shape), len(columns)):
            raise ValueError("Histogram table size does not match its axes: " + str(path))
        data = data.reshape(*shape[::-1], len(columns))
        if len(shape) == 2:
            data = data.swapaxes(0, 1)
    column = BIN_ENTRIES if path.name.endswith("_h1_h1.1.csv") else BIN_SUM_WEIGHTS
    return Histogram(data[..., column], axes, bin_statistics=data, columns=columns,
                     value_column=column, annotations=tuple(header),
                     title=next((line[len("#title "):] for line in header
                                 if line.startswith("#title ")), ""),
                     plane_sum=next((float(line[len(PLANE_SUM_PREFIX):]) for line in header
                                     if line.startswith(PLANE_SUM_PREFIX)), None))


def _csv_axes(header):
    axes = []
    for line in header:
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
    return axes


def csv_histogram_axes(path):
    """Read only axis metadata, without loading histogram bin statistics."""
    axes = _csv_axes(Path(path).read_text().splitlines())
    if not axes:
        raise ValueError("No histogram axes found in " + str(path))
    return axes


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

    def __getitem__(self, name):
        """Read one histogram with the same representation for either format."""
        if self.format == "csv":
            path = csv_histogram_path(self.prefix, name)
            histogram = read_csv_histogram(path)
            if not histogram.axes:
                raise ValueError("No histogram axes found in " + str(path))
            return histogram

        histogram = read_root_histogram(self._root()[name])
        if name == PRIMARY_HISTOGRAM and not np.isclose(
                histogram.values.sum(), histogram.statistics["fEntries"]):
            raise ValueError(
                "%s.root contains a weighted %s histogram; per-bin primary counts are unavailable"
                % (self.prefix.name, PRIMARY_HISTOGRAM))
        if len(histogram.axes) not in (1, 2):
            raise ValueError(
                "Unsupported response histogram dimension for " + name
            )
        return histogram

    def phantom_count(self):
        indexes = {
            int(match.group(1))
            for name in self.names()
            if (match := re.fullmatch(r"h2\.dos(\d+)", name)) is not None
        }
        if indexes and indexes != set(range(max(indexes) + 1)):
            raise ValueError("Phantom response histogram indexes are not contiguous")
        return len(indexes)

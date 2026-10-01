# Software ecosystem

An AtRIS calculation brings together a planetary model, particle transport,
and analysis of the resulting radiation field. Several tools in the wider
simulation community address different parts of that work. Geant4 supplies the
transport used by AtRIS; pyg4ometry, ROOT, and HDF5 offer ways to work with
geometry and scientific data around a simulation.

The Python analysis work is based on [NumPy](https://numpy.org/doc/stable/) for
numerical arrays and [Matplotlib](https://matplotlib.org/stable/) for plotting,
with [Jupyter notebooks](https://jupyter.org/) used for interactive calculations
and exploration. The [exoplanet notebook](../tutorials/exoplanet-psf.ipynb)
uses these tools to construct and inspect an atmospheric model.

## Geant4: particle transport

[Geant4](https://geant4.web.cern.ch/) follows particles through matter using the
geometry, materials, source, and physics configured by the application. AtRIS
uses it to calculate interactions in the planetary model and records deposition
and interface crossings. [How AtRIS uses Geant4](geant4-and-atris.md) follows
one primary history through that calculation.

Geant4 also provides analysis classes for accumulating histograms and writing
results. Its [analysis managers](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Analysis/managers.html)
support formats including CSV, ROOT, and HDF5, depending on the manager and
build configuration. The application chooses which of those facilities it uses.

## GDML: exchanging geometry

[GDML (Geometry Description Markup Language)](https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/Geometry/geomXML.html)
is an XML format for describing materials, solid shapes, and the placement of
volumes within a geometry. It lets a geometry be stored in a readable file and
exchanged between Geant4 and other tools.

AtRIS converts the planetary layers in `simulation.psf` into `simulation.gdml`
with `atris-psf-to-gdml`. Geant4 then loads the generated geometry for particle
transport. The PSF remains the model input used by preparation and
post-processing; the [GDML input reference](../reference/inputs.md#gdml)
describes the additional detector tags required by AtRIS.

## pyg4ometry: constructing and inspecting geometry

[pyg4ometry](https://pyg4ometry.readthedocs.io/en/stable/) is a Python package
for creating, reading, editing, and displaying radiation-transport geometries.
It can read and write GDML, provides a VTK viewer, and supports conversions
involving CAD and ROOT geometry.

For AtRIS, a geometry viewer can help inspect the arrangement of volumes in
the generated `simulation.gdml` before running transport. pyg4ometry is an
optional tool for this work.

If you modify the GDML outside the PSF workflow, account for AtRIS's sensitive
layer IDs and the PSF geometry used during post-processing. A geometry that can
be displayed is not by itself a complete AtRIS model. See the
[geometry input reference](../reference/inputs.md#gdml) for those conventions.

## ROOT: analysis and ROOT files

[ROOT](https://root.cern/manual/) is a scientific data-analysis framework with
histograms, plotting, fitting, and facilities for storing and processing data.
A [ROOT file](https://root.cern/manual/root_files/), usually named `.root`, can
hold objects such as histograms as well as columnar datasets. ROOT is therefore
both an analysis environment and the name associated with a file format.
Its [Python interface, PyROOT](https://root.cern/manual/python/), makes those
facilities available from Python.

AtRIS uses Geant4's generic analysis manager. Response mode writes histogram
CSVs; profile and shower modes write the same histograms and their particle
ntuples to ROOT. The Python tools read ROOT with
[Uproot](https://uproot.readthedocs.io/) and do not require a separate ROOT
installation.

## HDF5: arrays and metadata in one file

HDF5 is a scientific data format that organizes datasets into groups and allows
metadata to be attached as attributes. In Python, [h5py](https://docs.h5py.org/en/stable/quick.html)
provides access to those datasets with NumPy-style array operations. Files
commonly use `.h5` or `.hdf5` extensions.

A possible downstream use for AtRIS is an analysis archive containing response
arrays, primary-energy axes, layer coordinates, and the settings for several
runs. Such an archive should also record units, normalization, and which
primaries contributed to each response. HDF5 provides the storage structure;
the analysis must define what the datasets mean.

The current AtRIS tools do not supply an HDF5 export or read HDF5 as their
standard simulation output. The [output reference](../reference/outputs.md)
describes the CSV and ROOT products written by this version, and
[processing results](../running-atris/process-results.md) covers the supported
response-table workflow.

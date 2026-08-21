# Installing AtRIS

This document covers the work done once for a machine or compiler environment:

1. install the build requirements;
2. build Geant4;
3. build AtRIS;
4. confirm that the executable and Geant4 runtime are present.

The steps repeated for each shell session and simulation are in the
[running instructions](MODERN.md).

## Requirements

AtRIS requires:

- [Geant4](https://geant4.web.cern.ch/) with GDML, multithreading, and runtime
  datasets;
- [Xerces-C++](https://xerces.apache.org/xerces-c/) for GDML support;
- [CMake](https://cmake.org/) 3.22 or newer;
- a C++17 compiler.

The preparation tools and automated system test use
[Python](https://www.python.org/).

A package manager or an HPC
[environment-module system](https://modules.readthedocs.io/en/latest/) is
needed to make the compiler, CMake, Xerces-C++, and Python available in the
shell. For example, [Homebrew](https://brew.sh/) can provide the macOS packages:

```bash
brew install cmake xerces-c
```

On an HPC system, use its module system to load the corresponding compiler,
CMake, Xerces-C++, and Python packages before running the build commands.

## Directory layout

The commands used here assume a target workspace with the AtRIS and Geant4
directories beside one another:

```text
atris-work/
|-- atris/
`-- geant4/
    |-- source/
    |-- build/
    `-- install/
```

Start in `atris-work`:

```bash
cd atris-work
```

## Installing Geant4

Geant4 is a particle-transport simulation toolkit. AtRIS uses it to model the
interactions of particles with the planet and atmosphere.

### Why build from source

Geant4 publishes [binary releases](https://geant4.web.cern.ch/download/) for
selected operating-system and compiler combinations. The macOS binary
available when this setup was tested was built without GDML support. These
instructions therefore build Geant4 from source, explicitly enabling GDML and
multithreading and installing the physics datasets used by AtRIS.

Enter the Geant4 directory in the target workspace:

```bash
cd geant4
```

### Obtain the source

Download and unpack a Geant4 source archive so that its top-level
`CMakeLists.txt` is at:

```text
source/CMakeLists.txt
```

For an archive placed in `atris-work`:

```bash
mkdir -p source
tar -xf ../geant4-VERSION.tar.gz --strip-components=1 -C source
```

### Configure and install

Configure Geant4 with the features required by AtRIS, then build and install
it in the target workspace:

```bash
cmake -S source \
  -B build \
  -DCMAKE_INSTALL_PREFIX="$PWD/install" \
  -DGEANT4_USE_GDML=ON \
  -DGEANT4_BUILD_MULTITHREADED=ON \
  -DGEANT4_INSTALL_DATA=ON

cmake --build build -j
cmake --install build
```

`GEANT4_INSTALL_DATA=ON` installs the runtime datasets used during physics
initialization.

### Verify the installation

The installed Geant4 runtime and CMake package must now exist:

```bash
test -f install/bin/geant4.sh
test -f install/lib/cmake/Geant4/Geant4Config.cmake
```

## Installing AtRIS

Return to the target workspace and clone Dag Evensberget's
[AtRIS repository](https://github.com/svaberg/atris2-mirror) from GitHub's
`main` branch into `atris/`:

```bash
cd ..
git clone --branch main https://github.com/svaberg/atris2-mirror.git atris
```

Configure and build the AtRIS C++ executable:

```bash
cmake -S atris/atris \
  -B atris/atris/build \
  -DGeant4_DIR="$PWD/geant4/install/lib/cmake/Geant4" \
  -DWITH_GEANT4_UIVIS=OFF

cmake --build atris/atris/build -j
```

The non-GUI build is sufficient for command-line and HPC simulations. Check
the resulting executable:

```bash
test -x atris/atris/build/AtRIS
```

Running it without simulation arguments prints its expected argument form:

```bash
atris/atris/build/AtRIS
```

The expected line is:

```text
### AtRIS: ./AtRIS physicslist simname mode nrofphantoms
```

At this point installation is complete. Continue with the
[running instructions](MODERN.md) to prepare and execute a simulation.

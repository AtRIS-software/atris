# Installing AtRIS

This document covers the work done once for a machine or compiler environment:

1. install the build requirements;
2. build Geant4;
3. build AtRIS;
4. confirm that the executable and Geant4 runtime are present;
5. create the Python environment.

The steps repeated for each shell session and simulation are in the
[running instructions](README.md).

## Requirements

AtRIS requires:

- [Geant4](https://geant4.web.cern.ch/) with GDML, multithreading, and runtime
  datasets;
- [Xerces-C++](https://xerces.apache.org/xerces-c/) for GDML support;
- [CMake](https://cmake.org/) 3.22 or newer;
- a C++17 compiler, used consistently to build both Geant4 and AtRIS;
- [Git](https://git-scm.com/) to obtain the AtRIS source;
- [Conda](https://docs.conda.io/projects/conda/en/stable/) to manage the Python
  environment.

The preparation tools and automated system test use
[Python](https://www.python.org/).

On macOS, Apple's
[Command Line Tools](https://developer.apple.com/documentation/xcode/installing-the-command-line-tools/)
provide Git and AppleClang:

```bash
xcode-select --install
```

[Homebrew](https://brew.sh/) can provide CMake and Xerces-C++:

```bash
brew install cmake xerces-c
```

Use one C++ toolchain throughout the installation. The Command Line Tools make
AppleClang the default compiler on macOS.

On an HPC system, use its
[environment-module system](https://modules.readthedocs.io/en/latest/) to load
one compiler, a compatible Xerces-C++, and the required CMake, Git, and Python
modules before running the build commands. When reusing an existing Geant4
installation, use the compiler with which that installation was built.

## Directory layout

The commands used here assume a target workspace with the AtRIS and Geant4
directories beside one another:

```text
<ATRIS_WORK>/
├── atris/
└── geant4-<VERSION>/
    ├── build/
    └── install/
```

Start in `<ATRIS_WORK>`:

```bash
cd <ATRIS_WORK>
```

## Installing Geant4

Geant4 is a particle-transport simulation toolkit. AtRIS uses it to model the
interactions of particles with the planet and atmosphere. AtRIS requires a
Geant4 installation with GDML, multithreading, and the runtime datasets. The
official [Building and Installing from Source](https://geant4-userdoc.web.cern.ch/UsersGuides/InstallationGuide/html/installguide.html#on-unix-platforms)
guide describes the general procedure; the commands below provide the options
required by AtRIS.

Geant4 binary installations are available only for selected systems and do
not necessarily include GDML support. Building from source lets us enable
GDML, install the required runtime datasets, and use the same compiler
toolchain for Geant4 and AtRIS.

### Obtain the source

Download a source archive in `tar.gz` format from the official
[Geant4 releases](https://geant4.web.cern.ch/download/) page. Place it in
`<ATRIS_WORK>`, then unpack it and enter the resulting directory. In the
commands below, `<VERSION>` is a placeholder for the Geant4 version in the
archive and directory names, for example `v11.4.2`.

```bash
cd <ATRIS_WORK>
tar -xf geant4-<VERSION>.tar.gz
cd geant4-<VERSION>
```

### Configure and install

Configure Geant4 with the features required by AtRIS, then build and install
it in the target workspace:

```bash
cmake -B build \
  -DCMAKE_INSTALL_PREFIX="$PWD/install" \
  -DGEANT4_USE_GDML=ON \
  -DGEANT4_BUILD_MULTITHREADED=ON \
  -DGEANT4_INSTALL_DATA=ON

cmake --build build -j
cmake --install build
```

`GEANT4_USE_GDML` enables GDML support, and `GEANT4_INSTALL_DATA` installs the
standard datasets. `GEANT4_BUILD_MULTITHREADED=ON` is included explicitly for
clarity, although it is currently the default.

### Verify the installation

Load the installed Geant4 environment, then inspect the installation:

```bash
source install/bin/geant4.sh
geant4-config --version
geant4-config --features
geant4-config --check-datasets
```

The feature list must show `gdml[yes]` and `multithreading[yes]`. Dataset
requirements depend on the physics list; `GEANT4_INSTALL_DATA=ON` installs the
full standard set for convenience.

## Installing AtRIS

Start again from the directory containing the target workspace, and clone the AtRIS repository:
```bash
cd <ATRIS_WORK>
git clone git@github.com:svaberg/atris.git
```

### Build AtRIS

Load the Geant4 environment so CMake can find the installed package, then
configure and build AtRIS with the same compiler used to build Geant4:

```bash
cd <ATRIS_WORK>

source geant4-<VERSION>/install/bin/geant4.sh

cd atris
cmake -B build
cmake --build build -j
```

Run the executable without simulation arguments to print its expected argument
form:

```bash
./build/AtRIS
```

The expected output is:

```text
Usage: ./build/AtRIS <physics-list> <simulation-name> <mode> <phantom-count>
```

### Install the Python environment

The atmosphere preparation and result-processing tools use the Python packages
listed in `environment.yml`. Create the environment once from the target
workspace:

```bash
cd <ATRIS_WORK>
conda env create -f atris/environment.yml
conda activate atris
python -m pip install -e atris
```

The editable installation registers the AtRIS preparation and post-processing
commands while keeping their Python source in the checkout.

At this point installation is complete. Continue with the
[running instructions](README.md) to prepare and execute a simulation.

## FAQ

These are the most likely problems to encounter while following the
installation steps.

### I ran `git` and got `command not found`

On macOS, install Apple's Command Line Tools. They provide Git as well as the
AppleClang compiler:

```bash
xcode-select --install
```

On an HPC system, Git may already be available after loading the appropriate
module. Modules must be loaded again after opening a new shell.

### I ran `cmake` and got `command not found`

On macOS, install CMake with [Homebrew](https://brew.sh/):

```bash
brew install cmake
```

On an HPC system, load the available CMake module. If CMake was available in a
previous shell, its module may simply need to be loaded again.

### CMake says `No CMAKE_CXX_COMPILER could be found`

On macOS, `xcode-select --install` installs AppleClang. On an HPC system, load
the compiler module intended for the Geant4 and AtRIS builds, then run CMake
again. Compiler modules must be loaded again after opening a new shell.

### I ran `geant4-config` and got `command not found`

After installing Geant4, load its environment into the current shell:

```bash
source <ATRIS_WORK>/geant4-<VERSION>/install/bin/geant4.sh
```

This environment applies only to the current shell, so source `geant4.sh`
again after opening a new one.

### I broke AtRIS! How do I rebuild it?

If only the generated build is broken, remove it:

```bash
cd <ATRIS_WORK>/atris
rm -r build
```

Then repeat the [AtRIS build instructions](#build-atris). This recreates
the build directory but does not undo changes to the AtRIS source files.

### Why does linking fail with undefined Geant4 symbols?

This usually means that AtRIS and Geant4 were built with incompatible C++
compilers or standard libraries. For example, AtRIS may compile with GCC and
`libstdc++` but then fail to link against a Geant4 installation built with
AppleClang and `libc++`. Typical missing symbols include
`G4VAnalysisManager::CreateH1` and `CreateH2`.

CMake remembers the selected compiler in the build directory, so changing the
shell environment is not enough for an existing build. Remove the failed AtRIS
build [as described above](#i-broke-atris-how-do-i-rebuild-it) and select the
compiler used for Geant4. For example, if Geant4 was built with the system
AppleClang compiler on macOS:

```bash
export CC=/usr/bin/clang
export CXX=/usr/bin/clang++
```

Then repeat the [AtRIS build instructions](#build-atris).

# AtRIS

AtRIS: the Atmospheric Radiation Interaction Simulator.
============================================= 
Author: Saša Banjac

 + For description and validation, please read the AtRIS validation papers by Banjac et al (2018).
 + Documentation can be found on https://et-wiki.physik.uni-kiel.de/atris/atris
 + Author: Saša Banjac
 + 

Build notes
===========

 + AtRIS requires a Geant4 build with GDML enabled.
 + Configure Geant4 with `-DGEANT4_USE_GDML=ON` and make sure Xerces-C++ is available.
 + The modern AtRIS build requires Geant4 with GDML and multithreading, CMake `3.22+`, and C++17.
 + Example configure/build commands:

```bash
cmake -S . -B build-modern \
  -DGeant4_DIR=/path/to/geant4/lib/cmake/Geant4 \
  -DWITH_GEANT4_UIVIS=OFF

cmake --build build-modern -j4
```


Organization of material
========================
 + ./src/ contains the source code
 + ./include/ contains the headers
 + ./interfaces/ contains the interface scripts
 + ./evaluation/ contains scripts for evaluation
 + ./phantoms/ contains phantom response files
 + ./examples/ contains a set of examples

List-of-changes
===============

 + DATE:
 + CHAGE:
 

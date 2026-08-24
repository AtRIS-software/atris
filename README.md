# AtRIS2
Atmospheric Radiation Interaction Simulator
With multi-threading, count rate mode, multiple phantom calulations and improved usabilityty. 

Description: This repository packages the AtRIS code, including all available phantom files and several helper tools that will help you:
 - Check if requirements are satisfied (see below)
 - Download and install geant4
 - Download and install AtRIS
 - Define your simulation
 - Start and monitor your simulation
 - Do data post-processing and prepare the data for evaluation with the Werkzeug
 
 Under documentation, a schematic view of the approach is provided. Please use draw.io to open that file. 

Purpose:
 - Make AtRIS easier to use to calculate ionization, absorbed dose, dose equivalent and count rate, in particular useful for aircraft dosimetry. 
 - this is ment to help you start Earth atmosphere simulations. Advanced uses, such as Mars and Venus simulations are not available due to licencing constraints. 
 - It still cant produce secondary particle spectra.
 - It requires some knowledge about linux systems and python to be usable.

## Modern build status
 - The core `atris/` application now builds against Geant4 `11.4.2` with GDML enabled.
 - The build has been validated with Apple Clang `17` on macOS and uses CMake `3.22+` with C++17.
 - GDML support is required because AtRIS uses `G4GDMLParser.hh` directly. Your Geant4 build must therefore be configured with `-DGEANT4_USE_GDML=ON`.
 - The helper notebooks and scripts are still Linux-oriented, but the core C++ build no longer assumes an old Geant4 release.

## Modern build recipe
Point AtRIS at an existing Geant4 install instead of letting the repo manage Geant4 for you.

```bash
cmake -S atris -B atris/build-modern \
  -DGeant4_DIR=/path/to/geant4/lib/cmake/Geant4

cmake --build atris/build-modern -j4
```

## Requirements:
 - Linux remains the primary supported runtime environment for the full workflow.
 - The core `atris/` build also works on recent macOS toolchains when Geant4 and Xerces-C++ are available.
 - Please make sure your system has a modern C++ compiler, CMake, and Xerces-C++ installed. We recommend system or package-manager installs instead of conda for Geant4 dependencies.
 - Python 3 is necessary. For Python packages, we recommend using Conda. Packages that are not available through Conda can be installed with pip.
 - To run the Werkzeug, docker is needed. The user must have docker run permissions. If that is given, just:
> docker run --restart=always -p 9123:8888 werkzeug:mt

## Instructions:
 - clone: 
> git clone https://gitlab.physik.uni-kiel.de/ET/atris2.git ./AtRIS2
 - cd in to the diretory, activate onda and start jupyter lab:
> cd ./AtRIS2
> jupyter lab
 - open the simstarter jupyter notebook and you are good to go. 
 - modify root dir, read the notebook and work with it.
 - if you are planning on using the Werkzeug, start the werkzeug - see info below. 
  
   
## Folder structure

## About Werkyzeug
 - The Werkzeug is used to analize and visualize the data. The main inputs are:
   - The simulation results
   - Phantom selection (an index between 0 and 31)
   - Solar modulation parameter phi
   - Geomagnetic Cutoff rigidity 
 - Werkzeug is being updated:
   - We are adding GUI scaling to have better visibility
   - We will implemement a preselection of optimal phantoms and automatic loading of phi
   - We will add band functions for the solar proton spetrum
   - ETA march 2023
 - To run the werkzeug start:
 > docker run --restart=always -p 9123:8888 werkzeug:mt
   - This will make the Werkzeug available under localhost:9123 in your browser.
   - If you encounter any problems, hit refresh. 
   - Once Werkzeug is updated, docker will recognize the new image and automatically download it.
 - Detailed information available on https://gitlab.physik.uni-kiel.de/banjac/atris-werkzeug

## About simulating secondary particles
 - While AtRIS produces seondary partile information, in order to obtain spetra from this data, a lot of post processing needs to be done.
 - For the moment, additional work is required to make this available to third parties. This could be an extension of the current approach, however no plans have been set in to motion.



## Notes:
 - We are in preview. You will encounter errors. Please document and report the errors. 
 - Scaling beyond a certain number of cores doesn't yield better results. This is CPU speific and has to the with the cache topography. Test it.
 - 

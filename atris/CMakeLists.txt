cmake_minimum_required(VERSION 3.22)

project(AtRIS LANGUAGES CXX)

option(WITH_GEANT4_UIVIS "Build AtRIS with all available Geant4 UI and visualization drivers" ON)

set(ATRIS_GEANT4_COMPONENTS gdml multithreaded)
if(WITH_GEANT4_UIVIS)
  list(APPEND ATRIS_GEANT4_COMPONENTS ui_all vis_all)
endif()

find_package(Geant4 REQUIRED COMPONENTS ${ATRIS_GEANT4_COMPONENTS})

set(ATRIS_HEADERS
  include/DetectorConstruction.hh
  include/HistoManager.hh
  include/PrimaryGeneratorAction.hh
  include/RunAction.hh
  include/SensitiveDetector.hh
  include/UserActionInitialization.hh
)

set(ATRIS_SOURCES
  main.cc
  src/DetectorConstruction.cc
  src/HistoManager.cc
  src/PrimaryGeneratorAction.cc
  src/RunAction.cc
  src/SensitiveDetector.cc
  src/UserActionInitialization.cc
)

add_executable(AtRIS)
target_sources(AtRIS PRIVATE ${ATRIS_SOURCES} ${ATRIS_HEADERS})
target_include_directories(AtRIS PRIVATE ${PROJECT_SOURCE_DIR}/include)
target_link_libraries(AtRIS PRIVATE ${Geant4_LIBRARIES})
target_compile_features(AtRIS PRIVATE cxx_std_17)
set_property(TARGET AtRIS PROPERTY CXX_EXTENSIONS OFF)
target_compile_options(AtRIS PRIVATE
  $<$<CXX_COMPILER_ID:AppleClang,Clang,GNU>:-Wall;-Wextra;-Wpedantic>
)

#----------------------------------------------------------------------------
# For internal Geant4 use - but has no effect if you build this
# example standalone
#
#add_custom_target(G4ET DEPENDS G4ET)

#----------------------------------------------------------------------------
# Install the executable to 'bin' directory under CMAKE_INSTALL_PREFIX
#
#install(TARGETS G4ET DESTINATION bin)

#----------------------------------------------------------------------------
# Copy helper tools
#
configure_file(files/reset.sh ./ COPYONLY)
configure_file(files/monitor.sh ./ COPYONLY)
configure_file(files/uniter.py ./ COPYONLY)
#configure_file(files/example.gdml ./ COPYONLY)
#configure_file(files/example.bins ./ COPYONLY)
#configure_file(files/example.py ./ COPYONLY)
#configure_file(files/example.mac ./ COPYONLY)
#configure_file(phantoms/icru_response.txt ./ COPYONLY)
#configure_file(phantoms/icru_counting.txt ./ COPYONLY)
#configure_file(phantoms/ramona_fifteen_0.060MeV_detA_response.txt ./ COPYONLY)
#configure_file(phantoms/ramona_fifteen_0.060MeV_detA_counting.txt ./ COPYONLY)

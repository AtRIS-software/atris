cmake_minimum_required(VERSION 3.22)

project(AtRIS LANGUAGES CXX)

find_package(Geant4 REQUIRED COMPONENTS gdml multithreaded)

get_filename_component(ATRIS_SOURCE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)

# Format Git metadata like setuptools-scm's default Python package version.
function(atris_format_version description output_variable)
  set(formatted_version "unknown")

  if(description MATCHES "^v?([0-9]+)\\.([0-9]+)\\.([0-9]+)-([0-9]+)-g([0-9a-f]+)(-dirty)?$")
    set(version_major "${CMAKE_MATCH_1}")
    set(version_minor "${CMAKE_MATCH_2}")
    set(version_patch "${CMAKE_MATCH_3}")
    set(version_distance "${CMAKE_MATCH_4}")
    set(version_node "${CMAKE_MATCH_5}")
    set(version_dirty "${CMAKE_MATCH_6}")

    if(version_distance EQUAL 0 AND NOT version_dirty)
      set(formatted_version "${version_major}.${version_minor}.${version_patch}")
    else()
      math(EXPR next_patch "${version_patch} + 1")
      string(LENGTH "${version_node}" node_length)
      if(node_length GREATER 9)
        # setuptools-scm limits live Git nodes to nine hash characters.
        string(SUBSTRING "${version_node}" 0 9 short_node)
      else()
        set(short_node "${version_node}")
      endif()
      set(formatted_version
          "${version_major}.${version_minor}.${next_patch}.dev${version_distance}+g${short_node}")
      if(version_dirty)
        string(TIMESTAMP dirty_date "%Y%m%d" UTC)
        string(APPEND formatted_version ".d${dirty_date}")
      endif()
    endif()
  elseif(description MATCHES "^v?([0-9]+\\.[0-9]+\\.[0-9]+)$")
    set(formatted_version "${CMAKE_MATCH_1}")
  endif()

  set(${output_variable} "${formatted_version}" PARENT_SCOPE)
endfunction()

set(ATRIS_GIT_DESCRIPTION "")
if(EXISTS "${ATRIS_SOURCE_ROOT}/.git")
  execute_process(
    COMMAND git describe --dirty --tags --long --abbrev=40 --match "*[0-9]*"
    WORKING_DIRECTORY "${ATRIS_SOURCE_ROOT}"
    OUTPUT_VARIABLE ATRIS_GIT_DESCRIPTION
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
endif()
if(NOT ATRIS_GIT_DESCRIPTION AND EXISTS "${ATRIS_SOURCE_ROOT}/.git_archival.txt")
  file(STRINGS "${ATRIS_SOURCE_ROOT}/.git_archival.txt" ATRIS_ARCHIVE_VERSION
       REGEX "^describe-name: ")
  string(REPLACE "describe-name: " "" ATRIS_GIT_DESCRIPTION "${ATRIS_ARCHIVE_VERSION}")
endif()

atris_format_version("${ATRIS_GIT_DESCRIPTION}" ATRIS_VERSION)
message(STATUS "AtRIS version: ${ATRIS_VERSION}")

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
target_compile_definitions(AtRIS PRIVATE ATRIS_VERSION="${ATRIS_VERSION}")
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

#configure_file(files/example.gdml ./ COPYONLY)
#configure_file(files/example.bins ./ COPYONLY)
#configure_file(files/example.py ./ COPYONLY)
#configure_file(files/example.mac ./ COPYONLY)
#configure_file(phantoms/icru_response.txt ./ COPYONLY)
#configure_file(phantoms/icru_counting.txt ./ COPYONLY)
#configure_file(phantoms/ramona_fifteen_0.060MeV_detA_response.txt ./ COPYONLY)
#configure_file(phantoms/ramona_fifteen_0.060MeV_detA_counting.txt ./ COPYONLY)

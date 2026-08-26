# Tests

AtRIS needs fast tests for its preparation and aggregation tools, plus a small
number of tests that build and run the Geant4 application. Scientific
regression tests should use fixed inputs and seeds and should state explicitly
whether a comparison is exact or tolerance-based.

## Test Data

Tests should use a small committed fixture containing one PSF, its GDML
geometry, one phantom pair, and a short energy grid. Synthetic Geant4 CSV files
should cover parser and aggregation behaviour without requiring AtRIS to run.
Tests should not download an atmosphere or depend on an external service.

Generated files should be written to temporary directories. Large simulation
outputs, build trees, and downloaded responses should not be committed as test
data.

## Fast Python Tests

These tests should run without Geant4 and should be suitable for every local
change.

- Generate exactly the requested number of proton and alpha chunk entries.
- Generate unique, six-digit seed pairs and reproduce the same plan when the
  macro generator receives the same random seed.
- Leave chunked shared macros free of `/random/setSeeds` while retaining seeds
  in ordinary single-run macros.
- Preserve the requested event count in both chunked and ordinary macros.
- Create an empty `chunks/` directory and refuse to overwrite an existing
  `chunks.txt` or a nonempty `chunks/` directory.
- Verify that destination refusal happens before existing macros are changed.
- Accept an existing empty `chunks/` directory.
- Parse valid `chunks.txt` entries and reject malformed lines with the correct
  line number.
- Select only entries that have a matching `COMPLETE` marker.
- Ignore unfinished chunks even when they contain partial CSV output.
- Gather one completed chunk into the canonical proton or alpha filenames.
- Gather several chunks by adding every numeric histogram accumulator column.
- Add `#planes_Sxyw` values while requiring all other histogram metadata and
  column names to match.
- Reject missing histograms, incompatible headers, and incompatible histogram
  shapes without replacing the affected canonical file.
- Gather only the species named on the command line.
- Produce no canonical output when no chunk of that species is complete.
- Produce byte-identical canonical CSV files when the same completed set is
  gathered twice.
- Confirm that adding another completed chunk replaces the canonical files
  with the new cumulative aggregate.
- Post-process gathered CSV files without requiring `protons.log` or
  `alphas.log`.

## AtRIS Integration Tests

These tests require a built AtRIS executable and a working Geant4 runtime. They
should use one worker and very few primary particles.

- Run the original unchunked invocation and confirm that it still reads and
  writes the ordinary simulation prefix.
- Run a six-digit seeded output prefix such as
  `chunks/protons_123456_654321` and confirm that AtRIS reads `protons.gdml`,
  `protons.mac`, and `protons.bins` from the run root.
- Confirm that the two suffix seeds are reported and that all histogram files
  are written under the seeded chunk prefix.
- Confirm that a name without two six-digit suffixes retains the original
  prefix behaviour.
- Confirm that a failed Geant4 macro command produces a nonzero AtRIS exit
  status.
- Compare macro-supplied and suffix-supplied runs using the same seeds, inputs,
  and worker count to determine whether their raw histograms are exactly
  reproducible.

## Slurm Wrapper Tests

The Slurm wrappers can be tested locally with scheduler variables and a stub
AtRIS executable; most cases do not require Slurm itself.

- Treat `run-atris.slurm.sh` as the default Slurm workflow.
- Run every unfinished plan entry sequentially when the default wrapper is
  invoked directly with Bash and no line number.
- Run only the requested one-based plan entry when Bash receives a line number.
- Map each one-based array index to the corresponding `chunks.txt` line.
- Pass the expected physics list, seeded output prefix, mode, and phantom count
  to AtRIS.
- Create `COMPLETE` only after a successful AtRIS exit.
- Leave no completion marker after a nonzero exit or termination.
- Skip a chunk that already has a completion marker.
- Fail when the array index has no corresponding plan entry.
- Set `G4FORCENUMBEROFTHREADS` from `SLURM_CPUS_PER_TASK`.
- Confirm that the singleton wrapper runs the ordinary proton and alpha
  prefixes sequentially under Slurm or Bash and stops if either invocation
  fails.

## End-To-End Tests

These tests exercise the supported workflow and may take longer.

- Generate a small two-species chunk plan, run every chunk, gather it, and run
  the unchanged postprocessor.
- Verify the exact raw sum of every gathered proton and alpha CSV against its
  source chunks.
- Verify the expected primary count after partial and complete gathering.
- Verify nonempty ionization, dose, dose-equivalent, count-rate, and PDF output
  for both species.
- Interrupt or fail one chunk, gather the completed subset, rerun the missing
  chunk, and verify that the final aggregate includes it once.
- Install the Python package in a clean environment and run each documented
  command-line entry point.
- Verify that each legacy command and its unified `atris` subcommand reach the
  same implementation and accept the same arguments.
- Verify top-level and per-command help for the unified `atris` interface.
- Follow `INSTALL.md` and `README.md` from a clean workspace as a release
  acceptance test.
- Submit a small array on a supported HPC system as a manual release test.

## Scientific Regression Tests

Scientific baselines should be added only after the fixture inputs and expected
behaviour have been reviewed. Exact comparisons are appropriate for parsers,
file conversion, and aggregation. Floating-point simulation and processed
results may require documented tolerances across supported compilers and
Geant4 versions.

- Compare PSF conversion against a reviewed fixed PSF fixture.
- Compare generated GDML structure and material values against a reviewed
  fixture without depending on irrelevant formatting.
- Protect macro energy bins, particle counts, source radius, and particle
  definitions against unintended changes.
- Compare selected raw and post-processed response values against reviewed
  baselines.
- Verify that chunk aggregation gives the same estimator as processing the
  equivalent combined raw accumulators.
- Record compiler, Geant4 version, worker count, inputs, and seeds alongside
  every simulation baseline.

Monte Carlo noise should not be tested by requiring every cumulative sequence
to improve monotonically. A separate characterization test can compare many
independent chunk subsets and report whether disagreement decreases roughly as
the inverse square root of the number of primaries. That report is evidence
about convergence, not a deterministic pass/fail regression test.

## Suggested Test Tiers

- Run fast Python tests on every change.
- Run AtRIS integration and the minimal end-to-end workflow when Geant4 is
  available.
- Run scientific regression tests before release or after changes to geometry,
  physics configuration, random-number handling, histogram production, or
  post-processing.
- Run the HPC array test manually before an HPC-facing release.

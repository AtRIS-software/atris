# Development

Version 3.0 added scatter-gather support and placed the existing Python scripts
in a small package. Structural work should not change scientific or numerical
behaviour unless that change is explicitly documented and validated.

## C++ conventions

AtRIS aims to follow Geant4's [example coding guidelines][g4-example-style] and
[modern C++ guidance][g4-modern-cpp] so that its C++ code is familiar to Geant4
users and contributors. New and modified code should use `UpperCamelCase`
member functions, `fUpperCamelCase` data members, `lowerCamelCase` local
variables and arguments, and `kUpperCamelCase` named compile-time constants.
Use `constexpr` for values known at compile time and `const` for other values
that do not change.

Existing code should be brought into line incrementally when related work is
already changing it. Non-obvious numerical boundaries and scientific constants
must be given descriptive names or explained where they are used; their meaning
should not have to be inferred from a value such as a PDG particle code.

[g4-example-style]: https://geant4.web.cern.ch/collaboration/working_groups/novextExamples/codingGuidelines.v2.2.html
[g4-modern-cpp]: https://geant4.web.cern.ch/assets/c11_guidelines.pdf

## Remaining goals

The remaining goals are:

- Reduce duplicated files and make the role of each retained dataset explicit.
- Provide small, reproducible system tests for installation and complete
  workflows.
- Protect existing scientific behaviour with numerical regression tests.

## Phantom data

The `phantoms/` library still contains historical response tables, variance
tables, plots, and other data whose provenance and continuing role need to be
established before removal. Preserve the source data while resolving that
history. The [phantom library reference](reference/phantom-library.md) contains
the available examples, historical notes, and original exploration notebook.

## Future development: propagate phantom uncertainty

AtRIS should propagate the sampling uncertainty of a calibrated phantom through
an atmospheric response calculation without storing individual calibration
events or interface crossings. This is distinct from uncertainty in Geant4's
physics models, the atmosphere, or a later physical source spectrum. Transport
sampling uncertainty and phantom-calibration uncertainty should remain separate
quantities so that their origins are clear.

### Retain compact calibration statistics

Phantom-calibration mode already accumulates the quantities needed for one
scoring volume and particle-energy cell: the primary count $N$, the sum $S$ of
deposited-energy fractions, the squared sum $Q$, and the detected-primary count
$K$. These give the mean response, its sampling variance and standard error,
and the counting efficiency with its sampling uncertainty. Keep these
mergeable accumulators rather than individual events or a covariance value
calculated before all chunks have been gathered.

A calibration with several scoring volumes may also retain the cross-product

$$
Q_{ab}=\sum_i x_{i,a}x_{i,b}
$$

for each required pair of volumes $a$ and $b$. Together with $N$, $S_a$, and
$S_b$, this gives the sample covariance after gathering. Store only one
triangle because $Q_{ab}=Q_{ba}$, and create cross-products only for explicitly
related detector channels. This avoids quadratic growth for geometries whose
volumes do not need a joint uncertainty estimate.

Use ROOT as the compact scientific record for the calibration axes, particle
codes, accumulators, metadata, and optional cross-products. Do not add separate
NPZ and JSON representations of the same result. Until the C++ phantom loader
is deliberately replaced, retain the existing `_response.txt` and
`_counting.txt` matrices as the small backward-compatible runtime inputs. They
can be generated from the calibrated result; the ROOT record retains the
statistics needed for later analysis. The runtime matrix sizes therefore do
not grow when uncertainty information is added.

### Resolve zero-deposit calibration bins

Model a phantom response as $R=IY$, where $I$ records whether a primary made a
positive ionizing-energy deposit and $Y$ is the deposited fraction conditional
on a positive deposit. Then $E[R]=P(I=1)E[Y]$. This two-part formulation avoids
interpreting an all-zero sample as having zero uncertainty. Use an exact
binomial upper confidence limit for $P(I=1)$ and a physical upper bound on $Y$
defined separately for each particle species, energy bin, phantom material,
and geometry.

When the resulting upper bound on $E[R]$ is below the configured absolute dose
tolerance, the builder may retain zero as the point estimate, record the upper
limit, and consider the bin sufficiently constrained. Otherwise it should keep
sampling. The existing primary count, positive-deposit count, and deposited-
fraction moments are sufficient, so this change belongs in the Python builder
and calibration analysis. Propagating the recorded limit through an ordinary
AtRIS simulation is separate later work.

### Accelerate small-phantom calibration

Thin phantoms give neutral particles such as photons and neutrons a small
probability of interacting. An analogue simulation therefore spends most of
its histories recording zero response, while a few interactions dominate the
estimated mean. Evaluate Geant4's generic force-collision biasing for these
calibrations. The [Geant4 biasing framework][g4-biasing] provides
`G4BOptrForceCollision`, which splits a track entering a selected volume
into a correctly weighted uncollided branch and a branch forced to interact;
`G4BOptnForceCommonTruncatedExp` samples the forced interaction before the
particle exits. Geant4's `GB02` extended example provides the reference
implementation.

The phantom-calibration scorer must treat each original primary as one weighted
sample. Its energy-response sample is the sum of statistically weighted energy
deposits from the biased branches and their descendants. Its counting sample is
the statistical weight of the branch satisfying the counting criterion, not
an unweighted test of whether any deposit occurred. The event-level first and
second moments must contain these complete weighted samples. Merely attaching
the biasing operator while leaving the current scorer unchanged would produce
biased response tables.

Keep analogue calibration available while developing this path. Validate each
biased particle type against an analogue calibration in a geometry and energy
range where both obtain adequate statistics. Compare response and counting
means within their estimated uncertainties, then benchmark uncertainty per CPU
time for a representative micrometre-scale phantom. Start with photons and
neutrons; do not assume that forcing a discrete collision benefits charged
particles, which also lose energy continuously.

[g4-biasing]: https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Fundamentals/biasing.html

### Retain response sensitivities

The normal response output currently contains the final sum after a phantom
coefficient has been applied. That sum does not reveal how strongly each
particle-energy cell of the phantom table contributed. Add an optional sparse
sensitivity product indexed by primary-energy bin, atmospheric interface,
secondary-particle code, and secondary-energy bin. Each occupied row needs
three mergeable accumulators:

- the number of crossings, which multiplies the counting coefficient;
- the sum of crossing kinetic energies, which multiplies the energy-response
  coefficient; and
- the sum of radiation-weighted crossing kinetic energies, which multiplies
  the same coefficient for the equivalent-response result.

These transport sensitivities are common to compatible phantoms and should not
be duplicated once per selected phantom. Store them as a sparse ROOT object,
not as per-crossing or per-event records. Measure their size and runtime cost
on a representative atmospheric run before deciding whether they should be
enabled by default.

For an output bin with response-table coefficients $r_j$ and accumulated
sensitivities $W_j$, the phantom contribution is

$$
Y=\sum_j W_jr_j.
$$

With a coefficient covariance matrix $C$, its calibration variance is

$$
\operatorname{Var}(Y)=\boldsymbol{W}^{\mathsf T}C\boldsymbol{W}.
$$

When only the individual coefficient variances are available, the tools may
calculate the diagonal approximation $\sum_j W_j^2\operatorname{Var}(r_j)$,
but must identify the omitted covariance rather than silently treating it as
known to be zero. The same calculation applies to counting and
radiation-weighted responses using their corresponding sensitivities.

Gather sensitivities by adding their raw accumulators across chunks before
calculating a variance. The same uncertain phantom coefficient is reused in
every chunk, so calculating a variance independently in each chunk and adding
those variances would omit cross terms. A gathered response may still be
produced from old or mixed chunks, but propagated phantom uncertainty is
available only when the complete gathered set has compatible sensitivity data.

### Retain transport sampling moments

Phantom-table uncertainty is not the Monte Carlo uncertainty of the atmospheric
transport. The current response histograms are filled at particle crossings,
and their `Sw2` values treat those correlated crossings as separate fills. To
estimate transport sampling uncertainty, accumulate each primary history's
total contribution to each output bin and retain its first and second moments.
These fixed-size moments can be gathered by addition and used independently of
the phantom-calibration covariance.

Keep the established response histogram names and numerical meanings unchanged.
Add new uncertainty products under versioned names and record the schema in
their ROOT metadata. Existing phantom tables and response files must remain
readable; when the additional statistics are absent, the tools should report
that the corresponding uncertainty is unavailable rather than infer it from
crossing-level `Sw2` values.

## Simulation preparation interface

Physics-list and output-mode choices currently reach the simulation through
`atris-run` arguments. This splits the simulation definition between preparation
and launch, leaving users to repeat those choices when starting or resuming a
job.

A future revision should move these choices into the input-generation step,
save them with the prepared inputs, and have the runner read them from there.
Thread counts, worker assignments, and scheduler limits would remain execution
settings.

The name `atris-generate-macros` also needs reconsideration. The command already
prepares geometry copies and energy bins as well as macros, and would then
define more of the simulation configuration. Its name should describe preparing
simulation inputs rather than generating one particular file format. The
replacement name and configuration format are still to be decided.

## Future development: adaptive energy-range chunks

The current chunk plan repeats the same source-energy distribution with new
random seeds. All chunks of a species share one chunk macro and identical
histogram axes. This is useful for restarts and parallel execution, but it
cannot direct additional simulation effort towards the energy intervals where
another primary history would reduce the final uncertainty most.

A future chunk format should treat completed chunks as additive building
blocks of one canonical response matrix. The run would retain complete proton
and alpha energy grids, while each chunk could select a contiguous subset of
those bins and its own event count. The selection changes where computation is
spent; it does not change the definition of the final response.

The plan should store canonical bin indices rather than independent
floating-point limits. For example, a versioned plan entry could contain the
particle species, two random seeds, an inclusive first-bin index, an exclusive
stop-bin index, and an event count. User-facing energy limits would be resolved
to exact edges of the canonical grid when the entry is created. This prevents
nearly equal edges, incompatible bin widths, and proton/alpha energy-scaling
conventions from making apparently compatible chunks impossible to combine.
Legacy three-field plan entries could continue to mean a full-range chunk
using the existing shared chunk macro.

### Chunk execution

Each ranged chunk should run in an isolated temporary working directory. The
runner would stage links to the fixed geometry and phantom inputs, write a
local slice of the species `.bins` file, and generate a local chunk macro with
the requested energy range and event count. Output would still be written to
the run's central `chunks/` directory. Private working directories prevent
concurrent workers from replacing one another's macros or energy grids.

This arrangement can initially use the existing C++ input-prefix behaviour;
the orchestration changes can remain in the Python tools. Local energy axes
also avoid writing the full energy-by-detector matrix for a chunk that samples
only a small part of it.

### Range-aware gathering

`atris-gather` would use the run-level `.bins` file as the canonical output
axis. For every completed chunk it would:

1. verify that the local energy edges are an exact contiguous slice of the
   canonical grid;
2. map the local primary counts and raw response sums into the corresponding
   canonical rows; and
3. add those raw accumulators before any response normalization.

Overlapping chunks would improve the statistics of the same energy bins, and
disjoint chunks would fill different parts of the response matrix. Bins with
no primary histories must remain explicitly unsampled, normally represented
as `NaN` after post-processing rather than as zero response. Local energy
underflow or overflow entries would make the mapping ambiguous and should
therefore cause gathering to fail.

Histograms without a primary-energy axis, such as source direction and source
position, can continue to be added directly. Both CSV and ROOT gathering
should follow the same mapping and validation rules.

Only sampling properties represented by an output dimension can safely vary
between additive chunks. Energy range, event count, sampling weight between
energy bins, and random seeds may differ because actual primary counts are
retained for every energy bin. Geometry, materials, physics list, phantom
definitions, detector layout, and canonical bin boundaries must remain fixed.
Changing the source direction or position distribution would not be safe with
the present response products because those dimensions are averaged out rather
than retained in the response matrix.

### Choosing valuable follow-up chunks

Range-aware chunks provide the mechanism for adaptive simulation but do not by
themselves decide where to spend more computation. An initial pilot should
include at least two independent contributions to every energy bin so that the
tools can estimate variation between chunks. For each energy bin, the planning
tools could then report:

- accumulated primary histories;
- response uncertainty estimated from independent chunk means;
- measured computation time per primary; and
- contribution to uncertainty after convolution with one or more supplied
  physical spectra.

A follow-up priority can be defined as the predicted reduction in the selected
final uncertainty divided by the predicted additional runtime. The supplied
physical spectra would influence only the allocation of future histories; they
would not be folded into or otherwise specialize the gathered response matrix.
Konstantin's later convolution with measured spectra would therefore remain
possible.

The planner must retain a minimum exploration allocation. A sparse energy bin
that has not yet produced an interaction is not evidence that its true response
is zero. Adjacent high-priority bins can be grouped into one practical chunk so
that Geant4 initialization time does not dominate many tiny simulations. The
existing per-run timing output can provide the setup and transport measurements
needed for this decision.

Development should proceed in stages: first add manual ranged chunks and a
backward-compatible plan parser; then implement and test range-aware gathering;
then expose per-energy convergence and cost diagnostics; and only then add a
tool that recommends or appends the next highest-value chunks. Numerical tests
should cover overlapping ranges, disjoint ranges, unsampled gaps, incompatible
edges, and equivalence between a full-range aggregate and the same raw
histories divided among ranged chunks.

## Simulation output

The simulation filename selects Geant4's analysis backend; CSV is the default
when no extension is supplied. Mode 0 adds the `interfaces` ntuple and mode 1
also adds the `steps` ntuple. With ROOT selected, Geant4 stores these products
and the histograms in one file and merges worker-thread objects. The
interface columns contain particle, interface, angle, crossing-energy, and
primary-energy values. The step columns contain event and track identifiers,
particle and detector identifiers, pre- and post-step positions and energies,
energy deposition, step length, time, primary energy, and process names. The
Python tools read this output with Uproot and process the larger step table in
bounded chunks.

Some modules still retain names and implementation details from the original
standalone scripts. Further cleanup should favor clear importable functions and
small command-line entry points without changing the supported workflow.

## Thread scaling

Do not assume that AtRIS becomes faster whenever more worker threads are added.
The imported README (commit `112e4dc`) says that scaling eventually stops
because of CPU cache topology. It does not give the limiting core count. The
accompanying `simstarter.ipynb` uses 16 worker threads. That is a historical
example, not a benchmark for current hardware.

The thread count applies to each AtRIS process. Therefore, an HPC chunk using
16 worker threads requires 16 cores, and concurrent chunks require separate
sets of cores. Benchmark representative chunks at several thread counts before
deciding how many cores to allocate to each chunk. Guidance for chunk sizing, scheduler worker
pools, and resource measurement is in
[Running AtRIS on an HPC system](hpc.md).

## Remaining tests

Temporary end-to-end harnesses are not part of the supported Python interface.
Useful harnesses should be converted into reproducible smoke or system tests;
those that do not provide lasting test coverage should be removed.

The current tests cover the Python tools and short runs of the compiled AtRIS
executable. The main remaining gaps are a complete preparation-to-post-processing
system test, behavioral tests for the Slurm wrappers, and reviewed numerical
regression baselines for scientific output.

See [Minimal test fixture](reference/minimal-test-fixture.md) for the fixture
layout and the limits of its validation.

The [Earth tutorials](tutorials/earth-nrlmsis-full.md) exercise preparation,
execution, and processing with a few chunks. They provide a worked workflow;
numerical regression tests remain separate work.

# Development

Version 3.0 added scatter-gather support and placed the existing Python scripts
in a small package. Structural work should not change scientific or numerical
behaviour unless that change is explicitly documented and validated.

## Release plan

The boundary between 3.x and 4.0 is backward compatibility, not the amount of
work in a release. Development belongs in 3.x when existing run directories,
commands, input files, output products, and numerical definitions continue to
work. Version 4.0 is reserved for changes that require users or downstream
tools to migrate. Breaking an interface solely to make the implementation
cleaner is not a reason to begin 4.0.

A central scientific-computing goal is adaptive sampling based on error
minimisation. AtRIS should measure uncertainty and computation cost, then direct
new primary histories to the species and energy ranges where they are expected
to reduce the selected result uncertainty most efficiently. Adaptation must
preserve unbiased estimators, mergeable outputs, and enough exploration to
avoid treating an unsampled or rarely interacting region as a known zero.

### Version 3.x

The 3.x line should consolidate and test the workflow on `main` while
preserving its current interfaces. Its planned work is:

- establish the provenance and role of the retained phantom data;
- report the minimal uncertainty estimates supported by the current phantom
  calibration statistics and clearly identify unresolved bins;
- experiment with bounds for sparse phantom responses and variance reduction
  for thin phantoms without making either a supported 3.x calibration mode;
- add backward-compatible ranged chunks and convergence diagnostics in stages;
- improve installation, workflow, and numerical regression tests; and
- continue local C++ and Python cleanup where it does not alter supported
  interfaces or scientific results.

The current positional executable interface, numbered runtime phantom files,
`phantoms.txt` schema, source sampling, and established output products remain
the 3.x compatibility baseline. New metadata or diagnostics may be added when
old files and commands remain valid. The 3.x phantom builder should provide
minimal per-bin uncertainty estimates from its existing sampling moments and
must identify statistically unresolved all-zero bins rather than report zero
error. A supported error bound for sparse bins, forced-interaction calibration,
and propagation of phantom uncertainty through an ordinary atmospheric response
calculation are deferred to 4.0. Experiments supporting those features may be
performed during 3.x development.

### Version 4.0

The `run-configuration` branch contains an alternative configuration and
output design. It must remain separate from `main` until a 4.0 integration is
started. The branch is development material rather than a release candidate;
before use it must be reconciled with all later 3.x work on `main`.

AtRIS 4.0 should be controlled by the `.mac` command stream. The selected
macro, together with the scientific files it names, should be a complete and
persistent description of the simulation. Positional executable arguments,
filename stems, and directory contents should not act as additional hidden
configuration channels. Python tools may prepare, compose, and validate macros,
while the executable consumes the resulting Geant4 command stream.

Use existing Geant4 macro commands wherever they express the required setting.
This includes the established `/control/`, `/run/`, `/gps/`, `/random/`, and
available `/analysis/` command families. Add an `/atris/` command only for an
AtRIS-specific concept that Geant4 does not already expose. Do not wrap a
standard Geant4 command merely to give it an AtRIS spelling.

The 4.0 work should also remove arbitrary restrictions inherited from the
original implementation. In particular, particle species, input basenames,
macro filenames, output names, and phantom response channels should not be
fixed where Geant4 or the scientific model permits a general value. Physical
constraints and format invariants should remain explicit and validated; the
goal is to remove historical coupling, not useful checks.

No legacy phantom tables, plots, variance files, or historical notebook outputs
should be included in the 4.0 distribution. If they remain useful for
reproducibility or comparison, they may be published as a separately versioned
archive with their provenance and applicable AtRIS versions. The 4.0 phantom
library should contain only the new, clearly named and validated reference
families.

No other legacy feature should enter 4.0 by default. Before inclusion, evaluate
its scientific purpose, present use, overlap with the macro-controlled design,
data-model and output implications, and available regression coverage. Record
one decision for each inherited command, alias, file format, naming convention,
and behavior: retain, redesign, distribute separately, or remove. Compatibility
with 3.x is evidence to consider, not by itself a reason to preserve a feature.

The intentionally incompatible parts of the design are therefore:

- replacing `AtRIS <physics-list> <simulation-name> <mode> <phantom-count>`
  with `AtRIS <macro-file>`;
- making self-contained Geant4 macros authoritative for geometry, energy bins,
  output destination, physics list, output mode and format, random seeds,
  source settings, and phantom response tables;
- replacing inferred, numbered phantom inputs with named response channels and
  explicit response factors, and changing `phantoms.txt` accordingly;
- defining output products once in the AtRIS output layer and writing either
  CSV or ROOT through Geant4's analysis manager, with a common logical schema
  and metadata;
- changing primary-energy sampling from the 3.x finite-bin procedure to a
  continuous log-uniform source;
- introducing supported sparse-bin error bounds and forced-interaction
  calibration for thin phantoms;
- supplying clearly named water and ICRU phantom families at several physical
  sizes;
- making error-minimising adaptive sampling a supported workflow, using
  measured uncertainty and runtime rather than fixed event allocations; and
- adding versioned products for full phantom-calibration and transport
  uncertainty propagation.

The branch also contains useful internal work: focused run-configuration and
phantom-response classes, the `AnalysisOutput` split, clearer initialization
and failure handling, common metadata writers, and additional regression
examples. These changes support the 4.0 design but do not independently require
a major version. They should be reviewed and carried forward only with the
interfaces they serve, rather than merged piecemeal into 3.x.

### Version 4.0 migration gate

Before 4.0 is merged, the incompatible contracts must be defined together and
tested as one workflow. At minimum, the release needs:

- a migration guide from the positional executable call and 3.x macros to the
  macro-only interface;
- an audit of every custom macro command, replacing it with the corresponding
  standard Geant4 command where one exists and documenting why each remaining
  `/atris/` command is project-specific;
- a documented conversion from numbered phantom inputs and the 3.x
  `phantoms.txt` format to named response channels;
- an inventory of legacy features and data with an explicit retain, redesign,
  separate-distribution, or removal decision for each item;
- versioned CSV and ROOT schemas, with readers for supported 3.x results where
  practical and explicit errors where conversion would lose information;
- numerical comparisons that isolate the effect of continuous log-uniform
  source sampling from unrelated code changes;
- validated water and ICRU phantom families at several sizes, including
  analogue comparisons for the forced-interaction results;
- numerical tests showing that adaptive allocations remain unbiased and reduce
  the selected uncertainty more efficiently than the comparison fixed
  allocation;
- scatter, run, gather, post-process, and plot tests using the new macros and
  both output backends; and
- updated tutorials and reference pages delivered with the implementation,
  rather than describing either interface as current before the code changes.

The branch should be integrated only after these migration requirements and
the retained 3.x behavior have regression coverage. There is no requirement to
start 4.0 merely because the branch exists.

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

## Phantom data in 3.x

The `phantoms/` library still contains historical response tables, variance
tables, plots, and other data whose provenance and continuing role need to be
established before removal. Preserve the source data while resolving that
history. The [phantom library reference](reference/phantom-library.md) contains
the available examples, historical notes, and original exploration notebook.
This preservation policy applies to the 3.x repository. It does not place the
legacy phantom library in the 4.0 distribution.

## Phantom calibration uncertainty (3.x)

Phantom calibration should retain enough information to give each response bin
a minimal sampling-uncertainty estimate without storing individual calibration
events. Bins with observed deposits can use their existing first and second
moments. All-zero bins must remain explicitly unresolved rather than receive a
reported standard error of zero. These estimates describe the phantom
calibration only; 3.x does not use them as a stopping bound or propagate them
through an ordinary atmospheric response run.

Experiments during 3.x may evaluate sparse-response bounds and forced
interactions. Their outputs must be identified as experimental and must not
silently replace analogue calibration products used by the supported workflow.

### Retain compact calibration statistics

Phantom-calibration mode already accumulates the quantities needed for one
scoring volume and particle-energy cell: the primary count $N$, the sum $S$ of
deposited-energy fractions, the squared sum $Q$, and the detected-primary count
$K$. These give the mean response, its sampling variance and standard error,
and the counting efficiency with its sampling uncertainty. Keep these
mergeable accumulators rather than individual events or a covariance value
calculated before all chunks have been gathered.

Use ROOT as the compact scientific record for the calibration axes, particle
codes, $N$, $S$, $Q$, $K$, and metadata. Do not add separate NPZ and JSON
representations of the same result. Until the C++ phantom loader is deliberately
replaced, retain the existing `_response.txt` and `_counting.txt` matrices as
the small backward-compatible runtime inputs. They can be generated from the
calibrated result; the ROOT record retains the statistics needed for later
analysis. The runtime matrix sizes therefore do not grow when uncertainty
information is added.

## Phantom calibration methods (4.0)

### Define sparse-response error bounds

Model a phantom response as $R=IY$, where $I$ records whether a primary made a
positive ionizing-energy deposit and $Y$ is the deposited fraction conditional
on a positive deposit. Then $E[R]=P(I=1)E[Y]$. This two-part formulation avoids
interpreting an all-zero sample as having zero uncertainty.

The supported 4.0 convergence criterion should use the positive-deposit count
$K$ and squared-deposit accumulator $Q$, together with $N$ and $S$ where needed
for normalization. The method must define its confidence level, assumptions,
and behavior when $K=Q=0$. In particular, an all-zero sample cannot acquire a
zero error merely because no response has yet been observed. Any physical cap
or distributional assumption needed to obtain a finite upper bound must be
recorded with the calibration result.

When the resulting bound is below the configured absolute dose tolerance, the
builder may retain zero as the point estimate, record the bound, and consider
the bin sufficiently constrained. Otherwise it should keep sampling. The bound
must remain mergeable across chunks and be reproducible from the retained
calibration statistics.

### Force interactions in thin phantoms

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

### Supply reference phantom families

The supported calibration feature should include clearly named water and ICRU
phantom families at several physical sizes. Names should state the material,
geometry, size, and unit rather than rely on an ordinal or an unexplained label.
Each entry should record its dimensions, composition, density, mass,
cross-sectional area, production cut, physics list, calibration method, and
uncertainty statistics.

The size range should include phantoms thick enough for direct analogue
validation and thin phantoms that exercise the sparse-response bound and
forced-interaction path. For every size where forced interactions are used,
compare the result with an analogue calculation in a range where both methods
obtain adequate statistics. Ship the ROOT calibration record and the compact
runtime response tables under the same unambiguous phantom stem.

## Propagate phantom uncertainty (4.0)

AtRIS 4.0 may propagate phantom-calibration uncertainty through an atmospheric
response calculation without storing individual calibration events or interface
crossings. This is distinct from uncertainty in Geant4's physics models, the
atmosphere, or a later physical source spectrum. Transport sampling uncertainty
and phantom-calibration uncertainty should remain separate quantities so that
their origins are clear.

### Retain calibration covariance

A calibration with several scoring volumes may retain the cross-product

$$
Q_{ab}=\sum_i x_{i,a}x_{i,b}
$$

for each required pair of volumes $a$ and $b$. Together with $N$, $S_a$, and
$S_b$, this gives the sample covariance after gathering. Store only one
triangle because $Q_{ab}=Q_{ba}$, and create cross-products only for explicitly
related detector channels. This avoids quadratic growth for geometries whose
volumes do not need a joint uncertainty estimate.

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
their ROOT metadata. Whether 4.0 directly reads a 3.x phantom or response file
is decided by the legacy-feature review rather than assumed. If a supported
conversion cannot preserve the required information, keep the old data and its
reader in the separate 3.x archive instead of weakening the 4.0 schema.

## Simulation preparation interface (4.0)

On `main`, physics-list and output-mode choices reach the simulation through
`atris-run` arguments. This splits the simulation definition between preparation
and launch, leaving users to repeat those choices when starting or resuming a
job. This remains the supported 3.x interface.

The `run-configuration` branch moves these choices into self-contained species
macros and changes the executable to accept one macro-file argument. Geometry,
energy bins, output naming and format, random seeds, source settings, and
phantom response channels are also explicit macro commands. Thread counts,
worker assignments, deadlines, and scheduler limits remain execution settings.
Because adopting this design replaces the executable and prepared-input
contracts, it is deferred to 4.0.

The macro should be authoritative rather than one of several equivalent ways
to configure a run. It may use `/control/execute` to compose other macros, but
AtRIS should not require a particular filename or include hierarchy. The
Python tools may generate wrapper, species, or chunk macros for convenience;
those files should resolve to the same command stream that the executable
receives.

The generated macros should use Geant4's own commands directly for source
particles and distributions, initialization and event processing, random
seeds, threading, macro composition, and analysis settings wherever the linked
Geant4 version provides them. Custom AtRIS commands should be limited to
AtRIS-owned data and calculations, such as its energy-bin input, response
channels, and output products when no equivalent Geant4 command exists. This
keeps the C++ control layer small and lets an experienced Geant4 user understand
and modify a prepared run using familiar commands.

Historical restrictions should be removed as this interface is introduced.
The executable should not infer related files from one simulation prefix,
restrict ordinary runs to proton and alpha naming conventions, require
numbered phantom aliases, or assume exactly two kinds of phantom response.
Inputs and response calculations should instead be named explicitly in the
macro. Similar restrictions should be retained only when they express a real
Geant4, file-format, or scientific invariant.

The name `atris-generate-macros` also needs reconsideration. The command already
prepares geometry copies and energy bins as well as macros, and would then
define more of the simulation configuration. Its name should describe preparing
simulation inputs rather than generating one particular file format. The
replacement name and configuration format are still to be decided.

## Adaptive sampling by error minimisation

Backward-compatible ranged chunks and convergence diagnostics may be developed
in 3.x. They provide the mechanism and measurements needed for later adaptive
sampling. A supported planner that automatically allocates additional work is
a 4.0 feature because it depends on a defined uncertainty model, persistent
macro-controlled inputs, and versioned statistical output.

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

### Choose follow-up chunks by error reduction

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

A follow-up priority should be the predicted reduction in the selected final
uncertainty divided by the predicted additional runtime. This is an
error-minimisation policy, not merely a rule that adds histories to bins with
few samples. The supplied physical spectra would influence only the allocation
of future histories; they would not be folded into or otherwise specialize the
gathered response matrix. Konstantin's later convolution with measured spectra
would therefore remain possible.

Use an established adaptive-stratified-sampling rule, such as a cost-aware,
batched form of MC-UCB, rather than designing a new allocation algorithm. Keep
the rule as a small policy that receives per-range statistics and returns the
range or ranges for the next chunks. Chunk creation, execution, gathering, and
recording adaptive decisions remain responsibilities of the existing tools.
Neighbour-informed initialization may be an optional policy, but must not be
required by the core allocator or replace direct samples in the final response.
Avoid adding a general adaptive-sampling framework when the published
allocation rule and an AtRIS-specific adapter are sufficient.

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

## Simulation output interface (4.0)

AtRIS should own one format-independent definition of its histograms, ntuples,
axes, units, uncertainty fields, and run metadata. Its output class should book
and fill those products through Geant4's analysis manager. The `.mac` file
selects `csv` or `root`; the backend determines whether the products appear as
several CSV files or objects in one ROOT file. Filename extensions should
reflect that selection, not provide a second way to configure it.

CSV and ROOT should contain the same logical scientific products and metadata
where their Geant4 representations permit it. AtRIS should not maintain a
hand-written scientific writer for one format and a separate Geant4 writer for
the other. Format-specific code belongs at the I/O boundary. Python readers
should convert both representations into the same histogram and table data
models before gathering, post-processing, or plotting.

Output modes may still select how much data is recorded, such as aggregate
responses, interface crossings, or transport steps. They should select products
within the common writer rather than select unrelated writing implementations.
Tests must compare CSV and ROOT at the level of axes, units, metadata, entries,
and numerical accumulators, allowing only documented backend representation
differences.

## Current simulation output (3.x)

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

# Known bugs

This page records unresolved defects, possible bugs awaiting confirmation,
and corrections that affect existing simulation results.

## Mixed units in phantom response tables

The supplied radiation tables show evidence of two quantities. Older
`*_old_response.txt` files and the biological (`bact`, `cell`, `sbug`) tables
store dimensionless energy fractions. Later ICRU tables store
deposited energy in MeV. The
[phantom library reference](reference/phantom-library.md#moved-deposited-energy-tables)
describes these tables and their conversion to energy fractions.
The files did not declare this distinction.

The C++ reader passes both quantities directly to the scorer, which
multiplies them by the crossing particle's kinetic energy in eV. That is
appropriate for a fraction, but applies an extra energy factor to a value
already representing deposited energy. The resulting error depends on the
crossing particle's energy; it is not a single scale factor for the whole run.

See the [response-table format](reference/inputs.md#phantom-response-matrices).

This mismatch affects `h2.dosN`, `h2.equiN`, and their processed dose and
radiation-weighted results. Gathering or post-processing them again cannot
correct it: recalculating these
responses requires rerunning transport. Counting responses, particle transport,
and atmospheric energy-deposit histograms are unaffected.

Energy-fraction tables are kept in `phantoms/`; deposited-energy tables are
kept separately in `phantoms/MeV-valued/`. The
[phantom reference](reference/phantom-library.md#moved-deposited-energy-tables)
lists the moved families and their required column-by-column conversion.

### Differences between old and new phantom tables

The older and newer ICRU tables predict different deposited energies even
when compared in the same units. Their generation settings have not been
recovered, so the cause remains unresolved.

The old unshielded ICRU response is also zero below roughly 60 keV for
protons, electrons, and alpha particles despite its `0.000MeV` filename.
The filename threshold therefore does not describe this old response table.

## Possible radiation-weighting bug

The radiation weights in `src/SensitiveDetector.cc` resemble the prescription
in [ICRP Publication 103](https://www.maff.go.jp/e/policies/market/reference/attach/pdf/reference-25.pdf),
Table 2 and Equation 4.3, but differ in three places:

- The low-energy neutron branch starts with `3.5`, whereas the ICRP formula
  starts with `2.5`.
- Each neutron branch squares the energy expression inside the logarithm,
  producing $\ln(x^2)$ rather than $(\ln x)^2$. Here $x$ is the branch's
  dimensionless energy expression: $e$, $2e$, or $0.04e$, with
  $e=E_{\mathrm{kin}}/(1\,\mathrm{MeV})$. These are different functions, not
  equivalent ways of writing the same formula.
- The pion condition applies weight `2` to neutral pions (PDG `111`), not
  charged pions (PDG `211` and `-211`), which are the pions specified by ICRP.

[Banjac et al. (2019), Section 4](https://doi.org/10.1029/2019JA026622),
cites both ICRP 60 and ICRP 103 for the energy-dependent neutron weight, but
does not reproduce the piecewise formula or explain these differences.

If ICRP 103 is the intended prescription, these differences are possible
formula-transcription and particle-selection bugs. The intended prescription
has not yet been confirmed, and the calculation remains unchanged.

The affected outputs are the raw `h2.equiN` histograms, processed `.equiN`
tables, and quantities derived from them. These weighting differences do not
affect Geant4 particle transport, `.doseN`, `.ratesN`, `.ioni`, or `.edep`.
They cannot be corrected in the combined `.equiN` table, which no longer
separates contributions by crossing particle species and energy.
See [radiation-weighted response](background/radiation-quantities.md#radiation-weighted-response)
for the calculation's purpose and [radiation weighting as implemented](reference/outputs.md#radiation-weighting-as-implemented)
for the exact current formula.

## Primary energies are sampled linearly inside logarithmic bins

The generated proton and alpha macros use a Geant4 GPS `User` energy
histogram. AtRIS supplies logarithmically spaced energy edges, gives the first
edge weight zero, and gives every later edge equal weight. Geant4 consequently
assigns equal probability to every interval, so the expected primary count is
flat when measured using those same logarithmic bins.

Within each interval, however, Geant4 obtains the primary energy by linearly
interpolating the inverse cumulative distribution. The energy is therefore
uniform in linear energy rather than in logarithmic energy. At finer resolution
the generated density in log energy rises across each interval and drops at
the next boundary, producing a repeating sawtooth. For 20 bins per decade, an
interval spans a factor of approximately 1.122, so its log-energy sampling
density rises by approximately 12% from its lower to its upper edge.

The primary-count histogram is not biased when it uses the same bins: each bin
still receives the intended equal probability. The defect can instead bias the
response assigned to a bin. With response function $R(E)$ and bin edges $a$
and $b$, the current sampling converges to the linear-energy average

$$
R_{\mathrm{linear}}=\frac{1}{b-a}\int_a^b R(E)\,dE,
$$

rather than the log-energy average

$$
R_{\log}=\frac{1}{\log(b/a)}\int_a^b\frac{R(E)}{E}\,dE.
$$

Dividing accumulated responses by the primary count removes unequal sampling
*between* bins but cannot correct the sampling distribution *within* a bin.
Increasing the number of histories therefore reduces random noise without
removing this bias. The difference should be small for a response that varies
smoothly across the current narrow bins, but it may be more important near a
threshold or another sharp energy dependence.

Continuous log-uniform sampling can be obtained from the GPS power-law energy
distribution with index -1 between the requested minimum and maximum energies.
That would allow Geant4 to sample freely in log energy before AtRIS assigns the
generated energy to an output bin. Changing the sampling rule changes the
scientific meaning of each finite-bin response and therefore requires numerical
regression tests and regenerated simulation results.

## Zero-deposit phantom bins never become resolved

The adaptive phantom builder considers an energy bin resolved only after at
least two primaries have been sampled, its estimated uncertainty is finite, and
its mean ionizing-energy deposit is positive. A bin in which every sampled
primary deposits zero ionizing energy therefore remains unresolved regardless
of how many zero-deposit events have been observed. The builder continues to
schedule that energy decade instead of using the accumulating evidence that
the response is small. With one sample, the calculated standard error is
undefined. With two or more all-zero samples, the ordinary sample standard
error is instead zero. That numerical zero describes the observed sample but
incorrectly suggests certainty about rare, as-yet-unobserved deposits; the
separate completion check nevertheless keeps the bin unresolved.

Zero observations do constrain the probability $p$ of a positive deposit. After
$n$ independent primaries with no positive deposits, the one-sided 95% upper
confidence limit is

$$
p_{95}=1-0.05^{1/n}\approx\frac{3}{n}.
$$

If the deposited-energy fraction $R$ has a known upper bound $R_{\max}$, this
also bounds the mean response by $E[R]\leq p_{95}R_{\max}$. Taking
$R_{\max}=1$ would give the intuitive bound that the mean deposited-energy
fraction cannot exceed the probability of a deposit. That unit bound must be
verified for the scored Geant4 quantity, particularly for nuclear reactions
that can release binding energy; otherwise an appropriate physical bound is
needed.

The builder should compare this response bound with its absolute dose tolerance.
It may then classify a sufficiently constrained bin as consistent with zero,
record the upper limit, and stop resampling it. Until this is implemented,
adaptive phantom builds containing persistent zero-deposit bins may not report
precision completion.

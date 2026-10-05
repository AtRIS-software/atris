# Known bugs

This file records confirmed defects that have not yet been fixed.

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

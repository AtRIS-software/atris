# Response normalization and statistical uncertainty

AtRIS adds the contributions from simulated incoming particles and their
secondaries. We first divide these sums by the number of incoming particles
to find the average response. We then apply an incident spectrum to calculate
physical rates, such as ion pairs produced per second.

## Normalize by the primaries actually sampled

For layer $d$ and primary-energy bin $b$, the ionization response is

$$
R_{d,b}=\frac{I_{d,b}}{P_b V_d},
$$

where $I_{d,b}$ is accumulated ionizing deposition, $P_b$ is the number of
primary entries in that energy bin, and $V_d$ is layer volume. The denominator
uses the primaries actually recorded in the bin, not the requested total
number of events. Total energy deposition is normalized identically, replacing
$I_{d,b}$ with the accumulated total deposit $T_{d,b}$. Phantom products have
additional mass and area factors;
see [the normalization formulas](../reference/outputs.md#processed-response-tables).

An energy bin with no simulated incoming particles has no response estimate.
Division by zero can produce NaN or infinity. Run more particles to estimate
that bin's response; replacing the missing value with zero would bias the result.

## Apply a physical source separately

If $\dot N_b$ is the physical primary rate represented by bin $b$, a response
rate can be estimated as

$$
\dot Y_d=\sum_b R_{d,b}\,\dot N_b.
$$

This assumes the response represents the source distribution within each bin.
For a spectrum varying strongly inside a broad bin, finer sampling or explicit
weighting may be needed. AtRIS does not divide processed responses by bin width;
use bin-integrated primary rates here. Converting a differential intensity into
$\dot N_b$ also requires energy, source-area, and angular integration consistent
with the simulated source. The [Earth spectrum notebook](../tutorials/earth-spectrum-folding.ipynb)
works through that conversion.

The atmospheric response matrices in
[Winant et al. (2023), Section 2](https://doi.org/10.3390/universe9120502)
illustrate this distinction: they describe the atmospheric effect per incident
primary before applying the incident spectrum and geomagnetic filtering.
The response matrix and the physical radiation environment are separate
parts of the calculation.

## Gather raw sums before normalization

For independent chunks $c$, the combined estimate is

$$
R_{d,b}=\frac{\sum_c I_{c,d,b}}{V_d\sum_c P_{c,b}}.
$$

This weights chunks by the primaries contributing to each bin. An unweighted
average of already normalized chunk tables generally gives a different answer.
The standard `atris-gather` then `atris-postprocess` sequence combines the raw
sums before performing the normalization.

Separately prepared batches can also contribute to one estimate when their
geometry, physics, phantom responses, source distribution, and histogram bins
agree. Event counts and independent random seeds may differ. The shared
normalization must use the combined primary counts.

## What the uncertainty measures mean

Tracks and steps from one primary history are correlated. Histogram fills
therefore cannot automatically be treated as independent Monte Carlo samples.
In particular, `Sw2` alone is not an uncertainty estimate for every normalized
response.

The gather tool reports convergence diagnostics for ionization, including
changes as chunks accumulate and standard-error estimates based on weighted
chunk means. Their [definitions](../reference/chunks.md#convergence-csv) matter:
these are not uncertainty estimates for every dose or counting product. A
small change between successive aggregates can also occur before rare events
have been adequately sampled.

For independent samples with finite variance, statistical error typically
scales approximately as $N^{-1/2}$. Reducing it by a factor of two therefore
requires roughly four times as many histories. More histories do not remove
uncertainty in the atmosphere, incident spectrum, phantom tables, or interaction
models. Examine both sampling convergence and sensitivity to those inputs.

```{figure} ../images/earth-example/protons.convergence.png
:name: earth-proton-convergence
:alt: Proton ionization convergence as completed chunks increase, comparing changes after each chunk group with estimated relative standard errors.
:width: 100%

Ionization convergence in the Earth example. The upper panel measures changes
after adding chunks; the lower panel estimates statistical uncertainty. A small
update does not imply equally small uncertainty.
```

[Open the full-size convergence plot](../images/earth-example/protons.convergence.png).

## Implementation

`atris_tools/postprocess.py` normalizes the responses;
`atris_tools/gather.py` combines histograms and calculates chunk-based
convergence diagnostics.

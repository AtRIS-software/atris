# Research applications

AtRIS calculates how energetic particles interact with an atmosphere and
surface. Depending on the research question, the results may be used directly
as particle spectra or energy-deposition profiles, or passed to chemistry,
climate, and detector-response calculations. The studies below illustrate
several uses of the same transport model.

## Atmospheric chemistry and biosignatures

Cosmic-ray ionization initiates chemical reactions that can change atmospheric
composition and the spectral features used to search for life.
[Herbst et al. (2019)](https://doi.org/10.1051/0004-6361/201935888) combined
AtRIS with the ExoTIC ion-chemistry model and a climate-chemistry model,
testing the coupled calculation against modern Earth. AtRIS supplied the
altitude-dependent ionization rates; the other models calculated the chemical
response and its effect on atmospheric spectra.

The later [TRAPPIST-1e study by Herbst et al. (2024)](https://doi.org/10.3847/1538-4357/ad0895)
used this approach within the INCREASE model suite to investigate how cosmic
rays change ion chemistry and transmission spectra in an Earth-like atmosphere
on TRAPPIST-1e. This connects particle transport to the interpretation of
potential biosignatures without requiring AtRIS itself to solve the chemical
reaction network or calculate a transmission spectrum.

## Earth's atmosphere and secondary particles

[Winant et al. (2023)](https://doi.org/10.3390/universe9120502) used AtRIS to
investigate how latitude and seasonal changes in atmospheric density affect
ionization and absorbed dose from the surface to 100 km. Changing the
atmospheric profile changes where a particle shower develops, even when the
incoming radiation is held fixed.

Particle fluxes are also useful independently of dose. In
[Al-Qaaod et al. (2025)](https://doi.org/10.1029/2025JA034303), AtRIS supplied
summer and winter muon profiles for comparison with MCNP simulations in a study
of atmospheric effects on muon flux. Here the quantity of interest was the
secondary particles reaching each altitude.

## Planetary surfaces, shielding, and solar events

[Guo et al. (2019)](https://doi.org/10.1051/swsc/2018051) applied AtRIS to
the Martian atmosphere and regolith, compared interaction models, and checked
the simulated surface particle spectra against Curiosity's Radiation
Assessment Detector. [Röstel et al. (2020)](https://doi.org/10.1029/2019JE006246)
then examined radiation above and below the surface for different regolith
compositions, including water-rich material, to study shielding for future
habitats.

AtRIS has also been used to study transient radiation from solar energetic
particles. [Zhang et al. (2023)](https://doi.org/10.1029/2023SW003490) applied
spectra reconstructed from historical solar events to Martian atmospheric
models. They investigated how the incident spectrum and atmospheric depth
affect radiation at different surface locations and below ground.

## Dose, detectors, and biological environments

The [phantom method of Banjac et al. (2019)](https://doi.org/10.1029/2019JA026622)
uses precomputed material responses to estimate absorbed and radiation-weighted
dose during atmospheric transport. The paper describes a water-sphere phantom
and compares calculations with balloon dosimetry measurements. Such responses
connect the transported particle field to a particular material or instrument;
[radiation quantities](radiation-quantities.md#phantom-responses) explains how
the method works and the current weighting limitations.

Biological applications extend beyond human exposure.
[Herbst et al. (2020)](https://doi.org/10.1051/0004-6361/201936968) used AtRIS
to investigate radiation in Venus's atmosphere with several phantom geometries
and compositions, including a water-based microbial cell. They compared
galactic cosmic-ray and solar-event contributions at cloud altitudes relevant
to proposed microbial habitats.

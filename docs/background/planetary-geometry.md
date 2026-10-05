# Atmosphere and regolith

The planetary model describes the materials through which radiation travels.
Its primary input is `simulation.psf`. The geometry converter translates that
table into GDML, which Geant4 loads for particle transport.

## Material shells

Each PSF row defines a shell by inner and outer radius, angular bounds,
temperature, density, pressure, and composition. Full angular coverage gives a
spherical shell. Within each shell, these material properties are constant;
an atmospheric profile is approximated by a sequence of such shells.

Layer thickness therefore controls spatial resolution. Finer layers can better
resolve rapid changes near a surface or within a steep density gradient, but
increase the geometry and output size. Refining the grid does not correct an
inaccurate atmospheric profile or composition.
See [the runtime cost of atmospheric layers](what-determines-runtime.md#atmospheric-layers)
for how boundaries affect transport and scoring.

A useful physical measure is the column mass along a path:

$$
X=\int\rho(s)\,\mathrm ds
\;\approx\;\sum_i\rho_i\,\Delta s_i.
$$

Here $\rho_i$ is mass density and $\Delta s_i$ is the distance travelled in
layer $i$. Density in g cm$^{-3}$ and distance in cm give $X$ in g cm$^{-2}$.
Equal geometric altitude does not imply equal overlying material on different
planets; composition also affects which interactions occur.

## Why the atmospheric profile matters

[Winant, Pierrard, Botek, and Herbst (2023)](https://doi.org/10.3390/universe9120502)
used AtRIS to compare Earth atmospheres at different latitudes and times of
year. Their model extended from the surface to 100 km, using 500 m layers.
They found that the atmospheric inputs affect both ionization and absorbed
dose profiles. A PSF therefore describes a physical scenario, not merely the
shape of the simulation volume. Its density profile, composition, location,
and date need to be appropriate to the question being studied. The study's
100 km boundary and layer thickness are choices for that calculation, not
requirements of the PSF format.

## Surface and boundaries

The standard layout contains an interior, a thin surface layer, atmospheric
shells, and an outer terminating shell. The first and last detector IDs stop
tracks. The interior and outer shell are therefore computational boundaries;
their inclusion does not mean transport is followed indefinitely through a
planet's deep interior or surrounding space.

The post-processor uses the first atmospheric row as its altitude reference.
Changing the row ordering or using angular sectors requires checking those
assumptions. The [PSF reference](../reference/inputs.md#planet-specification-format-psf)
and [geometry normalization](../reference/outputs.md#geometry-and-altitude)
specify the conventions.

## Implementation

`atris_tools/psf2gdml.py` constructs the geometry,
`src/SensitiveDetector.cc` handles the terminating detector IDs, and
`atris_tools/postprocess.py` supplies the volume and altitude conventions.

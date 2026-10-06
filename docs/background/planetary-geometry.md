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

## Estimate the primary stopping altitude

The thin dashed curve in the [Earth chunk comparison](../tutorials/run-earth-simulation.md#decide-whether-to-continue)
estimates where a vertically incoming proton stops. It uses the
**continuous slowing-down approximation (CSDA)**: replace individual energy-loss
events by their average rate. The mass stopping power is

$$
S(E)=-\frac{\mathrm dE}{\mathrm dX},
\qquad
R(E_0)=\int_0^{E_0}\frac{\mathrm dE}{S(E)}.
$$

Here $E_0$ is the incoming proton energy, $E$ its remaining energy, and
$R(E_0)$ the mass thickness traversed before stopping. With $S$ in
$\mathrm{MeV\,cm^2\,g^{-1}}$, the range $R$ is in $\mathrm{g\,cm^{-2}}$.
[NIST PSTAR](https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html)
tabulates this range for protons in dry air; the figure uses these
{download}`tabulated values <../data/pstar-air.csv>`.

For the PSF atmosphere, the vertical column mass above altitude $h$ is

$$
X(h)=\int_h^{h_{\mathrm{top}}}\rho(z)\,\mathrm dz,
\qquad
X(h_{\mathrm{stop}})=R(E_0).
$$

Compute $X$ by summing density times layer thickness from the top down, then
interpolate within the layer where the accumulated mass reaches $R(E_0)$.
The plotted curve uses log–log interpolation of the PSTAR energy–range table
and the constant density within each PSF layer. Dry-air stopping powers are
used throughout. For this atmosphere, the estimated stopping altitudes are
about 86 km at 1 MeV, 63 km at 10 MeV, and 33 km at 100 MeV.

The close agreement with the sharp low-energy edge identifies primary stopping
as its main cause. This estimate assumes a straight vertical path; oblique
incidence, scattering, and energy-loss fluctuations change individual stopping
altitudes. It also omits secondary production and transport. Deposition below
the curve can come from descendants of the incoming proton, whose contributions
remain in the original proton's energy column. The curve therefore marks a
primary stopping estimate, not a boundary beyond which deposition is forbidden.

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

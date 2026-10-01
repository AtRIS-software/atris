# Output files

`<name>` below is the full simulation prefix; `N` is a zero-based phantom ID.
This revision writes Geant4 CSV histograms and AtRIS binary files.

## Raw histogram files

| Suffix | Axes | Accumulated weight |
| --- | --- | --- |
| `_h1_h1.1.csv` | Primary kinetic energy, MeV | Primary kinetic energy, MeV. Use `entries`, not `Sw`, for primary counts. |
| `_h2_h2.dir.csv` | Global azimuth, rad; cos(polar angle) | One per primary direction. |
| `_h2_h2.pos.csv` | Global azimuth, rad; cos(polar angle) | One per primary source position. |
| `_h2_h2.ion.csv` | Primary energy, MeV; detector ID | Total deposit minus non-ionizing deposit, MeV, for steps in non-terminating sensitive layers. |
| `_h2_h2.dosN.csv` | Primary energy, MeV; interface ID | Radiation response coefficient × crossing kinetic energy in eV. |
| `_h2_h2.equiN.csv` | Primary energy, MeV; interface ID | The same energy response multiplied by the implemented radiation weight. |
| `_h2_h2.ratesN.csv` | Primary energy, MeV; interface ID | Counting response coefficient. |

All three modes write these histograms. There are $4 + 3N_{\mathrm{phantom}}$
histogram products, where $N_{\mathrm{phantom}}$ is the phantom count. Despite the histogram titles, raw phantom values have not
yet been divided by primary counts, masses, or interface areas.

Source-position and direction histograms have 120 azimuth bins from 0 to $2\pi$
and 60 $\cos\theta$ bins from 0 to 1. Negative $\cos\theta$ values go into underflow;
see the [recorded angular diagnostic defect](../known-bugs.md).

### CSV structure

Files begin with `#` metadata lines, followed by a column header and numeric
rows. Axes are described by `#axis edges ...` or `#axis fixed N low high`.
Read the axes from the output when analyzing an existing run.

| Column | Meaning for a histogram fill with weight `w` |
| --- | --- |
| `entries` | Number of fills, independent of weight. |
| `Sw` | Sum of `w`. |
| `Sw2` | Sum of `w²`. |
| `Sxw0`, `Sx2w0` | Sum of `x*w` and `x²*w` for axis 0. |
| `Sxw1`, `Sx2w1` | Corresponding moments for axis 1, in H2 files. |

These are statistical accumulators, not one particle per CSV row. `Sw2` is not
a ready-to-use uncertainty on the final normalized result. `#planes_Sxyw` is
additional H2 cross-moment metadata; gather sums it with the other accumulators.

Underflow and overflow bins are included. For an energy-versus-detector H2
with `D` detector bins and `B` energy bins, the post-processor reshapes `Sw` to
`(D+2, B+2)`: energy varies fastest. Slicing `[1:-1, 1:-1]` removes the
underflow/overflow rows and columns. The raw primary H1 similarly contains
`B+2` rows. Post-processing assumes the current Geant4 layout of seven header
lines for H1 and ten for H2, including the column header.

### Detector and interface IDs

Ionization is associated with the sensitive volume's detector ID. Phantom
responses and binary crossings use the interface ID:

$$
\alpha = \arccos(\hat{\mathbf r}\cdot\hat{\mathbf p}),\qquad
\mathrm{interface\_id} =
\begin{cases}
\mathrm{detector\_id}-1, & \alpha < \pi/2,\\
\mathrm{detector\_id}, & \text{otherwise}.
\end{cases}
$$

Here $\hat{\mathbf r}$ is the radial unit position and $\hat{\mathbf p}$ is
the momentum direction.

The angle is measured from the outward local radial direction: outward-moving
particles have angles below 90 degrees, inward-moving particles above 90.
The binary angle is rounded to the nearest whole degree, so a stored value of
90 cannot resolve a near-tangential crossing's original direction.

## Processed response tables

`atris-postprocess` writes headerless, whitespace-separated files:

| Suffix | Quantity after scaling |
| --- | --- |
| `.ioni` | Ionizing energy deposition per cm³ per primary in the corresponding energy bin, in MeV cm⁻³ primary⁻¹. It is not yet an ion-pair production rate. |
| `.doseN` | Phantom energy response per mass per primary, using the table's radiation coefficients and eV energy factor. |
| `.equiN` | The same response with the code's radiation weighting applied. |
| `.ratesN` | Counting response per primary, after area scaling. It is not counts per second. |

Each row contains:

```text
detector_or_interface_id  altitude_km  response_bin_0  response_bin_1 ...
```

There is one response column for each interior primary-energy bin, in the
order recorded by `<name>_h1_h1.1.csv`. No division by energy-bin width is
performed. IDs and altitudes are written with integer and three-decimal-place
formats respectively; response values use scientific notation with five
places after the decimal. The first and last physical layer rows are omitted.

Let $P_b$ be the primary H1 `entries` in energy bin $b$, $V_d$ the layer volume
in cm³, $S_d$ the interface area in cm², and $A_N$, $M_N$ the phantom area and
mass from `phantoms.txt`. With raw histogram sums $I$, $D$, $E$, and $C$:

$$
\begin{aligned}
\mathrm{ioni}_{d,b} &= \frac{I_{d,b}}{P_b V_d},\\
\mathrm{dose}_{N,d,b} &= \frac{D_{d,b} A_N}{P_b M_N S_d},\\
\mathrm{equi}_{N,d,b} &= \frac{E_{d,b} A_N}{P_b M_N S_d},\\
\mathrm{rates}_{N,d,b} &= \frac{C_{d,b} A_N}{P_b S_d}.
\end{aligned}
$$

The code does not convert eV/g to Gy or apply a source flux or an ion-pair
creation energy. If the supplied radiation coefficients are dimensionless
energy fractions, `.doseN` has units eV g⁻¹ primary⁻¹; the conversion to
Gy primary⁻¹ would multiply by `1.602176634e-16`. The equivalent response has
the corresponding radiation-weighted units. Coefficient normalization and the
phantom's associated mass/area must be checked against that table's provenance;
the file format alone does not certify them.

An empty primary bin can yield NaN or infinity during division. The
post-processor does not fill unsampled bins or propagate uncertainties. It
warns about detectable input/output mismatches but does not generally reject
them. Keep the input geometry and phantom metadata with each run.

### Geometry and altitude

For PSF radii converted to cm, the post-processor calculates:

$$
\begin{aligned}
\Omega &= (\phi_{\mathrm{end}}-\phi_{\mathrm{start}})
 (\cos\theta_{\mathrm{start}}-\cos\theta_{\mathrm{end}}),\\
S_{\mathrm{inner}} &= \Omega r_{\mathrm{inner}}^2,\\
V &= \frac{\Omega}{3}(r_{\mathrm{outer}}^3-r_{\mathrm{inner}}^3).
\end{aligned}
$$

$\Omega$ is the angular factor.

For a zero-radius core, `S_inner` is replaced with its outer area. Rows are
stably sorted by this area. Reported altitude is
given in km by

$$
h_d = \frac{1}{10^5}\left(\sqrt{\frac{S_d}{4\pi}}-
\sqrt{\frac{S_2}{4\pi}}\right),
$$

where $S_2$ is the area at sorted row index 2.
The standard Earth layout makes this the inner-boundary altitude relative to
the first atmospheric layer. This altitude formula assumes full spherical
shells and the standard interior/crust/atmosphere row arrangement; it is not a
general altitude definition for arbitrary PSF sectors or layer orderings.

### Radiation weighting as implemented

The equivalent-response histogram uses weight 1 by default, 2 for absolute
PDG codes `2212` and `111`, and 20 for supported positive heavy-ion codes in
the phantom header. Thus the pion condition here specifically names neutral
pions; it is not a test for every pion species.

For neutrons, with $e$ equal to kinetic energy in MeV, the implemented weight is:

$$
w(e)=\begin{cases}
3.5+18.2\exp\!\left[-\frac{\ln(e^2)}{6}\right], & e\leq 1,\\
5.0+17.0\exp\!\left[-\frac{\ln((2e)^2)}{6}\right], & 1<e\leq 50,\\
2.5+3.25\exp\!\left[-\frac{\ln((0.04e)^2)}{6}\right], & e>50.
\end{cases}
$$

Here $\ln$ is the natural logarithm. These expressions describe the source
literally, including the placement of the square inside the logarithm; they
are not a statement that the implementation matches a particular radiation
protection standard.

## Binary header

Both binary products start with a 32-byte header. Integer and floating-point
payloads use the writer's native byte order, recorded by the marker. Current
Python readers recognize little- and big-endian headers.

| Byte offset | Type | Field | Current value |
| --- | --- | --- | --- |
| 0 | 8 bytes | Magic | `ATRISBIN` |
| 8 | uint16 | Format version | `1` |
| 10 | uint16 | Record type | `1` for interfaces; `2` for steps |
| 12 | uint32 | Byte-order marker | `0x01020304` |
| 16 | uint32 | Header size | `32` |
| 20 | uint32 | Record size | `16` or `256` bytes |
| 24 | uint32 | Schema version | `1` |
| 28 | uint32 | Reserved | `0` |

The reader rejects incompatible versions, record sizes, or incomplete final
records. Interface readers additionally accept historical headerless records,
interpreted in native byte order. Step readers require a versioned header.

## Interface records: `<name>.binary`

Written in modes `0` and `1` on entry into non-terminating sensitive volumes
when the pre-step status is a geometry boundary. A particle may cross many
interfaces or revisit one, so records are crossings, not unique particles.

| Byte offset | CSV field from `atris-dump` | Type | Meaning |
| --- | --- | --- | --- |
| 0 | `pdg` | int32 | Particle PDG code |
| 4 | `interface` | uint16 | Interface ID |
| 6 | `angle` | uint16 | Rounded angle from outward radius, degrees |
| 8 | `kinetic_energy` | float32 | Pre-step particle kinetic energy, MeV |
| 12 | `source_energy` | float32 | Primary source kinetic energy, MeV |

Records have no event or track identifier. Thread writes are serialized, but
record order is not a global event ordering. `atris-bin-to-ascii` writes these
same five fields without a header, separated by spaces; `atris-dump` writes
comma-separated values with a field-name header.

## Step records: `<name>.steps.binary`

Written in mode `1`, one record per processed step in a sensitive volume,
including terminating volumes. Each record is 256 bytes. Fields occur in this
order, with no extra padding between them:

| Field(s) | Type | Meaning |
| --- | --- | --- |
| `event_id` | int32 | Geant4 event ID; fallback `-1` if unavailable |
| `track_id`, `parent_id` | int32 each | Event-local track ID and parent track ID |
| `step_id` | int32 | Current track step number |
| `pdg` | int32 | Particle PDG code |
| `detector_id` | int32 | Sensitive-volume ID |
| `pre_x_km`, `pre_y_km`, `pre_z_km` | float64 each | Pre-step Cartesian position, km |
| `post_x_km`, `post_y_km`, `post_z_km` | float64 each | Post-step Cartesian position, km |
| `pre_kinetic_energy_MeV`, `post_kinetic_energy_MeV` | float64 each | Kinetic energy at each endpoint |
| `energy_deposit_MeV` | float64 | Total step energy deposit |
| `nonionizing_energy_deposit_MeV` | float64 | Non-ionizing component of that deposit |
| `step_length_m` | float64 | Step length, m |
| `global_time_ns` | float64 | Post-step global time, ns |
| `primary_energy_MeV` | float64 | Source primary kinetic energy, MeV |
| `creator_process` | 64 bytes | Null-terminated process name; `primary` for primary tracks |
| `step_process` | 64 bytes | Null-terminated step-defining process; `none` if unavailable |

The six integers occupy bytes 0–23, the thirteen doubles bytes 24–127, and
the two strings bytes 128–191 and 192–255. Names are truncated to 63 bytes plus
a null terminator. Identify a track by event and track ID together. Across
chunks, also retain the chunk identity. Multithreading can interleave records.

```bash
atris-dump protons.binary | head
atris-dump protons.steps.binary | head
```

## Plots and chunk metadata

`atris-plot` replaces generated PNGs for the input/output groups available:

| Filename | Contents |
| --- | --- |
| `<species>.inputs.png` | Source and geometry inputs |
| `phantom.<name>.inputs.png` | Phantom input response curves, with a sanitized name |
| `<species>.png` | Source diagnostics and processed ionization |
| `<species>.<phantom-stem>.png` | Processed phantom responses |
| `<species>.interfaces.png` | Interface-crossing diagnostics |
| `<species>.steps.png`, `<species>.shower.png` | Step summary and shower visualization |
| `<species>.convergence.png` | Gathered ionization convergence diagnostics |

An unnamed phantom input plot uses `phantom-N.inputs.png`. The plot command
inspects canonical `protons` and `alphas` products in the selected directory;
it does not automatically collect per-chunk binaries. See
[Scatter/gather files](chunks.md) for logs, completion markers, gathered-state
files, and the convergence CSV schema.

Implementation: `src/PrimaryGeneratorAction.cc`, `src/HistoManager.cc`,
`src/SensitiveDetector.cc`, `include/BinaryOutput.hh`, and
`atris_tools/postprocess.py`, `binary_output.py`, `interface_output.py`,
`step_output.py`, and `plotting.py`.

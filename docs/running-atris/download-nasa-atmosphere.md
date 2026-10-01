# Download an atmosphere from NASA and prepare it for AtRIS

Use this guide to obtain an NRLMSIS profile for a chosen date, time, and
location, then turn it into a PSF and Geant4 geometry. NRLMSIS is an
empirical atmospheric model: a profile for today's date is a model evaluation,
not a direct measurement of today's complete atmosphere.
[NASA's model description](https://ccmc.gsfc.nasa.gov/models/NRLMSIS~2.0/)
describes its inputs and scientific scope.

## Choose the date and activity inputs

Open the [NASA CCMC NRLMSIS Instant Run form](https://kauai.ccmc.gsfc.nasa.gov/instantrun/nrlmsis/).
Use **NRLMSIS 2.0** to match the repository examples. The converter can also
read the other supported NRLMSIS text-table versions, but it retains only its
selected species; choosing 2.1 does not add a nitric-oxide column to the PSF.

Select **Coordinated Universal Time (UTC)**, then enter the date and time you
want. To check today's UTC date in a terminal:

```bash
date -u '+%Y-%m-%d'
```

The form's default date may be older than today. Check the actual date rather
than accepting the default.

The form was checked on **29 September 2026**. At that time it required dates
at least **five days in the past** unless explicit optional inputs were supplied.
There are two ways to proceed:

- **Today's date:** supply `F10.7 (daily)`, `F10.7 (3 month avg)`, and `AP (daily)`
  appropriate to your experiment. Record the source and whether these are
  observations, estimates, or chosen scenario values. NASA's model description
  identifies the daily F10.7 input as the previous day's flux.
- **An older date:** leave these fields at `-1` to ask the service to obtain
  activity inputs from its datasets. Read any notices in the returned output;
  automatic lookup does not guarantee that every index is final or that no
  substitution was made.

For a **workflow demonstration only**, values `150`, `150`, and `4` respectively
allow a current-date scenario. These are assumed activity inputs, not a claim
about today's observed solar or geomagnetic conditions. They were used to
check the conversion workflow on 29 September 2026.

## Request a vertical profile

Set the following controls, substituting your location:

| Control | Example setting |
| --- | --- |
| Coordinate Type | Geographic |
| Latitude | `55` degrees north |
| Longitude | `45` degrees east |
| Profile Type | Height |
| Start | `0` km |
| Stop | `100` km |
| Step Size | `1` km |

Longitude uses 0–360 degrees east; for example, 10 degrees west is `350`.
The profile's Start, Stop, and Step Size define the altitude sweep. This request
contains 101 altitude samples. The current form rejects a step below 1 km;
the repository's archived 0.2 km example tables should not be taken as evidence
that the current web form accepts that spacing.

Click **Submit**. When results appear, choose **Download Output**, or open
**View Raw Output** and save its text as `nrlmsis_output.txt`. Save the numeric
text, not the form's HTML or a chart image. The raw-output link belongs to that
specific request; do not rely on it as permanent storage.

Inspect the downloaded file before conversion:

```bash
head -n 5 nrlmsis_output.txt
```

It should contain a header beginning `Year Mon Day` and rows with your requested
date, time, latitude, longitude, and altitude. Preserve any preceding notices
and the returned `F107`, `F107a`, and `apdaily` columns. Existing archived tables
in this repository include a notice that an unavailable averaged F10.7 was
replaced by the daily value, which is why retaining this information matters.

Keep the request settings alongside the file, for example in `atmosphere-request.md`:

```text
Model: NRLMSIS 2.0
Date/time: <requested UTC date and time>
Location: 55 N, 45 E
Altitude samples: 0 to 100 km, step 1 km
F10.7 daily / average / AP: <entered values or -1>
Activity input source and assumptions: <record here>
Returned notices or substitutions: <record here>
Downloaded: <UTC date>
```

## Convert the downloaded table

Create a new run directory and put `nrlmsis_output.txt` there. Run the remaining
commands **inside that directory**:

```bash
atris-nrlmsis-to-psf nrlmsis_output.txt --output simulation.psf
atris-psf-to-gdml simulation.psf
```

The outputs are `simulation.psf` and `simulation.gdml`. The first command
checks the merged altitude grid and physical values; the second converts
layers and compositions to Geant4 geometry. Existing files with these names
are replaced.

For 101 source samples, the PSF has **104 rows**: an interior, crust, 101
atmospheric shells, and an outer terminating layer. The converter treats each
sample as a shell's **lower boundary**, extending the last shell by one grid
step. Thus samples from 0 to 100 km at 1 km spacing produce an atmosphere
extending to **101 km**, not 100 km. Request 0–99 km if you require the final
atmospheric boundary at exactly 100 km with this spacing.

Check the generated dimensions and bounds:

```bash
python - <<'PY'
from atris_tools.psf import load_psf

layers = load_psf('simulation.psf')
atmosphere = layers[2:-1]
print('PSF shape:', layers.shape)
print('Atmospheric altitude bounds [km]:',
      atmosphere[0, 0] - 6371, atmosphere[-1, 1] - 6371)
print('Atmospheric detector IDs:',
      int(atmosphere[0, 6]), int(atmosphere[-1, 6]))
PY
```

For the 0–100 km request, expect `(104, 16)`, bounds `0.0 101.0`, and IDs
`2 102`. The conversion expands one local vertical profile into concentric
spherical shells; it does not create a geographically varying atmosphere.

## Continue with simulation preparation

The atmosphere is now represented by `simulation.psf` and `simulation.gdml`.
From inside this run directory, continue with
[particle-input preparation](prepare-simulation.md#prepare-particle-inputs),
then select any phantom responses and record the physics and output choices.
Keep the downloaded tables with the model so its origin and settings remain
available alongside the simulation inputs.

## Larger downloads and conversion errors

If a request is truncated or too large for the service, split the same uniform
grid into overlapping altitude ranges. For example, at 1 km spacing, use
0–50 and 50–100 km and save `nrlmsis-lower.txt` and `nrlmsis-upper.txt`:

```bash
atris-nrlmsis-to-psf nrlmsis-lower.txt nrlmsis-upper.txt -o simulation.psf
```

Keep model version, time, coordinates, activity inputs, and step size identical.
The repeated 50 km row is deduplicated. A damaged endpoint can be replaced by
a valid overlapping row; overlap does not repair a missing final endpoint
unless another download includes a valid copy of that altitude.

| Error or observation | What to check |
| --- | --- |
| No `Year Mon Day` header | Confirm you saved raw output text rather than HTML or an error response. |
| Mismatched time/location | Re-download every part with matching settings. |
| Conflicting duplicate altitude | Check activity inputs and model version too; the converter does not validate all those metadata fields independently. |
| Incomplete or nonuniform grid | Check returned first/last rows and missing altitudes; re-download the missing range. |
| Suspicious row without replacement | Inspect the row and obtain a valid overlapping sample; do not silently discard it. |
| Submit disabled for today's date | Supply explicit activity inputs or choose a date eligible for automatic lookup. |

See the [input reference](../reference/inputs.md) for detailed validation and
[NASA CCMC](https://kauai.ccmc.gsfc.nasa.gov/instantrun/nrlmsis/) for the current
service controls and restrictions.

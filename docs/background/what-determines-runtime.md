# What determines runtime?

## Particle cascades

Geant4 transports each primary and its secondary particles. More tracks and
steps mean more work, so the source energies, particle species, and physics
list affect the cost per event. Collisions are only part of this: a
[step](https://geant4.web.cern.ch/documentation/dev/prm_html/PhysicsReferenceManual/electromagnetic/elastic_scattering/msc.html#implementation-details)
can also end at a geometry boundary or a limit imposed by continuous energy
loss or scattering.

## Atmospheric layers

Finer layers introduce more boundary crossings, which can require extra steps
and response scoring. Their effect is smaller where the physics already
requires steps much shorter than the layers. Subdividing the same atmosphere
does not proportionally increase physical interactions, so runtime need not
scale with layer count. More layers also mean larger geometry and response
histograms.

## Phantom responses

All phantoms share the same particle transport. At eligible boundary crossings,
AtRIS looks up each phantom's response and updates three histograms: absorbed
dose, radiation-weighted response, and counts.

This scoring work grows roughly with phantom count and the number of crossings;
adding layers can increase both transport and phantom-scoring costs. Each phantom
also adds table and histogram memory, plus merging and writing work. Total
runtime therefore grows by the additional scoring and output cost, without
repeating the particle shower.

For a modest phantom selection, transport normally remains the larger cost, so
phantoms are comparatively cheap. A useful qualitative model is
$T(N) \approx T_{\mathrm{transport}} + N T_{\mathrm{phantom}}$: doubling the
phantom count doubles only the phantom-scoring term, not the complete runtime.
The cost can still become important when many phantoms are selected. Measure a
representative chunk when planning a large selection because the number of
eligible crossings, and therefore the cost per phantom, depends on the
simulation.

## Threads and fixed work

Geant4 distributes complete events among the worker threads. Particle transport
and the associated phantom scoring therefore run in parallel across events;
within one event, its worker processes the selected phantoms in sequence.

Input loading, geometry and run setup, worker coordination, result merging, and
final output contain work that does not scale in the same way. More threads can
shorten event transport without removing those fixed costs, so benchmark total
throughput rather than assuming that doubling the thread count halves runtime.
See [runtime settings](../reference/runtime.md#thread-precedence) for selecting
the number of threads.

## Output mode

`response` accumulates histograms. `profile` adds interface-crossing records,
and `shower` adds transport-step records in sensitive volumes. Those individual
records increase processing, file size, and writing time. See
[output modes](../reference/executable.md#output-modes).

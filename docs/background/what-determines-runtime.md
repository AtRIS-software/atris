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

## Output mode

`response` accumulates histograms. `profile` adds interface-crossing records,
and `shower` adds transport-step records in sensitive volumes. Those individual
records increase processing, file size, and writing time. See
[output modes](../reference/executable.md#output-modes).

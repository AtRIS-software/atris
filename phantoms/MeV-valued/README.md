# Deposited-energy response tables

These radiation-response tables store deposited energy in MeV. AtRIS expects
energy fractions; the compatible tables are in the parent `phantoms/` folder.
Counting tables and other companion files also remain in the parent folder.

The AtRIS energy fraction is obtained column by column using the arithmetic
incident-energy bin centres in MeV:
`fraction = deposited_energy_MeV / ENERGY_CENTRES_MEV`.
`ENERGY_CENTRES_MEV` is defined in `atris_tools.phantom_tables`. Both numerator
and denominator are in MeV, and the conversion factor varies with energy.
Counting efficiencies are already dimensionless. Converted responses are
separate files alongside the archived originals. Historical geometry and
generation settings are described in the phantom library reference.

See [the phantom library reference](../../docs/reference/phantom-library.md#moved-deposited-energy-tables)
for the family inventory, variance scaling, and a conversion example.

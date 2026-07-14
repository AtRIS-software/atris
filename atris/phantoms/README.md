# AtRIS

AtRIS: Phantoms
============================================= 
Author: Saša Banjac

 + For description and validation, please read the AtRIS validation papers by Banjac et al (2018).
 + Documentation can be found on https://et-wiki.physik.uni-kiel.de/atris/atris
 + Author: Saša Banjac

UPDATE 2021 FALL
===================

* AtRIS now also simulates count rates using an advanced counting efficiency response matrix
   - The new phantom generation routines create this matrix
   - A separate branch of AtRIS has been created for the binary output required for the phantoms
   - Previous phantoms are removed. From now on, only ICRU sphere and a ramona phantom is available
   - 5 versions of the RAMONA DOSTEL phantom are created with various shielding thicknesses:
     0 mm Aluminium, 5 mm, 10 mm, 15 mm, 20 mm. 
   - For the ICRU sphere, a similar set of shielded phantoms is being created.
   - Counting response matrices have the same phantom name, but the suffix "_counting" is expected
   - If a counting response matrix is not available, use ideal_counting_response.txt from the files directory
   - We now use only extended phantoms that consider also GCR nuclei

PHANTOM REQUIREMENTS
====================
 * Except for the first line, every line of the phantom has 650 columns describing the efective ionization of a specific particle
 * The binning is always fixed and cannot be changed. It can be recreated with numpy using: 10**np.linspace(-6,7,651). The unit is MeV. Therefore the range extends from 1eV to 10TeV.
 * The first line of the phantom holds the PDG codes of all particles and nothing else. No header starting "#" sign. Ne ending empty space.
 * PDG codes are separated with a single space. 
 * PDG codes do not repeat
 * PDG order gives the order of the rows corresponding to the particles.
 * Both phantoms must have the same PDG code order. Otherwise it will not work properly.
 

Extended phantoms:
==================
These phantoms include response to GCR fully ionized nuclei from Z=3 to Z=28 (most abundant isotope).
For water, I've used .997 g per ccm as desnity, while for TEM it is 1.00 g per ccm

 * icru_b phantom is a r=15cm sphere of water
   -                shape: solid sphere
   -          composition: h2o
   -               radius: 15 cm
   -                 mass: 14094.7550 g 
   -                 area: 1413.72 cm2
 * ramona phantom is a phantom corresponds to the RAMONA/DOSTEL detector A with aluminum shielding in front
   -                shape: disc
   -          composition: Si
   -               radius: 14.85 mm
   -            thickness: 0.315 mm
   -                 mass: 0.5082 g
   -                 area: 6.928 cm2



Instructions for use
====================
See the ramona_dostel example 



 

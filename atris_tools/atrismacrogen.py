"""Generate proton and alpha source macros and energy-bin files."""
import argparse
import logging
import os
from pathlib import Path
import random
import shutil

import numpy as np

from .cli import (
    HelpFormatter,
    add_logging_arguments,
    add_version_argument,
    configure_logging,
)
from .psf import OUTER_RADIUS, load_psf


def read_macro(filename):
    """Read command settings and ordered GPS histogram points."""
    settings = {}
    energy_points = []
    with Path(filename).open() as macro:
        for line in macro:
            fields = line.split("#", 1)[0].split()
            if not fields:
                continue
            command, *values = fields
            if command == "/gps/hist/point":
                energy_points.append((float(values[0]), float(values[1])))
            else:
                settings[command] = " ".join(values)
    return settings, np.asarray(energy_points).reshape(-1, 2)


GENERATED_INPUTS = (
    "protons.mac",
    "protons.bins",
    "protons.gdml",
    "alphas.mac",
    "alphas.bins",
    "alphas.gdml",
)
DEFAULT_PARTICLES_PER_BIN = 5000
DEFAULT_ALPHA_FACTOR = 0.66
logger = logging.getLogger(__name__)


def refuse_existing_inputs(output_dir):
    existing = [
        filename
        for filename in GENERATED_INPUTS
        if os.path.lexists(os.path.join(output_dir, filename))
    ]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing AtRIS inputs: " + ", ".join(existing)
        )


def genMacro(nr1,nr2,N,name,part,fact,thebins,radius,output_dir="./atris/simulation"):
    lines =  ""
    lines += "/run/initialize\n"
    lines += "/run/verbose 2\n"
    lines += part
    lines += "/gps/ene/type User\n"
    lines += "/gps/hist/type energy\n"
    bins   = thebins*fact
    np.savetxt(os.path.join(output_dir, name + '.bins'), bins)
    lines += "/gps/hist/point %.17e %.17e\n"%(bins[0],0.0)
    for thebin in bins[1:]:
        lines += "/gps/hist/point %.17e %.17e\n"%(thebin,1.0)
    lines += "/gps/pos/type Surface\n"
    lines += "/gps/pos/shape Sphere\n"
    lines += "/gps/pos/centre 0 0 0 m\n"
    lines += "/gps/pos/radius %.17e km\n"%radius
    lines += "/gps/ang/type cos\n"
    lines += "/gps/ang/mintheta 0 deg\n"
    lines += "/gps/ang/maxtheta 90 deg\n"
    lines += "/gps/number 1\n"
    lines += "/run/setCut 100. m\n"           #CONFIGURE
    lines += "/run/particle/dumpCutValues\n"
    lines += "/random/setSeeds %i %i\n"%(nr1,nr2)
    lines += "/run/beamOn %i\n"%N
    return lines


def macroSetup(prefix,part,fact,partspb,output_dir="./atris/simulation",base_bins=None,rng=None):
    if base_bins is None:
        base_bins = 10**np.linspace(0,6,121)
    if rng is None:
        rng = random
    radius  = load_psf(os.path.join(output_dir, 'simulation.psf'))[-2, OUTER_RADIUS] + 0.001 # we add 1 meter to the radius to aviod overlap.
    bins    = base_bins
    N       = bins.shape[0]*partspb # At 20 bins per decade, 2500 particles per bin is good. Even better would be 5k or 10k.
    # We are taking two random seeds. Control this for the ability to reproduce.
    seed1     = rng.randint(31,999999)
    seed2     = rng.randint(31,999999)
    #name      = str(seed1)+prefix
    name      = prefix
    shutil.copy2(os.path.join(output_dir, 'simulation.gdml'), os.path.join(output_dir, name + '.gdml'))
    lines = genMacro(seed1,seed2,N,name,part,fact,bins,radius,output_dir)
    filehandle = open(os.path.join(output_dir, name + '.mac'), 'w')
    filehandle.writelines(lines)
    filehandle.close()
    

def macroGenManager(partspb=DEFAULT_PARTICLES_PER_BIN,alphafactor=DEFAULT_ALPHA_FACTOR,output_dir="./atris/simulation",random_seed=None,energy_min_power=0.0,energy_max_power=6.0,energy_points=121):
    if energy_points < 2:
        raise ValueError("energy_points must be at least 2")
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        raise FileNotFoundError("Run directory does not exist: " + output_dir)
    refuse_existing_inputs(output_dir)
    rng = random.Random(random_seed) if random_seed is not None else random
    base_bins = 10**np.linspace(energy_min_power,energy_max_power,energy_points)
    macroSetup('protons',"/gps/particle proton\n",1,partspb,output_dir,base_bins,rng)
    macroSetup('alphas',"/gps/particle alpha\n",4,int(partspb*alphafactor),output_dir,base_bins,rng)


def main():
    """Run the AtRIS macro-generation command."""
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Generate the proton and alpha macros, energy grids, and geometry "
            "copies needed to run AtRIS."
        ),
        epilog=(
            "RUN_DIRECTORY must already contain simulation.psf and "
            "simulation.gdml. This command does not run AtRIS or stage phantom "
            "responses. It writes protons/alphas .mac, .bins, and .gdml files "
            "and refuses to overwrite any of them. The proton event count is "
            "PARTICLES_PER_BIN multiplied by ENERGY_POINTS; the alpha count "
            "uses ALPHA_FACTOR per energy point. Alpha energies are four times "
            "the corresponding proton grid values."
        ),
    )
    parser.add_argument(
        "run_directory",
        nargs="?",
        default=".",
        metavar="RUN_DIRECTORY",
        help="Prepared run directory (default: current directory).",
    )
    parser.add_argument(
        "--particles-per-bin",
        type=int,
        default=DEFAULT_PARTICLES_PER_BIN,
        metavar="COUNT",
        help="Number of proton histories per energy point (default: %(default)s).",
    )
    parser.add_argument(
        "--alpha-factor",
        type=float,
        default=DEFAULT_ALPHA_FACTOR,
        metavar="FACTOR",
        help=(
            "Alpha histories per energy point as a fraction of the proton "
            "count; the result is truncated to an integer (default: %(default)s)."
        ),
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        metavar="SEED",
        help="Seed for reproducible Geant4 seed pairs (default: random).",
    )
    parser.add_argument(
        "--energy-min-power",
        type=float,
        default=0.0,
        metavar="POWER",
        help=(
            "Base-10 exponent of the minimum proton energy in MeV "
            "(default: 0, or 1 MeV)."
        ),
    )
    parser.add_argument(
        "--energy-max-power",
        type=float,
        default=6.0,
        metavar="POWER",
        help=(
            "Base-10 exponent of the maximum proton energy in MeV "
            "(default: 6, or 1 TeV)."
        ),
    )
    parser.add_argument(
        "--energy-points",
        type=int,
        default=121,
        metavar="COUNT",
        help=(
            "Number of logarithmically spaced energy points, including both "
            "endpoints (default: 121)."
        ),
    )
    add_logging_arguments(parser)
    add_version_argument(parser)
    args = parser.parse_args()
    configure_logging(args.log_level)
    logger.debug(
        "Generating inputs with %i particles per bin, %i energy points, "
        "and alpha factor %.3g",
        args.particles_per_bin,
        args.energy_points,
        args.alpha_factor,
    )
    macroGenManager(
        args.particles_per_bin,
        args.alpha_factor,
        args.run_directory,
        args.random_seed,
        args.energy_min_power,
        args.energy_max_power,
        args.energy_points,
    )
    logger.info(
        "Generated proton and alpha input files in %s",
        os.path.abspath(args.run_directory),
    )


if __name__ == "__main__":
    main()

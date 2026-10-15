import argparse
import os
from pathlib import Path

import numpy as np

from .cli import HelpFormatter, add_version_argument
from .psf import (
    INNER_RADIUS, OUTER_RADIUS, PHI_START, PHI_END, THETA_START, THETA_END,
    DETECTOR_ID, TEMPERATURE, DENSITY, PRESSURE, STATE, FIRST_ELEMENT,
    PSF, _compact_fractions,
)

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

def gdml_material(mat, name, temperature, density, pressure,state="solid"):
    """Write element mass fractions; temperature K, density g/cm3, pressure Pa."""
    header = '\t<material name="%s" state="%s">\n'%(name,state)
    footer = '\t</material>\n'
    output = ""
    output += header
    output += '\t\t<D value="%e" unit="g/cm3" />\n'%density
    output += '\t\t<T value="%e" unit="K" />\n'%temperature
    output += '\t\t<P value="%e" unit="Pa" />\n'%pressure
    for element, frac in mat.items():
        if frac != 0.:
            current = '\t\t<fraction n="%e" ref="G4_%s" />\n'%(frac,element)
            output += current
    output += footer
    return output



def line_processor(filename):
    psf = PSF.read(filename)
    composition, *elements = psf.materials.split()
    core = _compact_fractions(composition)
    data = psf.layers
    
    #We generate the materials and geometry entries
    materials, geometry, struct = [], [], []
    for layer_index, aLine in enumerate(data):
        state_code = aLine[STATE]
        state = {1.0: "solid", 2.0: "liquid"}.get(state_code, "gas")
        sdid = int(aLine[DETECTOR_ID])
        identifier = str(sdid)
        if np.count_nonzero(data[:, DETECTOR_ID] == sdid) > 1:
            identifier += "_" + str(layer_index)
        name = "material" + identifier
        temp = aLine[TEMPERATURE]
        dens = aLine[DENSITY]
        pres = aLine[PRESSURE]
        rowmat = dict(zip(elements, aLine[FIRST_ELEMENT:]))
        material = (
            core
            if state_code == 1.0
            and not any(rowmat.values())
            else rowmat
        )
        materials.append(gdml_material(material, name, temp, dens, pres, state))
        #now the geometry  entry
        solname  = "solid" + identifier
        rmin     = aLine[INNER_RADIUS]
        rmax     = aLine[OUTER_RADIUS]
        phimin   = aLine[PHI_START]
        phimax   = aLine[PHI_END]
        phimax   = phimax - phimin
        if np.abs(phimax -2.0*np.pi) < 0.01: phimax = "TWOPI"
        thetamin = aLine[THETA_START]
        thetamax = aLine[THETA_END]
        thetamax = thetamax - thetamin
        if np.abs(thetamax -np.pi) < 0.01: thetamax = "PI"
        if thetamax == 2.0: thetamax = "PI"
        sphere   = '\t<sphere name="%s" rmin="%.17e" rmax="%.17e" startphi="%.17e" deltaphi="%s" starttheta="%.17e" deltatheta="%s" lunit="km" aunit="rad"/>\n'%(solname,rmin,rmax,phimin,str(phimax) if isinstance(phimax, str) else format(phimax, '.17e'),thetamin,str(thetamax) if isinstance(thetamax, str) else format(thetamax, '.17e'))
        geometry.append(sphere)
        struct.append(['volume'+identifier,name,solname,sdid])
    wrld = data[-1, OUTER_RADIUS]
    return materials, geometry, struct, wrld

def gdml_compile(materials, world, geometry, structure, filename):
    finalfile = ""
    header = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n<gdml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://service-spi.web.cern.ch/service-spi/app/releases/GDML/schema/gdml.xsd">\n\n\n\n'
    footer = '\n<setup name="Exoplanet" version="1.0">\n\t<world ref="World"/>\n</setup>\n</gdml>'
    finalfile += header
    
    #now the <define> part
    #here we need to modify the offset of the world box. 
    define = '<define>\n\t<constant name="PI" value="1.*pi"/>\n\t<constant name="TWOPI" value="2.*pi"/>\n\t<position name="center"/>\n\t<rotation name="identity"/>\n</define>\n'
    finalfile += define
    
    #Now the materials
    finalfile += "<materials>\n"
    #We also add the AtRIS material extensions
    finalfile += Path(data_dir, "atris.materials").read_text()
    for mat in materials:
        finalfile += mat
    finalfile += "</materials>\n"
    #Now the geometry
    finalfile += "<solids>\n"
    #add the world
    wd         = world * 2
    add        = '\t<box name="WorldBox" x="%.17e" y="%.17e" z="%.17e" lunit="km"/>\n'%(wd,wd,wd)
    finalfile += add
    
    for vol in geometry:
        finalfile += vol
    finalfile += "</solids>\n"
    
    #now the structure
    finalfile += "<structure>\n"
    for st in structure:
        add = '\t<volume name="%s">\n\t\t<materialref ref="%s"/>\n\t\t<solidref ref="%s"/>\n'%tuple(st[:3])
        if st[3] >= 0:
            add += '\t\t<auxiliary auxtype="SensDet" auxvalue="%i"/>\n'%st[3]
        add += '\t</volume>\n'
        finalfile += add
    #now we need to add the world and place all the other volumes
    worldpart = '\t<volume name="World">\n\t\t<materialref ref="Vacuum"/>\n\t\t<solidref ref="WorldBox"/>\n'
    finalfile += worldpart
    for st in structure:
        vv = st[0]
        add = '\t\t<physvol>\n\t\t\t<volumeref ref="%s"/>\n\t\t\t<positionref ref="center"/>\n\t\t</physvol>\n'%vv
        finalfile += add
    finalfile += "\t</volume>\n"
    finalfile += "</structure>\n"
    #Now the footer
    finalfile += footer
    Path(filename).write_text(finalfile)

def psf2gdml(input_path, output_path=None, *, world_margin_km=100.0):
    if not np.isfinite(world_margin_km) or world_margin_km < 0:
        raise ValueError("World margin must be finite and nonnegative")
    input_path = Path(input_path)
    output_path = (
        Path(output_path) if output_path else input_path.with_suffix(".gdml")
    )
    materials, geometry, structure, world = line_processor(input_path)
    gdml_compile(
        materials,
        world + world_margin_km,
        geometry,
        structure,
        output_path,
    )
    return output_path


def main():
    """Convert an AtRIS PSF file to GDML."""
    parser = argparse.ArgumentParser(
        formatter_class=HelpFormatter,
        description=(
            "Convert an AtRIS Planet Specification Format model into the GDML "
            "geometry and material description read by Geant4."
        ),
        epilog=(
            "The output defaults to the input basename with a .gdml suffix. "
            "An existing output file is replaced. This command does not "
            "download or generate an atmosphere and does not run AtRIS."
        ),
    )
    parser.add_argument(
        "psf_file",
        type=Path,
        metavar="PSF_FILE",
        help="PSF model to convert.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="GDML_FILE",
        help="GDML file to write (default: input basename with .gdml suffix).",
    )
    add_version_argument(parser)
    parser.add_argument("--world-margin-km", type=float, default=100.0,
                        help="Margin beyond the outer radius for the vacuum world (default: 100 km).")
    args = parser.parse_args()
    psf2gdml(args.psf_file, args.output, world_margin_km=args.world_margin_km)


if __name__ == "__main__":
    main()

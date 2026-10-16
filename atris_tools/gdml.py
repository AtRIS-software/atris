"""Convert PSF geometry to GDML and read spherical GDML layers."""

from pathlib import Path
import argparse
import xml.etree.ElementTree as ElementTree

import numpy as np

from .cli import HelpFormatter, add_version_argument
from .psf import (
    DENSITY,
    DETECTOR_ID,
    FIRST_ELEMENT,
    INNER_RADIUS,
    OUTER_RADIUS,
    PHI_END,
    PHI_START,
    PRESSURE,
    PSF,
    STATE,
    TEMPERATURE,
    THETA_END,
    THETA_START,
    _compact_fractions,
)


LENGTH_TO_KM = {
    "mm": 1.0e-6,
    "cm": 1.0e-5,
    "m": 1.0e-3,
    "km": 1.0,
}
DATA_DIRECTORY = Path(__file__).parent / "data"


def read_gdml_layers(filename):
    """Read every sensitive spherical layer from a GDML geometry."""
    root = ElementTree.parse(filename).getroot()

    materials = {
        material.get("name"): material
        for material in root.findall("./materials/material")
    }

    solids = {}
    for sphere in root.findall("./solids/sphere"):
        unit = sphere.get("lunit", "mm")
        if unit not in LENGTH_TO_KM:
            raise ValueError("Unsupported GDML length unit: " + unit)
        scale = LENGTH_TO_KM[unit]
        solids[sphere.get("name")] = (
            float(sphere.get("rmin")) * scale,
            float(sphere.get("rmax")) * scale,
        )

    layers = []
    for volume in root.findall("./structure/volume"):
        material_reference = volume.find("materialref")
        solid_reference = volume.find("solidref")
        sensitive_detector = volume.find("auxiliary[@auxtype='SensDet']")
        if (
            material_reference is None
            or solid_reference is None
            or sensitive_detector is None
        ):
            continue
        material = materials[material_reference.get("ref")]
        radii = solids[solid_reference.get("ref")]
        properties = {
            "state": material.get("state"),
            "fractions": {
                fraction.get("ref"): float(fraction.get("n"))
                for fraction in material.findall("fraction")
            },
            "density": float(material.find("D").get("value")),
            "temperature": float(material.find("T").get("value")),
            "pressure": float(material.find("P").get("value")),
        }
        layers.append(
            {
                "rmin": radii[0],
                "rmax": radii[1],
                "detector_id": int(sensitive_detector.get("auxvalue")),
                **properties,
            }
        )

    layers.sort(key=lambda layer: layer["rmin"])
    if not layers:
        raise ValueError("No sensitive spherical layers found in " + str(filename))
    return layers


def _material_xml(mat, name, temperature, density, pressure,state="solid"):
    """Render element mass fractions; temperature K, density g/cm3, pressure Pa."""
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


def _psf_sections(filename):
    """Return material, solid and volume definitions plus the outer radius in km."""
    psf = PSF.read(filename)
    composition, *elements = psf.materials.split()
    solid_fractions = _compact_fractions(composition)
    data = psf.layers
    
    materials, geometry, structure = [], [], []
    for layer_index, layer in enumerate(data):
        state_code = layer[STATE]
        state = {1.0: "solid", 2.0: "liquid"}.get(state_code, "gas")
        detector_id = int(layer[DETECTOR_ID])
        identifier = str(detector_id)
        if np.count_nonzero(data[:, DETECTOR_ID] == detector_id) > 1:
            identifier += "_" + str(layer_index)
        name = "material" + identifier
        temperature = layer[TEMPERATURE]
        density = layer[DENSITY]
        pressure = layer[PRESSURE]
        layer_fractions = dict(zip(elements, layer[FIRST_ELEMENT:]))
        material = (
            solid_fractions
            if state_code == 1.0
            and not any(layer_fractions.values())
            else layer_fractions
        )
        materials.append(_material_xml(material, name, temperature, density, pressure, state))
        solid_name  = "solid" + identifier
        rmin     = layer[INNER_RADIUS]
        rmax     = layer[OUTER_RADIUS]
        phi_start   = layer[PHI_START]
        phi_span   = layer[PHI_END]
        phi_span   = phi_span - phi_start
        if np.abs(phi_span -2.0*np.pi) < 0.01: phi_span = "TWOPI"
        theta_start = layer[THETA_START]
        theta_span = layer[THETA_END]
        theta_span = theta_span - theta_start
        if np.abs(theta_span -np.pi) < 0.01: theta_span = "PI"
        if theta_span == 2.0: theta_span = "PI"
        sphere   = '\t<sphere name="%s" rmin="%.17e" rmax="%.17e" startphi="%.17e" deltaphi="%s" starttheta="%.17e" deltatheta="%s" lunit="km" aunit="rad"/>\n'%(solid_name,rmin,rmax,phi_start,str(phi_span) if isinstance(phi_span, str) else format(phi_span, '.17e'),theta_start,str(theta_span) if isinstance(theta_span, str) else format(theta_span, '.17e'))
        geometry.append(sphere)
        structure.append(['volume'+identifier,name,solid_name,detector_id])
    outer_radius_km = data[-1, OUTER_RADIUS]
    return materials, geometry, structure, outer_radius_km


def _write_gdml(materials, world, geometry, structure, filename):
    xml = ""
    header = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n<gdml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://service-spi.web.cern.ch/service-spi/app/releases/GDML/schema/gdml.xsd">\n\n\n\n'
    footer = '\n<setup name="Exoplanet" version="1.0">\n\t<world ref="World"/>\n</setup>\n</gdml>'
    xml += header
    
    define = '<define>\n\t<constant name="PI" value="1.*pi"/>\n\t<constant name="TWOPI" value="2.*pi"/>\n\t<position name="center"/>\n\t<rotation name="identity"/>\n</define>\n'
    xml += define
    
    xml += "<materials>\n"
    xml += Path(DATA_DIRECTORY, "atris.materials").read_text()
    for mat in materials:
        xml += mat
    xml += "</materials>\n"
    xml += "<solids>\n"
    world_size_km         = world * 2
    add        = '\t<box name="WorldBox" x="%.17e" y="%.17e" z="%.17e" lunit="km"/>\n'%(world_size_km,world_size_km,world_size_km)
    xml += add
    
    for solid in geometry:
        xml += solid
    xml += "</solids>\n"
    
    xml += "<structure>\n"
    for volume in structure:
        add = '\t<volume name="%s">\n\t\t<materialref ref="%s"/>\n\t\t<solidref ref="%s"/>\n'%tuple(volume[:3])
        if volume[3] >= 0:
            add += '\t\t<auxiliary auxtype="SensDet" auxvalue="%i"/>\n'%volume[3]
        add += '\t</volume>\n'
        xml += add
    worldpart = '\t<volume name="World">\n\t\t<materialref ref="Vacuum"/>\n\t\t<solidref ref="WorldBox"/>\n'
    xml += worldpart
    for volume in structure:
        volume_name = volume[0]
        add = '\t\t<physvol>\n\t\t\t<volumeref ref="%s"/>\n\t\t\t<positionref ref="center"/>\n\t\t</physvol>\n'%volume_name
        xml += add
    xml += "\t</volume>\n"
    xml += "</structure>\n"
    xml += footer
    Path(filename).write_text(xml)


def psf_to_gdml(input_path, output_path=None, *, world_margin_km=100.0):
    if not np.isfinite(world_margin_km) or world_margin_km < 0:
        raise ValueError("World margin must be finite and nonnegative")
    input_path = Path(input_path)
    output_path = (
        Path(output_path) if output_path else input_path.with_suffix(".gdml")
    )
    materials, geometry, structure, world = _psf_sections(input_path)
    _write_gdml(
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
    psf_to_gdml(args.psf_file, args.output, world_margin_km=args.world_margin_km)


if __name__ == "__main__":
    main()

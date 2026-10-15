import numpy as np
import pytest
import xml.etree.ElementTree as ET

from atris_tools.psf import (
    DETECTOR_ID, STATE, FIRST_ELEMENT, GEOMETRY_COLUMNS,
    PSF, load_psf, read_psf_header, read_psf_layers, write_psf,
)


@pytest.mark.parametrize("filename", ["sphere", "sphere.psf", "sphere.data"])
@pytest.mark.parametrize("as_string", [False, True])
def test_write_psf_appends_missing_suffix(tmp_path, filename, as_string):
    psf = PSF(inner_radius_km=0, outer_radius_km=1e-4,
                    temperature_k=293, density_g_cm3=1, pressure_pa=101325,
                    mass_fractions={"H": 1})
    path = tmp_path / filename
    write_psf(str(path) if as_string else path, psf)
    expected = path if filename.endswith(".psf") else tmp_path / (filename + ".psf")
    np.testing.assert_allclose(load_psf(expected), psf.layers)
    assert not (tmp_path / (filename + ".psf.psf")).exists()


def test_psf_print_and_save(tmp_path):
    psf = PSF(inner_radius_km=0, outer_radius_km=1e-4,
                    temperature_k=293, density_g_cm3=1, pressure_pa=101325,
                    state="liquid", mass_fractions={"H": 1})
    summary = str(psf)
    assert "1 spherical layer" in summary
    assert "liquid" in summary
    assert "1.000000e-04" in summary
    assert "H=1.000000e+00" in summary
    psf.save(tmp_path / "sphere")
    np.testing.assert_allclose(load_psf(tmp_path / "sphere.psf"), psf.layers)


def test_gdml_preserves_micrometre_spheres_and_world(tmp_path):
    from atris_tools.psf2gdml import line_processor, gdml_compile
    radius = 4e-9  # 4 micrometres, in PSF kilometres.
    psf = PSF(inner_radius_km=[0], outer_radius_km=[radius],
                    temperature_k=293, density_g_cm3=1, pressure_pa=101325,
                    mass_fractions={"H": 1}, solid_composition="H1000")
    path = tmp_path / "sphere.psf"
    write_psf(path, psf)
    output = tmp_path / "sphere.gdml"
    materials, geometry, structure, _ = line_processor(path)
    gdml_compile(materials, 2 * radius, geometry, structure, output)
    gdml = ET.parse(output)
    sphere = gdml.find("./solids/sphere")
    world = gdml.find("./solids/box")
    assert float(sphere.attrib["rmax"]) == radius
    assert float(world.attrib["x"]) == 4 * radius
    assert "e-09" in sphere.attrib["rmax"]


def test_build_and_write_named_layers(tmp_path):
    psf = PSF(
        inner_radius_km=[0, 1, 2, 3.001],
        outer_radius_km=[1, 2, 3, 3.021],
        temperature_k=300,
        density_g_cm3=[2.7, 0.001, 1, 2.7],
        pressure_pa=1e5,
        state=["solid", "gas", "liquid", "solid"],
        mass_fractions={"O": [0, 0.2, 1, 0], "N": [0, 0.8, 0, 0]},
        solid_composition="O533Si467",
    )
    path = tmp_path / "simulation.psf"
    write_psf(path, psf, fmt=psf.formats("%.6e"))

    assert read_psf_header(path) == ["O533Si467", "O", "N"]
    expected = np.array([
        [0, 1, 0, 2*np.pi, 0, np.pi, 0, 300, 2.7, 1e5, 1, 0, 0],
        [1, 2, 0, 2*np.pi, 0, np.pi, 1, 300, 0.001, 1e5, 0, 0.2, 0.8],
        [2, 3, 0, 2*np.pi, 0, np.pi, 2, 300, 1, 1e5, 2, 1, 0],
        [3.001, 3.021, 0, 2*np.pi, 0, np.pi, 3, 300, 2.7, 1e5, 1, 0, 0],
    ])
    np.testing.assert_allclose(load_psf(path), expected, rtol=5e-7)
    assert read_psf_layers(path)[1]["fractions"] == {"O": 0.2, "N": 0.8}


def test_low_precision_preserves_thin_shells(tmp_path):
    psf = PSF(
        inner_radius_km=[9556.48, 9556.5, 9656.501],
        outer_radius_km=[9556.5, 9656.5, 9656.521],
        temperature_k=300, density_g_cm3=0.001234567,
        pressure_pa=80375.4, mass_fractions={"N": 1},
        solid_composition="O533Si467",
    )
    path = tmp_path / "simulation.psf"
    write_psf(path, psf, fmt=psf.formats("%.3e"))
    data = load_psf(path)
    np.testing.assert_allclose(data[:, GEOMETRY_COLUMNS], psf.layers[:, GEOMETRY_COLUMNS], rtol=1e-11)
    np.testing.assert_allclose(data[:, 1] - data[:, 0], [0.02, 100, 0.02])
    assert data[2, 0] - data[1, 1] == pytest.approx(0.001)
    assert "1.235e-03" in path.read_text()
    assert "8.038e+04" in path.read_text()


def test_scalar_shell_matches_single_element_arrays():
    scalar = dict(inner_radius_km=0, outer_radius_km=1.5e-4,
                  temperature_k=293, density_g_cm3=0.997, pressure_pa=101325,
                  state="liquid", mass_fractions={"H": 0.112, "O": 0.888},
                  solid_composition="H112O888")
    arrays = {key: [value] for key, value in scalar.items()
              if key not in ("mass_fractions", "solid_composition")}
    arrays.update(mass_fractions={key: [value] for key, value in scalar["mass_fractions"].items()},
                  solid_composition=scalar["solid_composition"])
    np.testing.assert_array_equal(PSF(**scalar).layers, PSF(**arrays).layers)


def test_explicit_liquid_fractions_supply_compact_header(tmp_path):
    hydrogen = 2 * 1.00794 / (2 * 1.00794 + 15.9994)
    oxygen = 1 - hydrogen
    psf = PSF(inner_radius_km=0, outer_radius_km=1.5e-4,
                    temperature_k=293, density_g_cm3=.997, pressure_pa=101325,
                    state="liquid", mass_fractions={"H": hydrogen, "O": oxygen})
    assert psf.materials == "H112O888 H O"
    np.testing.assert_array_equal(psf.layers[:, FIRST_ELEMENT:], [[hydrogen, oxygen]])
    path = tmp_path / "water.psf"
    write_psf(path, psf)
    assert read_psf_layers(path)[0]["fractions"] == {"H": hydrogen, "O": oxygen}


def test_zero_fraction_solid_requires_explicit_fallback():
    with pytest.raises(ValueError, match="require solid_composition"):
        PSF(inner_radius_km=0, outer_radius_km=1,
                  temperature_k=293, density_g_cm3=2.7, pressure_pa=0,
                  state="solid", mass_fractions={"O": 0})


def test_scalar_composition_broadcasts_across_layers():
    psf = PSF(
        inner_radius_km=[1, 2], outer_radius_km=[2, 3],
        temperature_k=[300, 200], density_g_cm3=0.001, pressure_pa=[10, 1],
        mass_fractions={"N": 0.8, "O": 0.2}, solid_composition="O533Si467",
    )
    np.testing.assert_allclose(psf.layers[:, FIRST_ELEMENT:], [[0.8, 0.2], [0.8, 0.2]])
    np.testing.assert_array_equal(psf.layers[:, STATE], [0, 0])
    with pytest.raises(ValueError, match="column order"):
        write_psf("unused.psf", psf, materials="O533Si467 O N", fmt="%.3e")


@pytest.mark.parametrize("override,match", [
    ({"outer_radius_km": [2]}, "equal length"),
    ({"inner_radius_km": [1, 1.5]}, "overlap"),
    ({"temperature_k": [100, 200, 300]}, "one value per layer"),
    ({"density_g_cm3": -1}, "positive"),
    ({"pressure_pa": np.nan}, "finite"),
    ({"state": "plasma"}, "State"),
    ({"mass_fractions": {"N": 0.5}}, "sum to one"),
    ({"mass_fractions": {"N": -0.1, "O": 1.1}}, "nonnegative"),
    ({"mass_fractions": {"N": 0}}, "sum to one"),
])
def test_named_layers_reject_inconsistent_inputs(override, match):
    arguments = dict(
        inner_radius_km=[1, 2], outer_radius_km=[2, 3], temperature_k=300,
        density_g_cm3=0.001, pressure_pa=1e5, mass_fractions={"N": 1},
        solid_composition="O533Si467",
    )
    arguments.update(override)
    with pytest.raises(ValueError, match=match):
        PSF(**arguments)


def test_written_psf_preserves_values_materials_and_states(tmp_path):
    path = tmp_path / "simulation.psf"
    layers = np.array([
        [0, 1, 0, 2 * np.pi, 0, np.pi, 0, 293, 2.7, 1e5, 1, 0, 0],
        [1, 2, 0, 2 * np.pi, 0, np.pi, 1, 250, 0.1, 2, 2, 0.25, 0.75],
        [2, 3, 0, 2 * np.pi, 0, np.pi, 2, 240, 0.01, 1, 0, 1, 0],
    ])

    write_psf(path, layers, materials="O750Si250 N O", fmt="%.6e")

    assert read_psf_header(path) == ["O750Si250", "N", "O"]
    np.testing.assert_allclose(load_psf(path), layers, rtol=5e-7)
    assert [layer["state"] for layer in read_psf_layers(path)] == ["solid", "liquid", "gas"]
    assert "density g/cm3" in path.read_text()
    assert "pressure state N O" in path.read_text()


@pytest.mark.parametrize("column,value", [(6, 0.5), (10, 3), (8, np.nan)])
def test_invalid_psf_does_not_overwrite_existing_file(tmp_path, column, value):
    path = tmp_path / "simulation.psf"
    path.write_text("original contents")
    layers = np.array([[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]], dtype=float)
    psf = PSF.from_layers(layers, "H1000 H")
    layers[0, column] = value

    with pytest.raises(ValueError):
        write_psf(path, layers, materials="H1000 H", fmt="%.3e")
    with pytest.raises(ValueError):
        psf.save(path)
    with pytest.raises(ValueError):
        PSF.from_layers(layers, "H1000 H")
    source = tmp_path / "invalid.psf"
    source.write_text("H1000 H\n" + " ".join(map(str, layers[0])) + "\n")
    with pytest.raises(ValueError):
        PSF.read(source)
    assert path.read_text() == "original contents"


@pytest.mark.parametrize("materials", ["H1000 H O", "H1000 H H", "invalid H", "H1000"])
def test_psf_read_and_array_construction_reject_bad_material_definitions(tmp_path, materials):
    layers = np.array([[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]], dtype=float)
    with pytest.raises(ValueError):
        PSF.from_layers(layers, materials)
    path = tmp_path / "invalid.psf"
    path.write_text(materials + "\n" + " ".join(map(str, layers[0])) + "\n")
    with pytest.raises(ValueError):
        PSF.read(path)


def test_psf_writer_rejects_material_column_mismatch(tmp_path):
    with pytest.raises(ValueError, match="columns"):
        write_psf(tmp_path / "simulation.psf", np.zeros((2, 12)), materials="H1000 H O", fmt="%.3e")


def test_reads_descriptive_header_followed_by_material_definition(tmp_path):
    path = tmp_path / "simulation.psf"
    path.write_text(
        "# Planet Specification Format\n"
        "# Column descriptions\n"
        "H1000 H\n"
        "0 1 0 1 0 1 0 293 1 1 1 0\n"
    )

    assert read_psf_header(path) == ["H1000", "H"]
    psf = PSF.read(path)
    assert psf.validate() is psf
    psf.save(tmp_path / "partial-angle.psf")
    np.testing.assert_array_equal(PSF.read(tmp_path / "partial-angle.psf").layers, psf.layers)
    np.testing.assert_allclose(
        load_psf(path),
        [[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]],
    )


def test_reads_legacy_commented_material_definition(tmp_path):
    path = tmp_path / "simulation.psf"
    path.write_text(
        "#H1000 H\n"
        "0 1 0 1 0 1 0 293 1 1 1 0\n"
    )

    assert read_psf_header(path) == ["H1000", "H"]
    np.testing.assert_allclose(
        load_psf(path),
        [[0, 1, 0, 1, 0, 1, 0, 293, 1, 1, 1, 0]],
    )


def test_reads_psf_rows_as_material_layers(tmp_path):
    from atris_tools.psf2gdml import line_processor

    path = tmp_path / "simulation.psf"
    path.write_text(
        "O3Si1 N O\n"
        "0 1 0 1 0 1 0 293 2.7 1 1 0 0\n"
        "1 2 0 1 0 1 1 250 0.1 2 2 0.25 0.75\n"
    )

    layers = read_psf_layers(path)

    assert [layer["state"] for layer in layers] == ["solid", "liquid"]
    assert layers[0]["fractions"] == {"O": 0.75, "Si": 0.25}
    materials, _, _, _ = line_processor(path)
    fractions = {item.get("ref").removeprefix("G4_"): float(item.get("n"))
                 for item in ET.fromstring(materials[0]).findall("fraction")}
    assert fractions == layers[0]["fractions"]
    assert layers[1]["fractions"] == {"N": 0.25, "O": 0.75}
    assert [layer["detector_id"] for layer in layers] == [0, 1]


def test_writer_without_format_uses_numpy_formatting(tmp_path):
    path = tmp_path / "simulation.psf"
    layers = np.array([
        [9556.48, 9556.5, 0, 2*np.pi, 0, np.pi, 0,
         293.123456789, 0.001234567891234, 80375.41234567, 0, 1],
    ])
    write_psf(path, layers, materials="H1000 H")
    np.testing.assert_array_equal(load_psf(path), layers)
    expected = tmp_path / "numpy.txt"
    np.savetxt(expected, layers)
    assert path.read_text().splitlines()[6:] == expected.read_text().splitlines()

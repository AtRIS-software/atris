import numpy as np

from atris_tools import input_plotting


MACRO = """\
/gps/particle proton
/gps/ene/type User
/gps/hist/type energy
/gps/hist/point 1 0
/gps/hist/point 10 1
/gps/hist/point 100 1
/gps/pos/type Surface
/gps/pos/shape Sphere
/gps/pos/radius 7000 km
/gps/ang/type cos
/gps/ang/mintheta 0 deg
/gps/ang/maxtheta 90 deg
/gps/number 1
/run/setCut 100 m
/random/setSeeds 123 456
/run/beamOn 10
"""


def prepare_inputs(run_directory, gdml_text):
    (run_directory / "protons.gdml").write_text(gdml_text)
    (run_directory / "protons.mac").write_text(MACRO)
    np.savetxt(run_directory / "protons.bins", [1, 10, 100])
    (run_directory / "phantoms.txt").write_text(
        "0  test-phantom  1.0  2.0\n"
    )

    response = np.vstack(
        (
            np.linspace(0.0, 1.0, 650),
            np.linspace(1.0, 2.0, 650),
        )
    )
    for prefix in ("radiation", "counting"):
        filename = run_directory / (prefix + "_phantom0.txt")
        filename.write_text("22 2212\n")
        with filename.open("a") as phantom_file:
            np.savetxt(phantom_file, response)


def test_read_macro_and_atmosphere(tmp_path, gdml_text):
    (tmp_path / "protons.mac").write_text(MACRO)
    (tmp_path / "protons.gdml").write_text(gdml_text)

    settings, energy_points = input_plotting.read_macro(tmp_path / "protons.mac")
    all_layers = input_plotting.read_layers(tmp_path / "protons.gdml")

    assert settings["/gps/particle"] == "proton"
    np.testing.assert_allclose(energy_points, [[1, 0], [10, 1], [100, 1]])
    assert all_layers[1]["fractions"] == {"G4_N": 0.75, "G4_O": 0.25}
    assert [layer["detector_id"] for layer in all_layers] == [1, 2, 3]
    assert [layer["state"] for layer in all_layers] == ["solid", "gas", "gas"]
    assert input_plotting.surface_radius(all_layers) == 6371.0
    detector_ids, positions, edges = input_plotting.shell_coordinates(
        all_layers, [2, 3]
    )
    np.testing.assert_array_equal(detector_ids, [2, 3])
    np.testing.assert_allclose(positions, [0.5, 2.0])
    np.testing.assert_allclose(edges, [0.0, 1.0, 3.0])


def test_particle_name_translates_standard_particles_and_nuclei():
    assert input_plotting.particle_name(22) == "photon"
    assert input_plotting.particle_name(-11) == "positron"
    assert input_plotting.particle_name(1000020040) == "He-4"
    assert input_plotting.particle_name(1000260560) == "Fe-56"


def test_particle_symbol_uses_compact_pdg_notation():
    assert input_plotting.particle_symbol(22) == r"$\gamma$"
    assert input_plotting.particle_symbol(12) == r"$\nu_e$"
    assert input_plotting.particle_symbol(-11) == r"$e^{+}$"
    assert input_plotting.particle_symbol(1000020040) == r"$^{4}\mathrm{He}$"


def test_particle_groups_include_every_particle_once():
    particle_codes = np.array(
        [22, 2212, 2112, -2112, 11, -11, 1000010020, 1000030070]
    )

    groups = input_plotting._particle_groups(particle_codes)

    assert groups == ([0, 1, 2, 3, 4, 5], [6, 7])


def test_plot_inputs_writes_species_and_phantom_pngs(
    tmp_path, monkeypatch, gdml_text
):
    prepare_inputs(tmp_path, gdml_text)
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == [
        "protons.inputs.png",
        "phantom.test-phantom.inputs.png",
    ]
    assert errors == []
    for filename in filenames:
        assert (tmp_path / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_plot_inputs_reports_missing_phantom_pair_but_keeps_species_plot(
    tmp_path, monkeypatch, gdml_text
):
    prepare_inputs(tmp_path, gdml_text)
    (tmp_path / "counting_phantom0.txt").unlink()
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == ["protons.inputs.png"]
    assert errors == [
        "phantom 0 inputs: missing counting_phantom0.txt"
    ]


def test_plot_inputs_uses_numbered_name_without_phantom_metadata(
    tmp_path, monkeypatch, gdml_text
):
    prepare_inputs(tmp_path, gdml_text)
    (tmp_path / "phantoms.txt").unlink()
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == ["protons.inputs.png", "phantom-0.inputs.png"]
    assert errors == []

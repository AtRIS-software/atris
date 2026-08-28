import numpy as np

from atris_tools import input_plotting


GDML = """\
<gdml>
  <materials>
    <material name="air0" state="gas">
      <D value="1.2e-3" unit="g/cm3"/>
      <T value="290" unit="K"/>
      <P value="1.0e5" unit="Pa"/>
      <fraction n="0.75" ref="G4_N"/>
      <fraction n="0.25" ref="G4_O"/>
    </material>
    <material name="air1" state="gas">
      <D value="1.0e-4" unit="g/cm3"/>
      <T value="250" unit="K"/>
      <P value="1.0e4" unit="Pa"/>
      <fraction n="0.70" ref="G4_N"/>
      <fraction n="0.30" ref="G4_O"/>
    </material>
  </materials>
  <solids>
    <sphere name="shell0" rmin="6371" rmax="6372" lunit="km"/>
    <sphere name="shell1" rmin="6372" rmax="6374" lunit="km"/>
  </solids>
  <structure>
    <volume name="layer0">
      <materialref ref="air0"/>
      <solidref ref="shell0"/>
    </volume>
    <volume name="layer1">
      <materialref ref="air1"/>
      <solidref ref="shell1"/>
    </volume>
  </structure>
</gdml>
"""


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


def prepare_inputs(run_directory):
    (run_directory / "protons.gdml").write_text(GDML)
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


def test_read_macro_and_atmosphere(tmp_path):
    (tmp_path / "protons.mac").write_text(MACRO)
    (tmp_path / "protons.gdml").write_text(GDML)

    settings, energy_points = input_plotting.read_macro(tmp_path / "protons.mac")
    layers = input_plotting.read_atmosphere(tmp_path / "protons.gdml")

    assert settings["/gps/particle"] == "proton"
    np.testing.assert_allclose(energy_points, [[1, 0], [10, 1], [100, 1]])
    assert [layer["altitude"] for layer in layers] == [0.5, 2.0]
    assert layers[0]["fractions"] == {"G4_N": 0.75, "G4_O": 0.25}


def test_particle_name_translates_standard_particles_and_nuclei():
    assert input_plotting.particle_name(22) == "photon"
    assert input_plotting.particle_name(-11) == "positron"
    assert input_plotting.particle_name(1000020040) == "He-4"
    assert input_plotting.particle_name(1000260560) == "Fe-56"


def test_particle_groups_include_every_particle_once():
    particle_codes = np.array(
        [22, 2212, 2112, -2112, 11, -11, 1000010020, 1000030070]
    )

    groups = input_plotting._particle_groups(particle_codes)

    assert groups == ([0, 1, 2, 3, 4, 5], [6, 7])


def test_plot_inputs_writes_species_and_phantom_pngs(tmp_path, monkeypatch):
    prepare_inputs(tmp_path)
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
    tmp_path, monkeypatch
):
    prepare_inputs(tmp_path)
    (tmp_path / "counting_phantom0.txt").unlink()
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == ["protons.inputs.png"]
    assert errors == [
        "phantom 0 inputs: missing counting_phantom0.txt"
    ]


def test_plot_inputs_uses_numbered_name_without_phantom_metadata(
    tmp_path, monkeypatch
):
    prepare_inputs(tmp_path)
    (tmp_path / "phantoms.txt").unlink()
    monkeypatch.chdir(tmp_path)

    filenames, errors = input_plotting.plot_inputs()

    assert filenames == ["protons.inputs.png", "phantom-0.inputs.png"]
    assert errors == []

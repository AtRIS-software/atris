import pytest


@pytest.fixture
def gdml_text():
    return """\
<gdml>
  <materials>
    <material name="rock" state="solid">
      <D value="2.8" unit="g/cm3"/>
      <T value="290" unit="K"/>
      <P value="0" unit="Pa"/>
      <fraction n="1.0" ref="G4_Si"/>
    </material>
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
    <sphere name="termination" rmin="0" rmax="6371" lunit="km"/>
    <sphere name="shell0" rmin="6371" rmax="6372" lunit="km"/>
    <sphere name="shell1" rmin="6372" rmax="6374" lunit="km"/>
  </solids>
  <structure>
    <volume name="inner-termination">
      <materialref ref="rock"/>
      <solidref ref="termination"/>
      <auxiliary auxtype="SensDet" auxvalue="1"/>
    </volume>
    <volume name="layer0">
      <materialref ref="air0"/>
      <solidref ref="shell0"/>
      <auxiliary auxtype="SensDet" auxvalue="2"/>
    </volume>
    <volume name="layer1">
      <materialref ref="air1"/>
      <solidref ref="shell1"/>
      <auxiliary auxtype="SensDet" auxvalue="3"/>
    </volume>
  </structure>
</gdml>
"""

#ifndef DetectorConstruction_hh
#define DetectorConstruction_hh

#include "G4VUserDetectorConstruction.hh"

class G4Material;
class G4GDMLParser;

namespace atris {

class DetectorConstruction : public G4VUserDetectorConstruction
{
  public:
    explicit DetectorConstruction(const ::G4GDMLParser& parser);
    ~DetectorConstruction() override;

    void ConstructSDandField() override;
    G4VPhysicalVolume* Construct() override;

  private:
    const ::G4GDMLParser& fParser;
};

}  // namespace atris

#endif

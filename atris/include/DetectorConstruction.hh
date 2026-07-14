#ifndef DetectorConstruction_hh
#define DetectorConstruction_hh

#include "G4VUserDetectorConstruction.hh"
#include "G4Cache.hh"
#include "G4SystemOfUnits.hh"
#include "G4GenericMessenger.hh"
#include "SensitiveDetector.hh"
#include <vector>
#include <map>

class G4Material;
class G4GDMLParser;
//some of the above can probably be deleted


class DetectorConstruction : public G4VUserDetectorConstruction {
	public:
		DetectorConstruction(const G4GDMLParser& parser);
		~DetectorConstruction();

		virtual void ConstructSDandField();
		virtual G4VPhysicalVolume* Construct();

	private:
		const G4GDMLParser& fParser;
};

#endif

#include "DetectorConstruction.hh"
#include "SensitiveDetector.hh"
#include "G4GDMLParser.hh"
#include "G4Element.hh"
#include "G4Isotope.hh"
#include "G4Material.hh"
#include "G4UnitsTable.hh"
#include "G4PhysicalConstants.hh"
#include "G4SDManager.hh"
#include <map>
#include <vector>
#include "G4SystemOfUnits.hh"
#include "G4GenericMessenger.hh"
#include "G4ApplicationState.hh"

extern G4int nrofdetectors;
extern G4bool atrisverbose;

namespace atris {

DetectorConstruction::DetectorConstruction(const ::G4GDMLParser& parser)
  : G4VUserDetectorConstruction(),
    fParser(parser)
{
  G4cout << "### AtRIS: Initialized the DetectorConstruction object." << G4endl;
}

G4VPhysicalVolume* DetectorConstruction::Construct()
{
	return fParser.GetWorldVolume();
}
void DetectorConstruction::ConstructSDandField() {
	// We increase the precision of G4cout
	G4int prec = G4cout.precision(15);
	G4cout << "### AtRIS: increased precission to " << prec << " printing pi=" << pi << G4endl;
	G4cout << "### AtRIS: proceeding with Detector contruction. " << G4endl;
	G4SDManager* const SDman = G4SDManager::GetSDMpointer();
	const G4GDMLAuxMapType* const auxmap = fParser.GetAuxMap();
	// We now generate the sensitive detectors and assign them to the proper volumes
	// We also count the number of generated sensitive detectors
	for(G4GDMLAuxMapType::const_iterator iter=auxmap->begin(); iter!=auxmap->end(); iter++) {
		for (G4GDMLAuxListType::const_iterator vit=(*iter).second.begin(); vit!=(*iter).second.end();vit++) {
			if ((*vit).type=="SensDet") {
				if (atrisverbose) G4cout << "SD " << (*vit).value << " to " << ((*iter).first)->GetName() << ", ";
				G4String detname            = (*vit).value;
				G4int SDID                  = std::stoi(detname);
				SensitiveDetector* const detSD = new SensitiveDetector(detname);
				SDman->AddNewDetector( detSD);
				G4VSensitiveDetector* const mydet = SDman->FindSensitiveDetector((*vit).value);
				if(mydet) {
					G4LogicalVolume* const myvol = (*iter).first;
					myvol->SetSensitiveDetector(mydet);
					// At this point we implement the calculation of volume, mass, surface
					G4double mass     = myvol->GetMass();
					G4VSolid* const mysol = myvol->GetSolid();
					G4double surface  = mysol->GetSurfaceArea();
					G4double volume   = mysol->GetCubicVolume();
					G4double density  = mass / volume;
					// Print detector ID, mass, surface area, volume, and density.
					G4cout << "SDIDr: " << SDID << ", " << mass/kg << ", " << surface/cm2 << ", " << volume/cm3 << ", " << density/(g/cm3) << G4endl;
					// populating the dictionaries
				}
				else {
					G4cout << (*vit).value << " detector not found" << G4endl;
				}
			}
		}
	}

	// Debugging: printout the new vector data:
	G4cout << "### AtRIS: printing detailed information about all materials" << G4endl;
	if (atrisverbose) G4cout << *(G4Material::GetMaterialTable()) << G4endl;
	G4cout << "### AtRIS: gdml construction complete. In total we have " << nrofdetectors << " sensitive detectors" << G4endl;
}

DetectorConstruction::~DetectorConstruction(){
	;
}

}  // namespace atris

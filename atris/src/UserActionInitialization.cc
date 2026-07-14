#include "UserActionInitialization.hh"
#include "G4UserRunAction.hh"
#include "PrimaryGeneratorAction.hh"
#include "G4GenericAnalysisManager.hh"
#include "DetectorConstruction.hh"
#include "G4GenericAnalysisManager.hh"
#include "HistoManager.hh"

UserActionInitialization::UserActionInitialization(DetectorConstruction* detector):
 fDetector(detector){
  ;
}
UserActionInitialization::~UserActionInitialization() {
	;
}



void UserActionInitialization::BuildForMaster() const {
  G4bool newrole = true;
  G4UserRunAction* runaction = new G4UserRunAction(fDetector,newrole);
  SetUserAction(runaction);
}

void UserActionInitialization::Build() const {
  G4cout << "Starting build of UserActionInitialization for workers" << G4endl;
  G4bool newrole = false;
  G4ThreadLocal G4UserRunAction* runaction = new G4UserRunAction(fDetector,newrole);
  SetUserAction(runaction);

 
  G4cout << "Proceeding with build of UserActionInitialization for workers" << G4endl;
  G4ThreadLocal PrimaryGeneratorAction* primary = new PrimaryGeneratorAction();
  SetUserAction(primary);


}
  


#include "UserActionInitialization.hh"
#include "RunAction.hh"
#include "PrimaryGeneratorAction.hh"
#include "DetectorConstruction.hh"

namespace atris {

UserActionInitialization::UserActionInitialization(DetectorConstruction* detector)
  : fDetector(detector)
{
}

UserActionInitialization::~UserActionInitialization()
{
}



void UserActionInitialization::BuildForMaster() const
{
  auto* runaction = new RunAction(fDetector, true);
  SetUserAction(runaction);
}

void UserActionInitialization::Build() const
{
  G4cout << "Starting build of UserActionInitialization for workers" << G4endl;
  auto* runaction = new RunAction(fDetector, false);
  SetUserAction(runaction);

 
  G4cout << "Proceeding with build of UserActionInitialization for workers" << G4endl;
  auto* primary = new PrimaryGeneratorAction();
  SetUserAction(primary);
}

}  // namespace atris

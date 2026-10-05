#include "UserActionInitialization.hh"
#include "RunAction.hh"
#include "PrimaryGeneratorAction.hh"
#include "G4ios.hh"

namespace atris {

UserActionInitialization::UserActionInitialization()
{
}

UserActionInitialization::~UserActionInitialization()
{
}



void UserActionInitialization::BuildForMaster() const
{
  auto* runaction = new RunAction(true);
  SetUserAction(runaction);
}

void UserActionInitialization::Build() const
{
  G4cout << "Starting build of UserActionInitialization for workers" << G4endl;
  auto* runaction = new RunAction(false);
  SetUserAction(runaction);

 
  G4cout << "Proceeding with build of UserActionInitialization for workers" << G4endl;
  auto* primary = new PrimaryGeneratorAction();
  SetUserAction(primary);
}

}  // namespace atris

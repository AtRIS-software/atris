#ifndef RunAction_hh
#define RunAction_hh 1

#include "G4UserRunAction.hh"

class G4Run;

namespace atris {

class DetectorConstruction;
class HistoManager;

class RunAction : public ::G4UserRunAction
{
  public:
    RunAction(DetectorConstruction* detector, G4bool role);
    ~RunAction() override;

    G4Run* GenerateRun() override;
    void BeginOfRunAction(const G4Run* aRun) override;
    void EndOfRunAction(const G4Run* aRun) override;

  private:
    HistoManager* fHisto;
};

}  // namespace atris

#endif

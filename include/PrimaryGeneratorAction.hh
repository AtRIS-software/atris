#include "G4VUserPrimaryGeneratorAction.hh"
#include "G4Types.hh"

class G4GeneralParticleSource;
class G4Event;

namespace atris {

class PrimaryGeneratorAction : public G4VUserPrimaryGeneratorAction
{
  public:
    PrimaryGeneratorAction();
    ~PrimaryGeneratorAction() override;

    void GeneratePrimaries(G4Event*) override;

  private:
    G4GeneralParticleSource* ParticleGenerator;
    G4double speed;
};

}  // namespace atris

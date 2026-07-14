#ifndef UserActionInitialization_hh
#define UserActionInitialization_hh

#include "G4VUserActionInitialization.hh"

namespace atris {

class DetectorConstruction;

class UserActionInitialization : public G4VUserActionInitialization
{
  public:
    explicit UserActionInitialization(DetectorConstruction* detector);
    ~UserActionInitialization() override;

    void Build() const override;
    void BuildForMaster() const override;

  private:
    DetectorConstruction* fDetector;
};

}  // namespace atris

#endif

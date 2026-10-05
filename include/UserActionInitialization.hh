#ifndef UserActionInitialization_hh
#define UserActionInitialization_hh

#include "G4VUserActionInitialization.hh"

namespace atris {

class UserActionInitialization : public G4VUserActionInitialization
{
  public:
    UserActionInitialization();
    ~UserActionInitialization() override;

    void Build() const override;
    void BuildForMaster() const override;
};

}  // namespace atris

#endif

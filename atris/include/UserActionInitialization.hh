#ifndef UserActionInitialization_hh
#define UserActionInitialization_hh

#include "G4VUserActionInitialization.hh"

class DetectorConstruction;

class UserActionInitialization : public G4VUserActionInitialization
{
public:
    UserActionInitialization(DetectorConstruction* detector);
    virtual ~UserActionInitialization();

    void Build() const;
    void BuildForMaster() const;

private:
    DetectorConstruction* fDetector;
};

#endif

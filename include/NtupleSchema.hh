#ifndef NtupleSchema_hh
#define NtupleSchema_hh 1

#include "globals.hh"

namespace atris {

constexpr G4int interfaceNtupleId = 0;
enum InterfaceNtupleColumn : G4int {
	interfacePdg = 0,
	interfaceId,
	interfaceAngleDegrees,
	interfaceKineticEnergyMeV,
	interfacePrimaryEnergyMeV,
};

constexpr G4int stepNtupleId = 1;
enum StepNtupleColumn : G4int {
	stepEventId = 0,
	stepTrackId,
	stepParentId,
	stepId,
	stepPdg,
	stepDetectorId,
	stepPreXKm,
	stepPreYKm,
	stepPreZKm,
	stepPostXKm,
	stepPostYKm,
	stepPostZKm,
	stepPreKineticEnergyMeV,
	stepPostKineticEnergyMeV,
	stepEnergyDepositMeV,
	stepNonionizingEnergyDepositMeV,
	stepLengthM,
	stepGlobalTimeNs,
	stepPrimaryEnergyMeV,
	stepCreatorProcess,
	stepProcess,
};

}  // namespace atris

#endif

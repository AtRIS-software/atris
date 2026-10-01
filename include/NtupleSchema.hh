#ifndef NtupleSchema_hh
#define NtupleSchema_hh 1

#include "globals.hh"

namespace atris {

constexpr G4int metadataNtupleId = 0;
enum MetadataNtupleColumn : G4int {
	metadataSchema = 0,
	metadataAtrisVersion,
	metadataInputPrefix,
	metadataPhysicsList,
	metadataOutputMode,
	metadataPhantomCount,
	metadataSeedsExplicit,
	metadataRandomSeed1,
	metadataRandomSeed2,
};

constexpr G4int interfaceNtupleId = 1;
enum InterfaceNtupleColumn : G4int {
	interfacePdg = 0,
	interfaceId,
	interfaceAngleDegrees,
	interfaceKineticEnergyMeV,
	interfacePrimaryEnergyMeV,
};

constexpr G4int stepNtupleId = 2;
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

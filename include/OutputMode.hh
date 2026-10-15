#ifndef OutputMode_hh
#define OutputMode_hh 1

#include "globals.hh"

namespace atris {

// Response mode writes histograms only. Interface mode adds crossing and
// metadata ntuples; step mode also records every transport step.
constexpr G4int kResponseOutputMode = -1;
constexpr G4int kInterfaceOutputMode = 0;
constexpr G4int kStepOutputMode = 1;
// Internal phantom mode: mergeable per-bin statistics, not event records.
constexpr G4int kPhantomOutputMode = 3;

constexpr G4bool WritesMetadataNtuple(const G4int outputMode)
{
	return outputMode == kInterfaceOutputMode || outputMode == kStepOutputMode
		|| outputMode == kPhantomOutputMode;
}

constexpr G4bool WritesInterfaceNtuple(const G4int outputMode)
{
	return outputMode == kInterfaceOutputMode || outputMode == kStepOutputMode;
}

constexpr G4bool WritesStepNtuple(const G4int outputMode)
{
	return outputMode == kStepOutputMode;
}

}  // namespace atris

#endif

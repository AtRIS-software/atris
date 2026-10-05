#ifndef OutputMode_hh
#define OutputMode_hh 1

#include "globals.hh"

namespace atris {

// AtRIS output modes are part of the executable's command-line interface.
constexpr G4int kResponseOutputMode = -1;
constexpr G4int kInterfaceOutputMode = 0;
constexpr G4int kStepOutputMode = 1;

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

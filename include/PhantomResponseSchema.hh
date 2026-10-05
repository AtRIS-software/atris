#ifndef PhantomResponseSchema_hh
#define PhantomResponseSchema_hh 1

#include "globals.hh"

namespace atris {

constexpr G4int kPhantomResponseEnergyBins = 650;
constexpr G4double kPhantomResponseLogEnergyStep = 0.02;

// Common particles use a dense lookup indexed by signed PDG code. The offset
// maps the supported range [-2213, 2213] onto [0, 4426]; nuclei use their full
// ion PDG codes in a separate map.
constexpr G4int kLightParticlePDGLimit = 2214;
constexpr G4int kLightParticlePDGOffset = kLightParticlePDGLimit - 1;
constexpr G4int kLightParticleLookupSize = 2 * kLightParticlePDGOffset + 1;

// The ion response table starts with deuterons. Protons use the ordinary PDG
// code 2212 and are handled by the dense light-particle lookup above.
constexpr G4int kFirstSupportedIonPDG = 1000010020;

constexpr G4int kPhotonPDG = 22;
constexpr G4int kNeutralPionPDG = 111;
constexpr G4int kNeutronPDG = 2112;
constexpr G4int kProtonPDG = 2212;

// H2 histogram IDs are assigned in HistoManager::Book() in this order.
constexpr G4int kIonizingEnergyHistogramId = 2;
constexpr G4int kTotalEnergyHistogramId = 3;
constexpr G4int kFirstPhantomHistogramId = 4;
constexpr G4int kPhantomHistogramsPerPhantom = 3;
constexpr G4int kPhantomDoseHistogramOffset = 0;
constexpr G4int kPhantomEquivalentDoseHistogramOffset = 1;
constexpr G4int kPhantomCountingHistogramOffset = 2;

}  // namespace atris

#endif

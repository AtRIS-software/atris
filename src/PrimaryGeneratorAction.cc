#include "PrimaryGeneratorAction.hh"
#include "G4Event.hh"
#include "G4GeneralParticleSource.hh"
#include "G4AnalysisManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "G4SliceTimer.hh"
#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"
#include <chrono>
#include <ctime>

namespace atris {

PrimaryGeneratorAction::PrimaryGeneratorAction()
	: ParticleGenerator(new G4GeneralParticleSource),
	  fStartTime(static_cast<G4int>(std::time(nullptr)))
{
	G4cout << "### AtRIS: Created the particle gun." << G4endl;
}

PrimaryGeneratorAction::~PrimaryGeneratorAction(){
	;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* anEvent){
	G4AnalysisManager* const analysis = G4AnalysisManager::Instance();
	ParticleGenerator->GeneratePrimaryVertex(anEvent);  // We generate the primary particle 

	const G4int current = anEvent->GetEventID();
	if (current % 100 == 0){
		if (current != 0){
		const G4int elapsed = static_cast<G4int>(std::time(nullptr)) - fStartTime;
		const G4double speed = (G4double) current / (G4double) elapsed;
		G4cout << "Processing event: " << current << ", " <<  elapsed << " secoonds have passed. We are processing " << speed << " primaries per second."  << G4endl;
		} else {
			G4cout << "Starting primary particle generation" << G4endl;
		}
	}
	// Calculate direction
	const G4ThreeVector dir = ParticleGenerator->GetParticleMomentumDirection();
	const G4double dirtheta = dir.theta();
	G4double dirphi = dir.phi();
	if (dirphi < 0.) dirphi += twopi;
	const G4double dircost = std::cos(dirtheta);

	// Get kinetic energy
	const G4double primary_vertex_energy = ParticleGenerator->GetParticleEnergy();

	// Calculate position
	const G4ThreeVector pos = ParticleGenerator->GetParticlePosition();
	const G4double postheta = pos.theta();
	G4double posphi = pos.phi();
	if (posphi < 0.) posphi += twopi;
	const G4double poscost = std::cos(postheta);

	// now we fil the histograms
	// Unit weights preserve per-energy primary counts in CSV and ROOT output.
	analysis->FillH1(0,primary_vertex_energy);
	analysis->FillH2(0,dirphi,dircost);
	analysis->FillH2(1,posphi,poscost);
}

}  // namespace atris

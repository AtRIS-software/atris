#include "PrimaryGeneratorAction.hh"
#include "G4Event.hh"
#include "G4GeneralParticleSource.hh"
#include "G4CsvAnalysisManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "G4SliceTimer.hh"
#include "G4SystemOfUnits.hh"
#include "G4UnitsTable.hh"
#include <chrono>
#include <cstdio>
#include <time.h>

extern G4int t0;

namespace atris {

PrimaryGeneratorAction::PrimaryGeneratorAction(){
	ParticleGenerator	= new G4GeneralParticleSource;
	G4cout << "### AtRIS: Created the particle gun." << G4endl;
	speed = 1;
}

PrimaryGeneratorAction::~PrimaryGeneratorAction(){
	;
}

void PrimaryGeneratorAction::GeneratePrimaries(G4Event* anEvent){
	G4CsvAnalysisManager* analysis  = G4CsvAnalysisManager::Instance();
	ParticleGenerator->GeneratePrimaryVertex(anEvent);  // We generate the primary particle 

	G4int current  = anEvent->GetEventID();
	if (current % 100 == 0){
		if (current != 0){
		G4int elapsed = time(NULL) - t0;
		speed = (G4double) current / (G4double) elapsed;
		G4cout << "Processing event: " << current << ", " <<  elapsed << " secoonds have passed. We are processing " << speed << " primaries per second."  << G4endl;
		} else {
			G4cout << "Starting primary particle generation" << G4endl;
		}
	}
	if (current != 0 && current % 100 == 0){
		std::fprintf(stdout, "AtRIS progress: event %d\n", current);
		std::fflush(stdout);
	}

	// Calculate direction
	G4ThreeVector dir = ParticleGenerator->GetParticleMomentumDirection();
	G4double dirtheta = dir.theta(), dirphi=dir.phi();
	if (dirphi < 0.) dirphi += twopi;
	G4double dircost  = std::cos(dirtheta);

	// Get kinetic energy
	// DEACT created a local variable here
	G4double primary_vertex_energy = ParticleGenerator->GetParticleEnergy();

	// Calculate position
	G4ThreeVector pos = ParticleGenerator->GetParticlePosition();
	G4double postheta=pos.theta(), posphi=pos.phi();
	if (posphi < 0.) posphi += twopi;
	G4double poscost = std::cos(postheta);

	// now we fil the histograms
	analysis->FillH1(0,primary_vertex_energy,primary_vertex_energy);
	analysis->FillH2(0,dirphi,dircost);
	analysis->FillH2(1,posphi,poscost);
}

}  // namespace atris

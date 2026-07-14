#include "G4UserRunAction.hh"
#include "G4ParticleTable.hh"
#include "globals.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "HistoManager.hh"
#include "G4CsvAnalysisManager.hh"
#include "DetectorConstruction.hh"
#include "G4UnitsTable.hh"
#include <vector>
#include <cmath>
#include <fstream>
#include <sstream>
#include <iostream>


extern G4String outputFileName;                       // from main.cc

G4UserRunAction::G4UserRunAction(DetectorConstruction* detector, G4bool role):
	fDetector(detector),
	isMaster(role) 
{

	if(!(G4ParticleTable::GetParticleTable()->GetReadiness()))
	{
		G4String msg =  " You are instantiating G4UserRunAction BEFORE your G4VUserPhysicsList \n";
		G4Exception("G4UserRunAction::G4UserRunAction()","Run0041",FatalException,msg);
	}
}


G4UserRunAction::~G4UserRunAction(){
	if (isMaster) {
		G4cout << "### AtRIS: now writing out histograms... " << G4endl;
		G4cout << "=== MASTER: " << isMaster << G4endl;
		// At this point we implement the scaling according to mass, volume, surface area
	}
	delete G4CsvAnalysisManager::Instance();
}

G4Run* G4UserRunAction::GenerateRun(){ 
	G4cout << "### AtRIS: executing GenerateRun" << G4endl;
	G4cout << "=== MASTER: " << isMaster << G4endl;
	/*	if (isMaster){
		G4cout << "### AtRIS: Since we are in the master thread, we can configure Analysis" << G4endl;
		}
		*/
	G4Run* aRun = new G4Run;
	return aRun;
}


void G4UserRunAction::BeginOfRunAction(const G4Run* aRun){
	G4cout << "### AtRIS: executing BeginOfRunAction" << G4endl;
	G4cout << "=== MASTER: " << isMaster << G4endl;
	fHisto = new HistoManager();
	G4CsvAnalysisManager * analysis = G4CsvAnalysisManager::Instance();
	if ( analysis->IsActive() ) {
		analysis->SetFileName(outputFileName);
		analysis->OpenFile();
	}
}

void G4UserRunAction::EndOfRunAction(const G4Run*){
	G4cout << "### AtRIS: executing EndOfRunAction" << G4endl;
	auto analysis = G4CsvAnalysisManager::Instance();
	if ( analysis->IsActive() ) {
		analysis->SetVerboseLevel(1);
		analysis->Write();
		analysis->CloseFile();
		G4cout << "### AtRIS: histograms written, closed. " << G4endl;
	}

}

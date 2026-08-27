#include "RunAction.hh"
#include "G4ParticleTable.hh"
#include "G4Run.hh"
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

namespace atris {

RunAction::RunAction(DetectorConstruction* detector, G4bool role)
  : fHisto(nullptr)
{
  (void)detector;
  SetMaster(role);

  if (!(G4ParticleTable::GetParticleTable()->GetReadiness()))
  {
    G4String msg = " You are instantiating RunAction BEFORE your G4VUserPhysicsList \n";
    G4Exception("atris::RunAction::RunAction()", "Run0041", FatalException, msg);
  }
}


RunAction::~RunAction()
{
  if (IsMaster()) {
    G4cout << "### AtRIS: now writing out histograms... " << G4endl;
    G4cout << "=== MASTER: " << IsMaster() << G4endl;
    // At this point we implement the scaling according to mass, volume, surface area
  }
  delete fHisto;
}

G4Run* RunAction::GenerateRun()
{
  G4cout << "### AtRIS: executing GenerateRun" << G4endl;
  G4cout << "=== MASTER: " << IsMaster() << G4endl;
  /*
  if (IsMaster()) {
    G4cout << "### AtRIS: Since we are in the master thread, we can configure Analysis" << G4endl;
  }
  */
  return new G4Run;
}


void RunAction::BeginOfRunAction(const G4Run*)
{
  G4cout << "### AtRIS: executing BeginOfRunAction" << G4endl;
  G4cout << "=== MASTER: " << IsMaster() << G4endl;
  fHisto = new HistoManager();
  G4CsvAnalysisManager* analysis = G4CsvAnalysisManager::Instance();
  if (analysis->IsActive()) {
    analysis->SetFileName(outputFileName);
    analysis->OpenFile();
  }
}

void RunAction::EndOfRunAction(const G4Run*)
{
  G4cout << "### AtRIS: executing EndOfRunAction" << G4endl;
  auto analysis = G4CsvAnalysisManager::Instance();
  if (analysis->IsActive()) {
    analysis->SetVerboseLevel(1);
    analysis->Write();
    analysis->CloseFile();
    G4cout << "### AtRIS: histograms written, closed. " << G4endl;
  }
}

}  // namespace atris

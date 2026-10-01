#include "RunAction.hh"
#include "G4ParticleTable.hh"
#include "G4Run.hh"
#include "globals.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4PhysicalConstants.hh"
#include "HistoManager.hh"
#include "G4AnalysisManager.hh"
#include "DetectorConstruction.hh"
#include "G4UnitsTable.hh"
#include <vector>
#include <cmath>
#include <fstream>
#include <sstream>
#include <iostream>


extern G4String outputFileName;                       // from src/main.cc
extern G4int mode;

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
  return new G4Run;
}


void RunAction::BeginOfRunAction(const G4Run*)
{
  G4cout << "### AtRIS: executing BeginOfRunAction" << G4endl;
  G4cout << "=== MASTER: " << IsMaster() << G4endl;
  G4AnalysisManager* analysis = G4AnalysisManager::Instance();
  const G4bool writesRoot = mode == 0 || mode == 1;
  analysis->SetDefaultFileType(writesRoot ? "root" : "csv");
  if (writesRoot) analysis->SetNtupleMerging(true);
  fHisto = new HistoManager();
  if (analysis->IsActive()) {
    analysis->SetFileName(outputFileName);
    analysis->OpenFile();
    fHisto->FillMetadata();
  }
}

void RunAction::EndOfRunAction(const G4Run*)
{
  G4cout << "### AtRIS: executing EndOfRunAction" << G4endl;
  auto analysis = G4AnalysisManager::Instance();
  if (analysis->IsActive()) {
    analysis->SetVerboseLevel(1);
    analysis->Write();
    analysis->CloseFile();
    G4cout << "### AtRIS: histograms written, closed. " << G4endl;
  }
}

}  // namespace atris

#include "HistoManager.hh"
#include "NtupleSchema.hh"
#include "G4AnalysisManager.hh"
#include "G4UnitsTable.hh"
#include "DetectorConstruction.hh"
#include "G4SDManager.hh"
#include "G4PhysicalConstants.hh"
#include "G4SystemOfUnits.hh"
#include <vector>
#include <string>
#include <math.h>
#include <iostream>
#include <iterator>
#include <fstream>
#include <algorithm>

extern G4int nrofdetectors;
extern G4String binedgesFile;
extern std::vector<G4double> enbins;
extern std::vector<G4double> detbins;
extern G4int nrphantoms;
extern G4int mode;
extern G4String outputFileName;

namespace atris {

HistoManager::HistoManager()
	: fFileName("exgps")
{
	Book();
}

HistoManager::~HistoManager()
{
	G4cout << "HistoManager deleted." << G4endl;
}

void HistoManager::Book()
{
	G4AnalysisManager* analysis = G4AnalysisManager::Instance();
	// This code replaces the HistoManager.cc
	G4cout << "### AtRIS: configuring analysis histograms. " << G4endl;
	analysis->SetVerboseLevel(0);
	analysis->SetActivation(true);     //enable inactivation of histos, nTuples
	auto setH1FileName = [analysis](G4int histogramId, const G4String& name) {
		if (mode == 0 || mode == 1) {
			analysis->SetH1FileName(
				histogramId,
				outputFileName + "_h1_" + name + ".csv"
			);
		}
	};
	auto setH2FileName = [analysis](G4int histogramId, const G4String& name) {
		if (mode == 0 || mode == 1) {
			analysis->SetH2FileName(
				histogramId,
				outputFileName + "_h2_" + name + ".csv"
			);
		}
	};
	G4int    id   = analysis->CreateH1("h1.1","kinetic energy", enbins, "MeV");
	analysis->SetH1Activation(id, true);
	setH1FileName(id, "h1.1");
	// This is the direction histogram
	G4int    dir_nbinx = 120;
	G4int    dir_nbiny = 60 ;
	G4double dir_vminx = 0.;
	G4double dir_vmaxx = twopi;
	G4double dir_vminy = 0.;
	G4double dir_vmaxy = 1.;
	id = analysis->CreateH2("h2.dir","source direction: phi,cos(theta)",
			dir_nbinx,dir_vminx,dir_vmaxx,dir_nbiny,dir_vminy,dir_vmaxy);
	analysis->SetH2Activation(id,true);
	setH2FileName(id, "h2.dir");
	// This is the position histogram.
	G4int    pos_nbinx = 120;
	G4int    pos_nbiny = 60 ;
	G4double pos_vminx = 0.;
	G4double pos_vmaxx = twopi;
	G4double pos_vminy = 0.;
	G4double pos_vmaxy = 1.;
	id = analysis->CreateH2("h2.pos","source position: phi,cos(theta)",
			pos_nbinx,pos_vminx,pos_vmaxx,pos_nbiny,pos_vminy,pos_vmaxy);
	analysis->SetH2Activation(id,true);
	setH2FileName(id, "h2.pos");
	// Now we activate the phantom histograms, 3 per phantom
	// This is the new ionization energy histogram, it gets the ID 2
	id = analysis->CreateH2("h2.ion","ionization: input energy,SID",enbins,detbins,"MeV","none","none","none");
	analysis->SetH2Activation(id,true);
	setH2FileName(id, "h2.ion");
	for (G4int phantomnr = 0; phantomnr < nrphantoms; phantomnr++){
		G4cout << "### AtRIS: Initializing higher order histograms for " << nrphantoms << " phantoms, with a total number of histograms equal to " << nrphantoms*3 + 4 <<G4endl;
		// For the DIID, we need less detbins, but we will keep this here and remove it latter when writing out the custom output
		G4String sufix = std::to_string(phantomnr);
		id = analysis->CreateH2("h2.dos"+sufix,"absorbed dose rate in a spherical water phatnom: input energy,SID",enbins,detbins,"MeV","none","none","none");
		analysis->SetH2Activation(id,true);
		setH2FileName(id, "h2.dos" + sufix);
		// same as above, but only for the equivalent dose rate
		id = analysis->CreateH2("h2.equi"+sufix,"equivalent absorbed dose rate in a spherical water phatnom: input energy,SID",enbins,detbins,"MeV","none","none","none");
		analysis->SetH2Activation(id,true);
		setH2FileName(id, "h2.equi" + sufix);
		// a histogram to hold the count rates if the first phantom
		id = analysis->CreateH2("h2.rates"+sufix,"Count rates in the first phantom rate,SID",enbins,detbins,"MeV","none","none","none");
		analysis->SetH2Activation(id,true);
		setH2FileName(id, "h2.rates" + sufix);

	}

	if (mode != 0 && mode != 1) return;

	id = analysis->CreateNtuple(
		"interfaces",
		"Particle crossings at layer interfaces"
	);
	analysis->CreateNtupleIColumn(id, "pdg");
	analysis->CreateNtupleIColumn(id, "interface_id");
	analysis->CreateNtupleIColumn(id, "angle_degrees");
	analysis->CreateNtupleDColumn(id, "kinetic_energy_MeV");
	analysis->CreateNtupleDColumn(id, "primary_energy_MeV");
	analysis->FinishNtuple(id);
	if (mode != 1) return;

	id = analysis->CreateNtuple("steps", "Particle transport steps");
	analysis->CreateNtupleIColumn(id, "event_id");
	analysis->CreateNtupleIColumn(id, "track_id");
	analysis->CreateNtupleIColumn(id, "parent_id");
	analysis->CreateNtupleIColumn(id, "step_id");
	analysis->CreateNtupleIColumn(id, "pdg");
	analysis->CreateNtupleIColumn(id, "detector_id");
	analysis->CreateNtupleDColumn(id, "pre_x_km");
	analysis->CreateNtupleDColumn(id, "pre_y_km");
	analysis->CreateNtupleDColumn(id, "pre_z_km");
	analysis->CreateNtupleDColumn(id, "post_x_km");
	analysis->CreateNtupleDColumn(id, "post_y_km");
	analysis->CreateNtupleDColumn(id, "post_z_km");
	analysis->CreateNtupleDColumn(id, "pre_kinetic_energy_MeV");
	analysis->CreateNtupleDColumn(id, "post_kinetic_energy_MeV");
	analysis->CreateNtupleDColumn(id, "energy_deposit_MeV");
	analysis->CreateNtupleDColumn(id, "nonionizing_energy_deposit_MeV");
	analysis->CreateNtupleDColumn(id, "step_length_m");
	analysis->CreateNtupleDColumn(id, "global_time_ns");
	analysis->CreateNtupleDColumn(id, "primary_energy_MeV");
	analysis->CreateNtupleSColumn(id, "creator_process");
	analysis->CreateNtupleSColumn(id, "step_process");
	analysis->FinishNtuple(id);

}

}  // namespace atris

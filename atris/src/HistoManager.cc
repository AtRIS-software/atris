#include "HistoManager.hh"
#include "G4CsvAnalysisManager.hh"
#include "G4UnitsTable.hh"
#include "DetectorConstruction.hh"
#include "G4SDManager.hh"
#include "G4PhysicalConstants.hh"
#include "G4SystemOfUnits.hh"
#include "G4UserRunAction.hh"
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
	G4CsvAnalysisManager* analysis = G4CsvAnalysisManager::Instance();
	// This code replaces the HistoManager.cc
	G4cout << "### AtRIS: configuring analysis histograms. " << G4endl;
	analysis->SetVerboseLevel(0);
	analysis->SetActivation(true);     //enable inactivation of histos, nTuples
	G4int    id   = analysis->CreateH1("h1.1","kinetic energy", enbins, "MeV");
	analysis->SetH1Activation(id, true);
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
	// Now we activate the phantom histograms, 3 per phantom
	// This is the new ionization energy histogram, it gets the ID 2
	id = analysis->CreateH2("h2.ion","ionization: input energy,SID",enbins,detbins,"MeV","none","none","none");
	analysis->SetH2Activation(id,true);
	for (G4int phantomnr = 0; phantomnr < nrphantoms; phantomnr++){
		G4cout << "### AtRIS: Initializing higher order histograms for " << nrphantoms << " phantoms, with a total number of histograms equal to " << nrphantoms*3 + 4 <<G4endl;
		// For the DIID, we need less detbins, but we will keep this here and remove it latter when writing out the custom output
		G4String sufix = std::to_string(phantomnr);
		id = analysis->CreateH2("h2.dos"+sufix,"absorbed dose rate in a spherical water phatnom: input energy,SID",enbins,detbins,"MeV","none","none","none");
		analysis->SetH2Activation(id,true);
		// same as above, but only for the equivalent dose rate
		id = analysis->CreateH2("h2.equi"+sufix,"equivalent absorbed dose rate in a spherical water phatnom: input energy,SID",enbins,detbins,"MeV","none","none","none");
		analysis->SetH2Activation(id,true);
		// a histogram to hold the count rates if the first phantom
		id = analysis->CreateH2("h2.rates"+sufix,"Count rates in the first phantom rate,SID",enbins,detbins,"MeV","none","none","none");
		analysis->SetH2Activation(id,true);

	}

}

#include "HistoManager.hh"
#include "G4CsvAnalysisManager.hh"
#include "G4UnitsTable.hh"
#include "DetectorConstruction.hh"
#include "G4SDManager.hh"
#include "G4PhysicalConstants.hh"
#include "G4SystemOfUnits.hh"
#include <array>
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
extern G4String simulationInputPrefix;
extern G4String physicsListName;
extern G4bool hasExplicitSeeds;
extern std::array<G4long, 2> explicitSeeds;

namespace {

template <typename Histogram>
void AnnotateHistogram(
	Histogram* histogram,
	const G4String& name,
	const G4String& quantity,
	const G4String& accumulatedWeight
)
{
	if (histogram == nullptr) return;
	histogram->add_annotation("atris.csv_schema", "1");
	histogram->add_annotation("atris.version", ATRIS_VERSION);
	histogram->add_annotation("atris.histogram_name", name);
	histogram->add_annotation("atris.quantity", quantity);
	histogram->add_annotation("atris.accumulated_weight", accumulatedWeight);
	histogram->add_annotation("atris.input_prefix", simulationInputPrefix);
	histogram->add_annotation("atris.physics_list", physicsListName);
	histogram->add_annotation("atris.output_mode", std::to_string(mode));
	histogram->add_annotation("atris.phantom_count", std::to_string(nrphantoms));
	if (hasExplicitSeeds) {
		histogram->add_annotation(
			"atris.random_seed_pairs",
			std::to_string(explicitSeeds[0]) + ":" + std::to_string(explicitSeeds[1])
		);
	} else {
		histogram->add_annotation("atris.random_seed_pairs", "runtime-default");
	}
}

}  // namespace

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
	G4CsvAnalysisManager* analysis = G4CsvAnalysisManager::Instance();
	// This code replaces the HistoManager.cc
	G4cout << "### AtRIS: configuring analysis histograms. " << G4endl;
	analysis->SetVerboseLevel(0);
	analysis->SetActivation(true);     //enable inactivation of histos, nTuples
	G4int id = analysis->CreateH1("h1.1", "Primary kinetic energy", enbins, "MeV");
	auto primaryEnergy = analysis->GetH1(id);
	AnnotateHistogram(
		primaryEnergy,
		"h1.1",
		"primary kinetic energy distribution",
		"primary kinetic energy [MeV]"
	);
	analysis->SetH1XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH1YAxisTitle(id, "Accumulated primary kinetic energy [MeV]");
	analysis->SetH1Activation(id, true);
	// This is the direction histogram
	G4int    dir_nbinx = 120;
	G4int    dir_nbiny = 60 ;
	G4double dir_vminx = 0.;
	G4double dir_vmaxx = twopi;
	G4double dir_vminy = 0.;
	G4double dir_vmaxy = 1.;
	id = analysis->CreateH2("h2.dir", "Primary source direction",
				dir_nbinx,dir_vminx,dir_vmaxx,dir_nbiny,dir_vminy,dir_vmaxy);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.dir",
		"primary source direction",
		"primary count"
	);
	analysis->SetH2XAxisTitle(id, "Global azimuth phi [rad]");
	analysis->SetH2YAxisTitle(id, "Cosine of global polar angle");
	analysis->SetH2ZAxisTitle(id, "Primary count");
	analysis->SetH2Activation(id,true);
	// This is the position histogram.
	G4int    pos_nbinx = 120;
	G4int    pos_nbiny = 60 ;
	G4double pos_vminx = 0.;
	G4double pos_vmaxx = twopi;
	G4double pos_vminy = 0.;
	G4double pos_vmaxy = 1.;
	id = analysis->CreateH2("h2.pos", "Primary source position",
				pos_nbinx,pos_vminx,pos_vmaxx,pos_nbiny,pos_vminy,pos_vmaxy);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.pos",
		"primary source position",
		"primary count"
	);
	analysis->SetH2XAxisTitle(id, "Global azimuth phi [rad]");
	analysis->SetH2YAxisTitle(id, "Cosine of global polar angle");
	analysis->SetH2ZAxisTitle(id, "Primary count");
	analysis->SetH2Activation(id,true);
	// Now we activate the phantom histograms, 3 per phantom
	// This is the new ionization energy histogram, it gets the ID 2
	id = analysis->CreateH2(
		"h2.ion", "Ionizing energy deposition", enbins, detbins,
		"MeV", "none", "none", "none"
	);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.ion",
		"ionizing energy deposition",
		"total energy deposit minus non-ionizing energy deposit [MeV]"
	);
	analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH2YAxisTitle(id, "Sensitive detector ID");
	analysis->SetH2ZAxisTitle(id, "Ionizing energy deposited [MeV]");
	analysis->SetH2Activation(id,true);
	for (G4int phantomnr = 0; phantomnr < nrphantoms; phantomnr++){
		G4cout << "### AtRIS: Initializing higher order histograms for " << nrphantoms << " phantoms, with a total number of histograms equal to " << nrphantoms*3 + 4 <<G4endl;
		// For the DIID, we need less detbins, but we will keep this here and remove it latter when writing out the custom output
		G4String suffix = std::to_string(phantomnr);
		id = analysis->CreateH2(
			"h2.dos" + suffix, "Phantom energy response", enbins, detbins,
			"MeV", "none", "none", "none"
		);
		auto dose = analysis->GetH2(id);
		AnnotateHistogram(
			dose,
			"h2.dos" + suffix,
			"phantom energy response",
			"response coefficient times crossing kinetic energy [eV]"
		);
		if (dose != nullptr) dose->add_annotation("atris.phantom_id", suffix);
		analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
		analysis->SetH2YAxisTitle(id, "Interface ID");
		analysis->SetH2ZAxisTitle(id, "Phantom energy-response weight [eV]");
		analysis->SetH2Activation(id,true);
		// same as above, but only for the equivalent dose rate
		id = analysis->CreateH2(
			"h2.equi" + suffix, "Radiation-weighted phantom energy response",
			enbins, detbins, "MeV", "none", "none", "none"
		);
		auto equivalentDose = analysis->GetH2(id);
		AnnotateHistogram(
			equivalentDose,
			"h2.equi" + suffix,
			"radiation-weighted phantom energy response",
			"response coefficient times crossing kinetic energy and radiation weight [eV]"
		);
		if (equivalentDose != nullptr) {
			equivalentDose->add_annotation("atris.phantom_id", suffix);
		}
		analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
		analysis->SetH2YAxisTitle(id, "Interface ID");
		analysis->SetH2ZAxisTitle(id, "Radiation-weighted phantom energy-response weight [eV]");
		analysis->SetH2Activation(id,true);
		// a histogram to hold the count rates if the first phantom
		id = analysis->CreateH2(
			"h2.rates" + suffix, "Phantom counting response", enbins, detbins,
			"MeV", "none", "none", "none"
		);
		auto countRate = analysis->GetH2(id);
		AnnotateHistogram(
			countRate,
			"h2.rates" + suffix,
			"phantom counting response",
			"counting response coefficient"
		);
		if (countRate != nullptr) countRate->add_annotation("atris.phantom_id", suffix);
		analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
		analysis->SetH2YAxisTitle(id, "Interface ID");
		analysis->SetH2ZAxisTitle(id, "Counting-response weight");
		analysis->SetH2Activation(id,true);

	}

}

}  // namespace atris

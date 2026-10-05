#include "HistoManager.hh"
#include "NtupleSchema.hh"
#include "G4AnalysisManager.hh"
#include "G4Threading.hh"
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

const G4int SOURCE_AZIMUTH_BINS = 120;
const G4int SOURCE_COSINE_BINS = 60;
const G4double SOURCE_AZIMUTH_MIN = 0.;
const G4double SOURCE_AZIMUTH_MAX = twopi;
const G4double SOURCE_COSINE_MIN = -1.;
const G4double SOURCE_COSINE_MAX = 1.;

template <typename Histogram>
void AnnotateHistogram(
	Histogram* const histogram,
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
{
	Book();
}

HistoManager::~HistoManager()
{
	G4cout << "HistoManager deleted." << G4endl;
}

void HistoManager::Book() const
{
	G4AnalysisManager* const analysis = G4AnalysisManager::Instance();
	// This code replaces the HistoManager.cc
	G4cout << "### AtRIS: configuring analysis histograms. " << G4endl;
	analysis->SetVerboseLevel(0);
	analysis->SetActivation(true);     //enable inactivation of histos, nTuples
	G4int id = analysis->CreateH1("h1.1", "Primary kinetic energy", enbins, "MeV");
	auto* const primaryEnergy = analysis->GetH1(id);
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
	id = analysis->CreateH2("h2.dir", "Primary source direction",
				SOURCE_AZIMUTH_BINS, SOURCE_AZIMUTH_MIN, SOURCE_AZIMUTH_MAX,
				SOURCE_COSINE_BINS, SOURCE_COSINE_MIN, SOURCE_COSINE_MAX);
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
	id = analysis->CreateH2("h2.pos", "Primary source position",
				SOURCE_AZIMUTH_BINS, SOURCE_AZIMUTH_MIN, SOURCE_AZIMUTH_MAX,
				SOURCE_COSINE_BINS, SOURCE_COSINE_MIN, SOURCE_COSINE_MAX);
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
	// Total local energy deposition, retained separately so that atmospheric
	// heating estimates do not have to rely on the ionizing component alone.
	id = analysis->CreateH2(
		"h2.edep", "Total energy deposition", enbins, detbins,
		"MeV", "none", "none", "none"
	);
	AnnotateHistogram(
		analysis->GetH2(id),
		"h2.edep",
		"total energy deposition",
		"total energy deposit [MeV]"
	);
	analysis->SetH2XAxisTitle(id, "Primary kinetic energy [MeV]");
	analysis->SetH2YAxisTitle(id, "Sensitive detector ID");
	analysis->SetH2ZAxisTitle(id, "Total energy deposited [MeV]");
	analysis->SetH2Activation(id,true);
	for (G4int phantomnr = 0; phantomnr < nrphantoms; phantomnr++){
		G4cout << "### AtRIS: Initializing higher order histograms for " << nrphantoms << " phantoms, with a total number of histograms equal to " << nrphantoms*3 + 5 <<G4endl;
		// For the DIID, we need less detbins, but we will keep this here and remove it latter when writing out the custom output
		const G4String suffix = std::to_string(phantomnr);
		id = analysis->CreateH2(
			"h2.dos" + suffix, "Phantom energy response", enbins, detbins,
			"MeV", "none", "none", "none"
		);
		auto* const dose = analysis->GetH2(id);
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
		auto* const equivalentDose = analysis->GetH2(id);
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
		auto* const countRate = analysis->GetH2(id);
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

	if (mode != 0 && mode != 1) return;

	id = analysis->CreateNtuple("metadata", "AtRIS output metadata");
	analysis->CreateNtupleIColumn(id, "schema");
	analysis->CreateNtupleSColumn(id, "atris_version");
	analysis->CreateNtupleSColumn(id, "input_prefix");
	analysis->CreateNtupleSColumn(id, "physics_list");
	analysis->CreateNtupleIColumn(id, "output_mode");
	analysis->CreateNtupleIColumn(id, "phantom_count");
	analysis->CreateNtupleIColumn(id, "seeds_explicit");
	analysis->CreateNtupleIColumn(id, "random_seed_1");
	analysis->CreateNtupleIColumn(id, "random_seed_2");
	analysis->FinishNtuple(id);
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

void HistoManager::FillMetadata() const
{
	if (mode != 0 && mode != 1) return;
	// One worker records the shared run metadata while Geant4 merges all ntuples.
	if (G4Threading::G4GetThreadId() != 0) return;
	auto* const analysis = G4AnalysisManager::Instance();
	analysis->FillNtupleIColumn(metadataNtupleId, metadataSchema, 1);
	analysis->FillNtupleSColumn(
		metadataNtupleId, metadataAtrisVersion, ATRIS_VERSION
	);
	analysis->FillNtupleSColumn(
		metadataNtupleId, metadataInputPrefix, simulationInputPrefix
	);
	analysis->FillNtupleSColumn(
		metadataNtupleId, metadataPhysicsList, physicsListName
	);
	analysis->FillNtupleIColumn(metadataNtupleId, metadataOutputMode, mode);
	analysis->FillNtupleIColumn(
		metadataNtupleId, metadataPhantomCount, nrphantoms
	);
	analysis->FillNtupleIColumn(
		metadataNtupleId, metadataSeedsExplicit, hasExplicitSeeds
	);
	analysis->FillNtupleIColumn(
		metadataNtupleId, metadataRandomSeed1, explicitSeeds[0]
	);
	analysis->FillNtupleIColumn(
		metadataNtupleId, metadataRandomSeed2, explicitSeeds[1]
	);
	analysis->AddNtupleRow(metadataNtupleId);
}

}  // namespace atris

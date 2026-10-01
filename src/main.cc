#include "G4RunManager.hh"
#include "G4MTRunManager.hh"
#include "G4Threading.hh"
#include "G4UImanager.hh"
#include "G4GDMLParser.hh"

#include "DetectorConstruction.hh"
#include "UserActionInitialization.hh"
#include "Randomize.hh"
#include "G4PhysListFactory.hh"
#include "G4StepLimiterPhysics.hh"
#include <array>
#include <vector>
#include <string>
#include <cstddef>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <fstream>
#include <sstream>

G4String outputFileName;
G4String simulationInputPrefix;
G4String physicsListName;
G4int    mode = -1;
G4int    nrofdetectors=0;
G4bool   hasExplicitSeeds = false;
std::array<G4long, 2> explicitSeeds = {0, 0};

// For holding phantom responses
G4int nrphantoms;
std::vector<G4int> useornot(4427,0);
std::map<G4int, G4int> heavy;
std::vector<std::vector<G4double>> abso;
std::vector<std::vector<G4double>> rate;

std::vector<G4double> enbins;
std::vector<G4double> detbins;
G4int t0 = static_cast<G4int>(std::time(nullptr));

G4bool atrisverbose = false;



// Functions used by main.
G4bool Phantoms(G4int howmany);
void determine_nrofdetectors(G4String fname);

struct SimulationRun {
	G4String inputPrefix;
	std::array<G4long, 3> seeds = {0, 0, 0}; // CLHEP expects two seeds followed by a zero terminator.
	G4bool hasSeeds = false;
};

SimulationRun parseSimulationRun(const G4String& argument) {
	SimulationRun run;
	std::string path = argument.c_str();
	std::size_t pathSeparator = path.find_last_of("/\\");
	std::size_t extensionSeparator = path.find_last_of('.');
	if (
		extensionSeparator != std::string::npos
		&& (pathSeparator == std::string::npos || extensionSeparator > pathSeparator)
	) {
		path.erase(extensionSeparator);
	}
	run.inputPrefix = path;
	pathSeparator = path.find_last_of("/\\");
	std::string name = pathSeparator == std::string::npos
	                     ? path
	                     : path.substr(pathSeparator + 1);
	std::size_t secondSeparator = name.rfind('_');
	if (secondSeparator == std::string::npos) return run;
	std::size_t firstSeparator = name.rfind('_', secondSeparator - 1);
	if (firstSeparator == std::string::npos || firstSeparator == 0) return run;

	std::string firstSeed = name.substr(firstSeparator + 1, secondSeparator - firstSeparator - 1);
	std::string secondSeed = name.substr(secondSeparator + 1);
	if (firstSeed.size() != 6 || secondSeed.size() != 6) return run;
	if (firstSeed.find_first_not_of("0123456789") != std::string::npos) return run;
	if (secondSeed.find_first_not_of("0123456789") != std::string::npos) return run;

	run.inputPrefix = name.substr(0, firstSeparator);
	run.seeds[0] = std::stol(firstSeed);
	run.seeds[1] = std::stol(secondSeed);
	run.hasSeeds = true;
	return run;
}



int main(int argc,char** argv){
	if (argc == 2 && std::string(argv[1]) == "--version") {
		std::cout << "AtRIS " << ATRIS_VERSION << '\n';
		return 0;
	}
	if (argc != 5){
		G4cout << "Usage: " << argv[0]
		       << " <physics-list> <simulation-name> <mode> <phantom-count>" << G4endl;
		return 0;
	}
	const auto totalStart = std::chrono::steady_clock::now();
	mode = std::stoi(argv[3]);
	nrphantoms = std::stoi(argv[4]);
	// The simulation name selects the geometry, energy bins, and macro inputs;
	// the phantom count selects the numbered radiation and counting responses.
	if (!Phantoms(nrphantoms)) return 1;
	SimulationRun simulation = parseSimulationRun(argv[2]);
	outputFileName    = argv[2];
	simulationInputPrefix = simulation.inputPrefix;
	hasExplicitSeeds = simulation.hasSeeds;
	if (simulation.hasSeeds) {
		explicitSeeds[0] = simulation.seeds[0];
		explicitSeeds[1] = simulation.seeds[1];
	}
	G4String gdmlname = simulation.inputPrefix+".gdml";
	determine_nrofdetectors(gdmlname);
	G4cout << "### AtRIS: Generating detbins with the determined number of detectors" << G4endl;
	for(int i=0;i<=nrofdetectors;i++){
		detbins.push_back(i-0.5);
	}
	// Create the enbinsa for the histograms
	G4String binedgesFile = simulation.inputPrefix+".bins";
	G4double newbinedge = 0;
	std::ifstream is(binedgesFile);
	G4int j=0;
	while (is >> newbinedge){
		enbins.push_back(newbinedge);
		j++;
	}
	G4cout << "### AtRIS: read " << j  << " binedges." << G4endl;

	// The log files could be necessary for the data analysis.
	// Therefore, we redirect them to a file. 
	G4UImanager * UImanager	= G4UImanager::GetUIpointer();
	G4Random::setTheEngine(new CLHEP::MTwistEngine); // Choose the Random engine
	G4MTRunManager *runManager = new G4MTRunManager;   // Instantiate the run manager
	if (simulation.hasSeeds) {
		G4Random::setTheSeeds(simulation.seeds.data());
		G4cout << "### AtRIS: using random seeds " << simulation.seeds[0]
		       << " and " << simulation.seeds[1] << G4endl;
	}
	if (std::getenv("G4FORCENUMBEROFTHREADS") == nullptr) {
		runManager->SetNumberOfThreads(G4Threading::G4GetNumberOfCores());
	}
	G4GDMLParser parser;                             //instantiate a GDML parser
	parser.Read(gdmlname);	 //parse the 
	atris::DetectorConstruction* detector = new atris::DetectorConstruction(parser);
	runManager->SetUserInitialization(detector);
	G4String physics = argv[1]; 			 //Setting up the physics list
	physicsListName = physics;
	G4PhysListFactory factory;                       // initialize physics list
	if (factory.IsReferencePhysList(physics) or (factory.IsReferencePhysList(physics.substr(0,physics.size()-4)))) {
		G4VModularPhysicsList* physlist = factory.GetReferencePhysList(physics);
		physlist->RegisterPhysics(new G4StepLimiterPhysics());
		runManager->SetUserInitialization(physlist);
	} else {
		G4cout << "### AtRIS: " << physics << " is not valid! use: "<<G4endl;
		std::vector<G4String> available = factory.AvailablePhysLists();
		for (std::size_t i = 0; i < available.size(); ++i){
			G4cout << available[i] << G4endl;
		}
		return -1;
	}
	if (mode == 0) {
		G4cout << "### AtRIS: mode 0 writes histograms and interface ntuples to "
		       << outputFileName << G4endl;
	}
	if (mode == 1) {
		G4cout << "### AtRIS: mode 1 writes histograms, interface, and transport-step ntuples to "
		       << outputFileName << "; output may be very large" << G4endl;
	}

	atris::UserActionInitialization* useract = new atris::UserActionInitialization(detector);
	runManager->SetUserInitialization(useract);


	// Get the pointer to the user interface manager and start the batch mode
	G4String macroName = simulation.inputPrefix+".mac";
	if (simulation.hasSeeds) {
		G4String chunkMacroName = simulation.inputPrefix+".chunk.mac";
		std::ifstream chunkMacro(chunkMacroName);
		if (chunkMacro.good()) macroName = chunkMacroName;
	}
	G4String tempString = "/control/execute "+macroName;
	G4cout << "### AtRIS: executing macro " << macroName << G4endl;
	G4cout << "### AtRIS: Starting the simulation " << G4endl;
	const auto macroStart = std::chrono::steady_clock::now();
	G4int commandStatus = UImanager->ApplyCommand(tempString);
	const auto macroEnd = std::chrono::steady_clock::now();
	const G4int workerThreads = runManager->GetNumberOfThreads();
	G4cout << "### AtRIS: simulation used " << workerThreads << " worker thread(s)" << G4endl;
	if (commandStatus == 0) {
		G4cout << "### AtRIS: the simulation has completed " << G4endl;
	} else {
		G4cerr << "### AtRIS: macro execution failed with Geant4 status " << commandStatus << G4endl;
	}
	delete runManager;
	const auto totalEnd = std::chrono::steady_clock::now();
	const double macroSeconds =
		std::chrono::duration<double>(macroEnd - macroStart).count();
	const double totalSeconds =
		std::chrono::duration<double>(totalEnd - totalStart).count();
	std::ostringstream timingOutput;
	timingOutput << std::fixed << std::setprecision(3)
		<< "### AtRIS timing: Geant4 macro wall time: " << macroSeconds
		<< " s using " << workerThreads << " worker thread(s)\n"
		<< "### AtRIS timing: setup/cleanup wall time: "
		<< totalSeconds - macroSeconds << " s\n"
		<< "### AtRIS timing: total wall time: " << totalSeconds << " s";
	G4cout << timingOutput.str() << G4endl;
	if (commandStatus == 0) {
		G4cout << "### AtRIS: Run completed successfully." << G4endl;
	} else {
		G4cerr << "### AtRIS: Run failed." << G4endl;
	}
	return commandStatus == 0 ? 0 : 1;
}

void determine_nrofdetectors(G4String fname){
	// One approach is to get it as an additional argument
	// Better: open the gdml file, count "<auxiliary", this is the number of sensitive detectors
	G4String line_of_text;
	G4String auxvalue = "<auxiliary";
	G4String temp2;
	std::ifstream is(fname);
	while (std::getline(is, line_of_text)) {
		std::stringstream ss(line_of_text);
		while (ss >> temp2) {
			if (temp2 == auxvalue) nrofdetectors +=1;
			if (temp2 == "</gdml>") return;
		}
	}
	G4cout << "### AtRIS: nrofdetectors has been determined to be: " << nrofdetectors << G4endl;
}

G4bool Phantoms(G4int howmany){
	G4int expected = 0; 
	std::vector<G4int> expected_pdgs;
	G4String expected_header_name;
	G4cout << "### AtRIS: proceeding to load " << howmany << " phantom(s)." << G4endl << std::flush;
	for (G4int phantom_index=0; phantom_index < howmany; phantom_index++){
		std::vector<G4double> icru;
		G4String phantom_name = "radiation_phantom" + std::to_string(phantom_index) + ".txt";
		G4cout << "### AtRIS: loading radiation response matrix for phantom " << phantom_index << " from " << phantom_name << G4endl << std::flush;
		std::ifstream is(phantom_name);
		if (!is.is_open()) {
			G4cerr << "### AtRIS: unable to open phantom file " << phantom_name << G4endl;
			return false;
		}

		G4String bLine;
		std::getline(is,bLine);
		std::stringstream header_stream(bLine);
		std::vector<G4int> pdgs;
		G4int pdgfound;
		while (header_stream >> pdgfound) pdgs.push_back(pdgfound);
		if (pdgs.empty()) {
			G4cerr << "### AtRIS: phantom file has an empty PDG header: " << phantom_name << G4endl;
			return false;
		}

		if (phantom_index == 0){
			// need to check which PDGs I've got and which are light&heavy.
			expected_pdgs = pdgs;
			expected_header_name = phantom_name;
			for (std::size_t j = 0; j < pdgs.size(); ++j) {
				pdgfound = pdgs[j];
				if (std::abs(pdgfound)<2214){
					G4cout << j << " adding sensitivity for light particle with PDG= " << pdgfound << " "<<  "  at index " << pdgfound + 2213 << G4endl;
					useornot[pdgfound+2213] = j; // modify the corresponding useornot location to j
					// this offset is for antiparticles up to neutron and proton!
				}else {
					G4cout << "Added sensitivity for heavy particle with PDG= " << pdgfound << " under the index j=" << j << G4endl;
					heavy[pdgfound] = j;
				}
			}
			G4cout << "total" << pdgs.size() << G4endl;
			expected = 650 * pdgs.size();
			G4cout << " ### AtRIS: nricrubins is:" << 650 << " and nrpdgs is : "<< pdgs.size() << ". We are expecting: " << expected << " data points in the phantom file." << G4endl;
		} else if (pdgs != expected_pdgs) {
			G4cerr << "### AtRIS: PDG header mismatch: " << phantom_name
			       << " does not match " << expected_header_name << G4endl;
			return false;
		}

		G4double f;
		G4int count = 0;
		while ( std::getline(is,bLine)){
			std::stringstream dd(bLine);
			while (dd >> f){
				icru.push_back(f);
				count++;
			}
		}
		G4cout << "### AtRIS: found " << count << " out of expected "<< expected  << G4endl;
		if (count != expected) G4cout << " ### AtRIS: check phantoms file for empty ending charachters!!" << G4endl;
		abso.push_back(icru);
		G4cout << "### AtRIS: adding the radiation vector to the abso nested vector" << G4endl;

		// Now we do the counting phantom
		std::vector<G4double> cicru;
		phantom_name = "counting_phantom" + std::to_string(phantom_index) + ".txt";
		G4cout << "### AtRIS: loading counting response matrix for phantom " << phantom_index << " from " << phantom_name << G4endl << std::flush;
		count = 0;
		std::ifstream cs(phantom_name);
		if (!cs.is_open()) {
			G4cerr << "### AtRIS: unable to open phantom file " << phantom_name << G4endl;
			return false;
		}
		std::getline(cs, bLine);
		std::stringstream counting_header_stream(bLine);
		pdgs.clear();
		while (counting_header_stream >> pdgfound) pdgs.push_back(pdgfound);
		if (pdgs != expected_pdgs) {
			G4cerr << "### AtRIS: PDG header mismatch: " << phantom_name
			       << " does not match " << expected_header_name << G4endl;
			return false;
		}
		while ( std::getline(cs,bLine)){
			std::stringstream dd(bLine);
			while (dd >> f){
				cicru.push_back(f);
				count++;
			}
		}
		G4cout << "### AtRIS: found " << count << " out of expected "<< expected  << G4endl;
		if (count != expected) G4cout << " ### AtRIS: check phantoms file for empty ending charachters!!" << G4endl;
		G4cout << "### AtRIS: adding the counting vector to the rate nested vector" << G4endl;
		rate.push_back(cicru);
	}
	return true;
}

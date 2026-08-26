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
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <iostream>
#include <fstream>
#include <sstream>


G4String outputFileName;
G4int    mode = -1;
G4int    nrofdetectors=0;
FILE*    tuples1;

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



// functions of main
void Phantoms(G4int howmany);
void determine_nrofdetectors(G4String fname);

struct SimulationRun {
	G4String inputPrefix;
	std::array<G4long, 3> seeds = {0, 0, 0}; // CLHEP expects two seeds followed by a zero terminator.
	G4bool hasSeeds = false;
};

SimulationRun parseSimulationRun(const G4String& argument) {
	SimulationRun run;
	run.inputPrefix = argument;

	std::string path = argument.c_str();
	std::size_t pathSeparator = path.find_last_of("/\\");
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
	if (argc != 5){
		G4cout << "Usage: " << argv[0]
		       << " <physics-list> <simulation-name> <mode> <phantom-count>" << G4endl;
		// G4cout << "Example: " << argv[0] << " FTFP_BERT_HP protons 0 1" << G4endl;
		return 0;
	}
	mode = std::stoi(argv[3]);
	nrphantoms = std::stoi(argv[4]);
	/*
	G4cout << "### AtRIS: make sure that the following files exist:" << G4endl;
	G4cout << "\t\t "<< prefix <<".gdml\t\t:: geometry specification" << G4endl;
	G4cout << "\t\t "<< prefix <<".mac\t\t:: macro file" << G4endl;
	G4cout << "\t\t "<< prefix <<".bins\t\t:: input spectrum energy bins" << G4endl;
	G4cout << "\t\t "<< "icru_response.txt\t\t:: first default phantom (or alternative)" << G4endl;
	G4cout << "\t\t "<< "cell_response.txt\t\t:: second default phantom (or alternative)" << G4endl;
	G4cout << "### AtRIS: the following files will be overwritten!" << G4endl;
	G4cout << "\t\t "<< prefix <<".ioni\t\t::        mode -1 custom ionization density output" << G4endl;
	G4cout << "\t\t "<< prefix <<".dose\t\t::        mode -1 custom absorbed dose rate output using first phantom" << G4endl;
	G4cout << "\t\t "<< prefix <<".dose2\t\t::       mode -1 custom absorbed dose rate output using second phantom" << G4endl;
	G4cout << "\t\t "<< prefix <<".equi\t\t::        mode -1 custom equivalent dose rate output using first phantom" << G4endl;
	G4cout << "\t\t "<< prefix <<".equi2\t\t::       mode -1 custom equivalent dose rate output using second phantom" << G4endl;
	G4cout << "\t\t "<< prefix <<".rates\t\t::       mode -1 custom count rate output using first phantom" << G4endl;
	G4cout << "\t\t "<< prefix <<".rates2\t\t::      mode -1 custom count rate output using second phantom" << G4endl;
	G4cout << "\t\t "<< prefix <<"0.binary\t\t::     mode 0 binary output (all interfaces)" << G4endl;
	G4cout << "\t\t "<< prefix <<"_h1_h1.1.csv\t::   source energy distribution" << G4endl;
	G4cout << "\t\t "<< prefix <<"_h2_h2.dir.csv\t:: source direction distribution" << G4endl;
	G4cout << "\t\t "<< prefix <<"_h2_h2.pos.csv\t:: source position distribution" << G4endl;
	G4cout << "\t\t "<< prefix <<"_h2_h2.ion.csv\t:: resulting ionization histrogram" << G4endl;
	G4cout << "\t\t "<< prefix <<".asci\t\t::        mode 1 ascii output" << G4endl;
	G4cout << "\t\t "<< prefix <<".log\t\t::         detailed log file" << G4endl;
	G4cout << "\t\t "<< prefix <<".error\t\t::       error stream file" << G4endl;
	*/
	Phantoms(nrphantoms);
	SimulationRun simulation = parseSimulationRun(argv[2]);
	outputFileName    = argv[2];
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
	if (mode == 0){
		G4String bFN = outputFileName + (G4String) ".binary";
		G4cout << "### AtRIS: opening file:" << bFN << G4endl;
		tuples1 = std::fopen(bFN,"wb");

	}

	// DEACT atris::PrimaryGeneratorAction *pga = new atris::PrimaryGeneratorAction;
	// DEACT runManager->SetUserAction(pga);
	// DEACT atris::RunAction *beg = new atris::RunAction;
	// DEACT runManager->SetUserAction(beg);

	// ACT
	atris::UserActionInitialization* useract = new atris::UserActionInitialization(detector);
	runManager->SetUserInitialization(useract);


	// Get the pointer to the user interface manager and start the batch mode
	G4String tempString             ="/control/execute "+simulation.inputPrefix+".mac";
	G4cout << "### AtRIS: Starting the simulation " << G4endl;
	G4int commandStatus = UImanager->ApplyCommand(tempString);
	G4cout << "### AtRIS: simulation used " << runManager->GetNumberOfThreads() << " worker thread(s)" << G4endl;
	if (commandStatus == 0) {
		G4cout << "### AtRIS: the simulation has completed " << G4endl;
	} else {
		G4cerr << "### AtRIS: macro execution failed with Geant4 status " << commandStatus << G4endl;
	}
	if (mode == 0) {std::fclose(tuples1);}
	delete runManager;
	G4cout << "### AtRIS: The logfile has been sucessfully closed... " << G4endl;
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

void Phantoms(G4int howmany){
	G4int expected = 0; 
	G4cout << "### AtRIS: proceeding to load " << howmany << " phantom(s)." << G4endl << std::flush;
	for (G4int phantom_index=0; phantom_index < howmany; phantom_index++){
		std::vector<G4double> icru;
		G4String phantom_name = "radiation_phantom" + std::to_string(phantom_index) + ".txt";
		G4cout << "### AtRIS: loading radiation response matrix for phantom " << phantom_index << " from " << phantom_name << G4endl << std::flush;
		G4String dummyLine;
		std::ifstream is(phantom_name);
		if (phantom_index == 0){
			// need to check which PDGs I've got and which are light&heavy.
			G4int pdgfound;
			G4String bLine;         // instantiate the header string
			G4String temp;
			if (is.is_open()){
				std::getline(is,bLine); // read first line
				std::stringstream ss(bLine);
				G4int    j = 0;             // initialize the column index
				while (ss >> temp) {
					if (std::stringstream(temp) >> pdgfound){
						if (std::abs(pdgfound)<2214){
							G4cout << j << " adding sensitivity for light particle with PDG= " << pdgfound << " "<<  "  at index " << pdgfound + 2213 << G4endl;
							useornot[pdgfound+2213] = j; // modify the corresponding useornot location to j
							// this offset is for antiparticles up to neutron and proton!
						}else {
							G4cout << "Added sensitivity for heavy particle with PDG= " << pdgfound << " under the index j=" << j << G4endl;
							heavy[pdgfound] = j;
						}
						j++;                         // increment j
					}
				}
				G4cout << "total" << j << G4endl;
				//nrpdgs = j;
				// Now we need to process all the data and put it inside the icru vector
				expected = 650 * (j);
				G4cout << " ### AtRIS: nricrubins is:" << 650 << " and nrpdgs is : "<< (j) << ". We are expecting: " << expected << " data points in the phantom file." << G4endl;
			}

		} else {
			// If we are not dealing with the 0th phantom, we skip the first line
			std::getline(is, dummyLine);
		}

		G4String bLine;         // instantiate the header string
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
		std::getline(cs, dummyLine);
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
}

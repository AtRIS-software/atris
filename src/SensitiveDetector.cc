#include "SensitiveDetector.hh"
#include "G4UnitsTable.hh"
#include "G4VVisManager.hh"
#include "G4Circle.hh"
#include "G4Colour.hh"
#include "G4VisAttributes.hh"
#include "G4RunManager.hh"
#include "G4SystemOfUnits.hh"
#include "G4HCofThisEvent.hh"
#include "G4Event.hh"
#include "G4Step.hh"
#include "G4ThreeVector.hh"
#include "G4SDManager.hh"
#include "G4ios.hh"
#include "G4UIcmdWithAnInteger.hh"
#include "DetectorConstruction.hh"
#include "G4UIcmdWithAString.hh"
#include "G4Run.hh"
#include "G4CsvAnalysisManager.hh"
#include "G4PhysicalConstants.hh"
#include "G4AutoLock.hh"
#include "BinaryOutput.hh"
#include "PrimaryGeneratorAction.hh"
#include "G4GeneralParticleSourceData.hh"
#include "G4VProcess.hh"
#include <cmath>
#include <cstdio>
#include <map>
#include <vector>
extern G4int mode;                      // from src/main.cc
extern G4int nrofdetectors;             // from src/main.cc
extern FILE * tuples1;                  // 
extern FILE * stepTrace;
extern std::vector<G4int> useornot;     // 
extern std::vector<std::vector<G4double>> abso;      //
extern std::vector<std::vector<G4double>> rate;      //
extern G4int nrphantoms;
extern std::map<G4int, G4int> heavy;    //

namespace {
G4Mutex binaryOutputMutex;
G4Mutex stepTraceMutex;
}

namespace atris {

G4double icrustep = 0.02;

G4Allocator<SDHit>* SDHit::SDHitAllocator = nullptr;


SDHit::SDHit()
	: G4VHit()
{}

SDHit::~SDHit() {}

void SDHit::Print() {}


SensitiveDetector::SensitiveDetector(const G4String& name, G4bool zero_E)
	: G4VSensitiveDetector(name),
	fHitsCollection(nullptr),
	zeroE(zero_E)
{
	collectionName.insert(name);
}

SensitiveDetector::~SensitiveDetector()
{}

void SensitiveDetector::Initialize(G4HCofThisEvent* hce){
	// Create hits collection
	fHitsCollection	= new SDHitsCollection(SensitiveDetectorName, collectionName[0]);
	// Add this collection in hce
	G4int hcID = G4SDManager::GetSDMpointer()->GetCollectionID(collectionName[0]);
	hce->AddHitsCollection( hcID, fHitsCollection );
}

G4bool SensitiveDetector::ProcessHits(G4Step* step, G4TouchableHistory*){
	G4Track *trk      = step->GetTrack();
	G4double edep     = step->GetTotalEnergyDeposit();
	auto sourcedata   = G4GeneralParticleSourceData::Instance();
	auto theGun       = sourcedata->GetCurrentSource();
	G4double einp     = theGun->GetParticleEnergy();
	G4CsvAnalysisManager* analysis = G4CsvAnalysisManager::Instance();

	G4int    detid = std::stoi(this->GetName());
	G4double nioni = step->GetNonIonizingEnergyDeposit();
	if (mode == 1) {
		const G4Event* event = G4RunManager::GetRunManager()->GetCurrentEvent();
		const G4StepPoint* prePoint = step->GetPreStepPoint();
		const G4StepPoint* postPoint = step->GetPostStepPoint();
		const G4ThreeVector& prePosition = prePoint->GetPosition();
		const G4ThreeVector& postPosition = postPoint->GetPosition();
		const G4VProcess* creatorProcess = trk->GetCreatorProcess();
		const G4VProcess* stepProcess = postPoint->GetProcessDefinedStep();
		const G4String creatorName = creatorProcess
			? creatorProcess->GetProcessName()
			: "primary";
		const G4String stepProcessName = stepProcess
			? stepProcess->GetProcessName()
			: "none";

		StepRecord record = {
			static_cast<std::int32_t>(event ? event->GetEventID() : -1),
			static_cast<std::int32_t>(trk->GetTrackID()),
			static_cast<std::int32_t>(trk->GetParentID()),
			static_cast<std::int32_t>(trk->GetCurrentStepNumber()),
			static_cast<std::int32_t>(trk->GetParticleDefinition()->GetPDGEncoding()),
			static_cast<std::int32_t>(detid),
			prePosition.x()/km,
			prePosition.y()/km,
			prePosition.z()/km,
			postPosition.x()/km,
			postPosition.y()/km,
			postPosition.z()/km,
			prePoint->GetKineticEnergy()/MeV,
			postPoint->GetKineticEnergy()/MeV,
			edep/MeV,
			nioni/MeV,
			step->GetStepLength()/m,
			postPoint->GetGlobalTime()/ns,
			einp/MeV,
			{},
			{}
		};
		std::snprintf(
			record.creatorProcess,
			sizeof(record.creatorProcess),
			"%s",
			creatorName.c_str()
		);
		std::snprintf(
			record.stepProcess,
			sizeof(record.stepProcess),
			"%s",
			stepProcessName.c_str()
		);

		G4AutoLock lock(&stepTraceMutex);
		std::fwrite(&record, sizeof(record), 1, stepTrace);
	}
	if (detid == 0){
		trk->SetTrackStatus(fStopAndKill);
		return false;
	}
	if (detid == (nrofdetectors-1)){
		trk->SetTrackStatus(fStopAndKill);
		return false;
	}
	G4double ioni  = edep - nioni;
	analysis->FillH2(2,einp,detid,ioni/MeV);
	// mode -1:      dose rate determination
	// mode 0:   	 output binary data for all atmospheric sheets, at sheet interface
	//         	 purpose: altitude particle profiles
	// mode 1: 	 output binary data at each step
	//           	 purpose: shower visualization

	//before the step, the particle should have been at the boundary. 
	G4StepPoint* pre = step->GetPreStepPoint();
	if (pre->GetStepStatus() == fGeomBoundary){
		//Let's check which sdid we have:
		G4double ekin = pre->GetKineticEnergy();
		G4ThreeVector position     = pre->GetPosition().unit();
		G4ThreeVector direction    = pre->GetMomentumDirection();
		G4double inclination       = std::acos(position*direction); 
		bool upward                = inclination < halfpi;
		G4int diid                 = detid - (1*upward);
		G4int    partPDG           = trk->GetParticleDefinition()->GetPDGEncoding();
		G4int    apartPDG          = std::abs(partPDG);
		G4int    k = static_cast<G4int>(std::log10(ekin/eV)/icrustep);
		if (k < 0) k=0;
		if (apartPDG<2214) {
			G4int    dpartPDG          = partPDG + 2213;
			bool use = ((useornot[dpartPDG]) or (partPDG==22));
			if (use) { // light relevant particles
				G4int j = useornot[dpartPDG]*650+k;
				// ##########################
				// Extension: equivalent dose
				//            factor = 1 for all particles except:
				//                     2 for protons and pions
				//                    20 for heavy nuclei and fission fragments
				//                       for neutrons, we have a continious function wneut
				G4double wfactor = 1;
				if ((apartPDG == 2212) or (apartPDG == 111)) wfactor=2;
				if (apartPDG == 2112){
					if (ekin <= 1/MeV) {
						wfactor = 3.5 + 18.2*std::exp(-std::log(std::pow(ekin/MeV,2.0))/6.0) ;
					} else if (ekin <= 50/MeV) {
						wfactor = 5.0 + 17.0*std::exp(-std::log(std::pow(2*ekin/MeV,2.0))/6.0) ;
					} else if (ekin > 50/MeV) {
						wfactor = 2.5 + 3.25*std::exp(-std::log(std::pow(0.04*ekin/MeV,2.0))/6.0) ;
					}
				}
				for (G4int pidx=0;pidx<nrphantoms;pidx++){
					G4int offset = 3 + 3*pidx;
					analysis->FillH2(offset+0,einp,diid,abso[pidx][j]*ekin/eV );
					analysis->FillH2(offset+1,einp,diid,abso[pidx][j]*ekin/eV*wfactor);
					analysis->FillH2(offset+2,einp,diid,rate[pidx][j]);
				}


			}
		} else if (1000010019 < partPDG) {
			// We first check if we are dealing with one of the smaller, relevant isotopes
			// We then check if we are dealing with one of: H2, H3, He3, He4
			// If so, we add the contribution to the dose-rate histogram
			if (heavy.find(partPDG) != heavy.end()){
				G4int j = heavy[partPDG]*650+k;
				G4double wfactor = 20;
				for (G4int pidx=0;pidx<nrphantoms;pidx++){
					G4int offset = 3 + 3*pidx;
					analysis->FillH2(offset+0,einp,diid,abso[pidx][j]*ekin/eV );
					analysis->FillH2(offset+1,einp,diid,abso[pidx][j]*ekin/eV*wfactor);
					analysis->FillH2(offset+2,einp,diid,rate[pidx][j]);
				}
			}
		}

		if ((mode == 0) or (mode == 1)) {
			const InterfaceRecord record = {
				static_cast<std::int32_t>(partPDG),
				static_cast<std::uint16_t>(diid),
				static_cast<std::uint16_t>(std::round(inclination/deg)),
				static_cast<float>(pre->GetKineticEnergy()),
				static_cast<float>(einp),
			};
			G4AutoLock lock(&binaryOutputMutex);
			std::fwrite(&record, sizeof(record), 1, tuples1);
		}
	}

	return true;

}

}  // namespace atris

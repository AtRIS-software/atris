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
#include "G4AnalysisManager.hh"
#include "G4PhysicalConstants.hh"
#include "NtupleSchema.hh"
#include "PrimaryGeneratorAction.hh"
#include "G4GeneralParticleSourceData.hh"
#include "G4VProcess.hh"
#include <cmath>
#include <map>
#include <vector>
extern G4int mode;                      // from src/main.cc
extern G4int nrofdetectors;             // from src/main.cc
extern std::vector<G4int> useornot;     // 
extern std::vector<std::vector<G4double>> abso;      //
extern std::vector<std::vector<G4double>> rate;      //
extern G4int nrphantoms;
extern std::map<G4int, G4int> heavy;    //

namespace atris {

namespace {

const G4double ICRU_LOG_ENERGY_STEP = 0.02;

}  // namespace

G4Allocator<SDHit>* SDHit::SDHitAllocator = nullptr;


SDHit::SDHit()
	: G4VHit()
{}

SDHit::~SDHit() {}

void SDHit::Print() {}


SensitiveDetector::SensitiveDetector(const G4String& name)
	: G4VSensitiveDetector(name),
	fHitsCollection(nullptr)
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
	G4Track* const trk = step->GetTrack();
	const G4double edep = step->GetTotalEnergyDeposit();
	auto* const sourcedata = G4GeneralParticleSourceData::Instance();
	auto* const theGun = sourcedata->GetCurrentSource();
	const G4double einp = theGun->GetParticleEnergy();
	G4AnalysisManager* const analysis = G4AnalysisManager::Instance();

	const G4int detid = std::stoi(this->GetName());
	const G4double nioni = step->GetNonIonizingEnergyDeposit();
	if (mode == 1) {
		const G4Event* const event = G4RunManager::GetRunManager()->GetCurrentEvent();
		const G4StepPoint* const prePoint = step->GetPreStepPoint();
		const G4StepPoint* const postPoint = step->GetPostStepPoint();
		const G4ThreeVector& prePosition = prePoint->GetPosition();
		const G4ThreeVector& postPosition = postPoint->GetPosition();
		const G4VProcess* const creatorProcess = trk->GetCreatorProcess();
		const G4VProcess* const definingProcess = postPoint->GetProcessDefinedStep();
		const G4String creatorName = creatorProcess
			? creatorProcess->GetProcessName()
			: "primary";
		const G4String stepProcessName = definingProcess
			? definingProcess->GetProcessName()
			: "none";

		analysis->FillNtupleIColumn(
			stepNtupleId,
			stepEventId,
			event ? event->GetEventID() : -1
		);
		analysis->FillNtupleIColumn(stepNtupleId, stepTrackId, trk->GetTrackID());
		analysis->FillNtupleIColumn(stepNtupleId, stepParentId, trk->GetParentID());
		analysis->FillNtupleIColumn(
			stepNtupleId,
			stepId,
			trk->GetCurrentStepNumber()
		);
		analysis->FillNtupleIColumn(
			stepNtupleId,
			stepPdg,
			trk->GetParticleDefinition()->GetPDGEncoding()
		);
		analysis->FillNtupleIColumn(stepNtupleId, stepDetectorId, detid);
		analysis->FillNtupleDColumn(stepNtupleId, stepPreXKm, prePosition.x()/km);
		analysis->FillNtupleDColumn(stepNtupleId, stepPreYKm, prePosition.y()/km);
		analysis->FillNtupleDColumn(stepNtupleId, stepPreZKm, prePosition.z()/km);
		analysis->FillNtupleDColumn(stepNtupleId, stepPostXKm, postPosition.x()/km);
		analysis->FillNtupleDColumn(stepNtupleId, stepPostYKm, postPosition.y()/km);
		analysis->FillNtupleDColumn(stepNtupleId, stepPostZKm, postPosition.z()/km);
		analysis->FillNtupleDColumn(
			stepNtupleId,
			stepPreKineticEnergyMeV,
			prePoint->GetKineticEnergy()/MeV
		);
		analysis->FillNtupleDColumn(
			stepNtupleId,
			stepPostKineticEnergyMeV,
			postPoint->GetKineticEnergy()/MeV
		);
		analysis->FillNtupleDColumn(stepNtupleId, stepEnergyDepositMeV, edep/MeV);
		analysis->FillNtupleDColumn(
			stepNtupleId,
			stepNonionizingEnergyDepositMeV,
			nioni/MeV
		);
		analysis->FillNtupleDColumn(
			stepNtupleId,
			stepLengthM,
			step->GetStepLength()/m
		);
		analysis->FillNtupleDColumn(
			stepNtupleId,
			stepGlobalTimeNs,
			postPoint->GetGlobalTime()/ns
		);
		analysis->FillNtupleDColumn(stepNtupleId, stepPrimaryEnergyMeV, einp/MeV);
		analysis->FillNtupleSColumn(stepNtupleId, stepCreatorProcess, creatorName);
		analysis->FillNtupleSColumn(stepNtupleId, stepProcess, stepProcessName);
		analysis->AddNtupleRow(stepNtupleId);
	}
	if (detid == 0){
		trk->SetTrackStatus(fStopAndKill);
		return false;
	}
	if (detid == (nrofdetectors-1)){
		trk->SetTrackStatus(fStopAndKill);
		return false;
	}
	const G4double ioni = edep - nioni;
	analysis->FillH2(2,einp,detid,ioni/MeV);
	analysis->FillH2(3,einp,detid,edep/MeV);
	// mode -1:      dose rate determination
	// mode 0:   	 output data for all atmospheric sheets, at sheet interface
	//         	 purpose: altitude particle profiles
	// mode 1: 	 output data at each step
	//           	 purpose: shower visualization

	//before the step, the particle should have been at the boundary. 
	const G4StepPoint* const pre = step->GetPreStepPoint();
	if (pre->GetStepStatus() == fGeomBoundary){
		//Let's check which sdid we have:
		const G4double ekin = pre->GetKineticEnergy();
		const G4ThreeVector position = pre->GetPosition().unit();
		const G4ThreeVector direction = pre->GetMomentumDirection();
		const G4double inclination = std::acos(position*direction);
		const bool upward = inclination < halfpi;
		const G4int diid = detid - (1*upward);
		const G4int partPDG = trk->GetParticleDefinition()->GetPDGEncoding();
		const G4int apartPDG = std::abs(partPDG);
		G4int    k = static_cast<G4int>(std::log10(ekin/eV)/ICRU_LOG_ENERGY_STEP);
		if (k < 0) k=0;
		if (apartPDG<2214) {
			const G4int dpartPDG = partPDG + 2213;
			const bool use = ((useornot[dpartPDG]) or (partPDG==22));
			if (use) { // light relevant particles
				const G4int j = useornot[dpartPDG]*650+k;
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
					const G4int offset = 4 + 3*pidx;
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
				const G4int j = heavy[partPDG]*650+k;
				const G4double wfactor = 20;
				for (G4int pidx=0;pidx<nrphantoms;pidx++){
					const G4int offset = 4 + 3*pidx;
					analysis->FillH2(offset+0,einp,diid,abso[pidx][j]*ekin/eV );
					analysis->FillH2(offset+1,einp,diid,abso[pidx][j]*ekin/eV*wfactor);
					analysis->FillH2(offset+2,einp,diid,rate[pidx][j]);
				}
			}
		}

		if (mode == 0 || mode == 1) {
			analysis->FillNtupleIColumn(interfaceNtupleId, interfacePdg, partPDG);
			analysis->FillNtupleIColumn(interfaceNtupleId, interfaceId, diid);
			analysis->FillNtupleIColumn(
				interfaceNtupleId,
				interfaceAngleDegrees,
				static_cast<G4int>(std::round(inclination/deg))
			);
			analysis->FillNtupleDColumn(
				interfaceNtupleId,
				interfaceKineticEnergyMeV,
				pre->GetKineticEnergy()/MeV
			);
			analysis->FillNtupleDColumn(
				interfaceNtupleId,
				interfacePrimaryEnergyMeV,
				einp/MeV
			);
			analysis->AddNtupleRow(interfaceNtupleId);
		}
	}

	return true;

}

}  // namespace atris

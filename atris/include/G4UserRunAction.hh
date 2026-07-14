#ifndef G4UserRunAction_h
#define G4UserRunAction_h 1

#include "G4VUserDetectorConstruction.hh"
#include "G4Cache.hh"
#include "G4SystemOfUnits.hh"
#include "G4Types.hh"
#include "G4String.hh"
#include "HistoManager.hh"
#include "G4Run.hh"
#include <vector>
class DetectorConstruction; 

class G4UserRunAction
{
	public:
		G4UserRunAction(DetectorConstruction* detector,G4bool role);
		virtual ~G4UserRunAction();

	public:
		virtual G4Run* GenerateRun();
		virtual void BeginOfRunAction(const G4Run* aRun);
		virtual void EndOfRunAction(const G4Run* aRun);

	private:
		DetectorConstruction* fDetector;
		HistoManager* fHisto;


	protected:
		G4bool isMaster;


	public:
		inline virtual void SetMaster(G4bool val=true)
		{ isMaster = val; }
};

#endif



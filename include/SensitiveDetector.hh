#ifndef SensitiveDetector_hh
#define SensitiveDetector_hh

#include "G4VSensitiveDetector.hh"
#include "G4UImessenger.hh"

#include <vector>
#include <fstream>

#include "G4VHit.hh"
#include "G4THitsCollection.hh"
#include "G4Allocator.hh"
#include "G4ThreeVector.hh"
#include "tls.hh"
#include <functional>

class G4Step;
class G4HCofThisEvent;

namespace atris {

class SDHit;


class SDHit : public G4VHit
{
public:
	SDHit();
	virtual ~SDHit();

	inline void* operator new(size_t);
	inline void  operator delete(void*);

	virtual void Print();

	G4double ioni, nioni;
	G4String det, part;
	G4int detid, stepid;
	

	static G4Allocator<SDHit>* SDHitAllocator;
};

using SDHitsCollection = G4THitsCollection<SDHit>;

inline void* SDHit::operator new(size_t)
{
	if(!SDHitAllocator)
		SDHitAllocator = new G4Allocator<SDHit>;
	return (void *) SDHitAllocator->MallocSingle();
}

inline void SDHit::operator delete(void *hit)
{
	SDHitAllocator->FreeSingle((SDHit*) hit);
}


class SensitiveDetector : public G4VSensitiveDetector, public G4UImessenger
{
public:
	SensitiveDetector(const G4String& name, G4bool zero_E=false);
	virtual ~SensitiveDetector();

	// methods from base class
	virtual void   Initialize(G4HCofThisEvent* hitCollection);
	virtual G4bool ProcessHits(G4Step* step, G4TouchableHistory* history);

private:

	SDHitsCollection* fHitsCollection;

protected:
	static std::string formatString;
	G4bool zeroE;

	static std::ofstream outstream;
};

}  // namespace atris

#endif

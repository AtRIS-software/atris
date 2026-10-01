#ifndef HistoManager_h
#define HistoManager_h 1

#include "globals.hh"
#include "G4Types.hh"
#include "G4String.hh"

namespace atris {

class HistoManager
{
  public:
    HistoManager();
    ~HistoManager();
    void FillMetadata();

  private:
    void Book();
    G4String fFileName;
};

}  // namespace atris

#endif

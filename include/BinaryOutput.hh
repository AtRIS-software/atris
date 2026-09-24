#ifndef BinaryOutput_hh
#define BinaryOutput_hh 1

#include <cstdint>
#include <cstdio>

namespace atris {

enum class BinaryRecordType : std::uint16_t {
	Interface = 1,
	Step = 2,
};

struct BinaryHeader {
	char magic[8];
	std::uint16_t version;
	BinaryRecordType recordType;
	std::uint32_t byteOrder;
	std::uint32_t headerSize;
	std::uint32_t recordSize;
	std::uint32_t schemaVersion;
	std::uint32_t reserved;
};

struct InterfaceRecord {
	std::int32_t pdg;
	std::uint16_t interfaceId;
	std::uint16_t angleDegrees;
	float kineticEnergyMeV;
	float sourceEnergyMeV;
};

struct StepRecord {
	std::int32_t eventId;
	std::int32_t trackId;
	std::int32_t parentId;
	std::int32_t stepId;
	std::int32_t pdg;
	std::int32_t detectorId;
	double preXKm;
	double preYKm;
	double preZKm;
	double postXKm;
	double postYKm;
	double postZKm;
	double preKineticEnergyMeV;
	double postKineticEnergyMeV;
	double energyDepositMeV;
	double nonionizingEnergyDepositMeV;
	double stepLengthM;
	double globalTimeNs;
	double primaryEnergyMeV;
	char creatorProcess[64];
	char stepProcess[64];
};

static_assert(sizeof(BinaryHeader) == 32, "Unexpected binary-header layout");
static_assert(sizeof(InterfaceRecord) == 16, "Unexpected interface-record layout");
static_assert(sizeof(StepRecord) == 256, "Unexpected step-record layout");

inline bool WriteBinaryHeader(
	FILE* output,
	BinaryRecordType recordType,
	std::uint32_t recordSize
) {
	const BinaryHeader header = {
		{'A', 'T', 'R', 'I', 'S', 'B', 'I', 'N'},
		1,
		recordType,
		0x01020304,
		sizeof(BinaryHeader),
		recordSize,
		1,
		0,
	};
	return std::fwrite(&header, sizeof(header), 1, output) == 1;
}

}  // namespace atris

#endif

"""Shared header and record handling for AtRIS binary output files."""

from pathlib import Path
import struct
import sys

import numpy as np


MAGIC = b"ATRISBIN"
FORMAT_VERSION = 1
SCHEMA_VERSION = 1
BYTE_ORDER_MARKER = 0x01020304
HEADER_SIZE = 32
INTERFACE_RECORDS = 1
HEADER_FORMAT = "8sHHIIIII"


def write_header(stream, record_type, record_size):
    """Write an AtRIS binary header to a binary stream."""
    byte_order = "<" if sys.byteorder == "little" else ">"
    stream.write(
        struct.pack(
            byte_order + HEADER_FORMAT,
            MAGIC,
            FORMAT_VERSION,
            record_type,
            BYTE_ORDER_MARKER,
            HEADER_SIZE,
            record_size,
            SCHEMA_VERSION,
            0,
        )
    )


def read_header(filename):
    """Read and validate the common AtRIS binary header."""
    path = Path(filename)
    with path.open("rb") as stream:
        raw = stream.read(HEADER_SIZE)
    if len(raw) < HEADER_SIZE or raw[:8] != MAGIC:
        return None

    marker = raw[12:16]
    if marker == struct.pack("<I", BYTE_ORDER_MARKER):
        byte_order = "<"
    elif marker == struct.pack(">I", BYTE_ORDER_MARKER):
        byte_order = ">"
    else:
        raise ValueError(str(path) + " has an invalid byte-order marker")

    (
        magic,
        version,
        record_type,
        _,
        header_size,
        record_size,
        schema_version,
        _,
    ) = struct.unpack(byte_order + HEADER_FORMAT, raw)
    if magic != MAGIC or version != FORMAT_VERSION:
        raise ValueError(str(path) + " uses an unsupported binary format")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(str(path) + " uses an unsupported record schema")
    if header_size != HEADER_SIZE:
        raise ValueError(str(path) + " has an unexpected binary header size")
    return {
        "path": path,
        "record_type": record_type,
        "record_size": record_size,
        "byte_order": byte_order,
        "data_offset": header_size,
    }


def read_records(filename, expected_type, dtype, allow_legacy=False):
    """Memory-map records after validating their binary header and size."""
    path = Path(filename)
    header = read_header(path)
    if header is None:
        if not allow_legacy:
            raise ValueError(str(path) + " is not a versioned AtRIS binary file")
        offset = 0
        file_dtype = dtype
    else:
        if header["record_type"] != expected_type:
            raise ValueError(str(path) + " contains a different AtRIS record type")
        if header["record_size"] != dtype.itemsize:
            raise ValueError(str(path) + " has an unexpected binary record size")
        offset = header["data_offset"]
        file_dtype = dtype.newbyteorder(header["byte_order"])

    payload_size = path.stat().st_size - offset
    if payload_size < 0 or payload_size % file_dtype.itemsize:
        raise ValueError(
            "%s does not contain complete %i-byte records"
            % (path, file_dtype.itemsize)
        )
    if not payload_size:
        return np.empty(0, dtype=file_dtype)
    return np.memmap(
        path,
        mode="r",
        offset=offset,
        dtype=file_dtype,
        shape=(payload_size // file_dtype.itemsize,),
    )

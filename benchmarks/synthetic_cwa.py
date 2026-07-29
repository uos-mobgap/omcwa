"""Write deterministic synthetic CWA recordings of any length.

Benchmarks need input files that are large enough for the per-sample costs to
dominate, and every developer needs the same file on every platform. Real
recordings cannot be committed, so this module writes valid CWA files directly.

The output is a byte-exact CWA container that the vendored omconvert loader
accepts. Field offsets below are taken from the sector layout documented in
``native/vendored/omconvert/omdata.c`` and were checked against a real AX6
recording and against files written by the OpenMovement ``omsynth`` tool.

A recording is fully determined by its :class:`RecordingSpec`.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# CWA container layout
# ref: native/vendored/omconvert/omdata.c

SECTOR_BYTES = 512

# the header packet is one 1020 byte payload plus a 4 byte packet header, so it
# occupies the first two sectors. Data sectors follow it
_HEADER_SECTORS = 2
_HEADER_PAYLOAD_BYTES = 1020

# every data sector holds a 508 byte payload, of which 480 bytes are samples
_DATA_PAYLOAD_BYTES = 508
_SAMPLE_OFFSET = 30
_SAMPLE_BYTES = 480
_CHECKSUM_OFFSET = 510

# number of 16 bit channels per sample. An AX3 stores three accelerometer axes.
# An AX6 stores six channels, gyroscope first, then accelerometer.
# ref: omdata.c, "Slight hack for synchronous multi-axis"
_CHANNELS = {"AX3": 3, "AX6": 6}

# sample rate byte @24: low nibble codes the rate as 3200 / (1 << (15 - n)),
# top two bits code the accelerometer range as 16 >> n. 0x4a is 100 Hz at the
# plus or minus 8 g range, which is what both AX3 and AX6 units ship with
_RATE_CODE = 0x4A
SAMPLE_RATE_HZ = 100

# light word @18: bits 13 to 15 code the accelerometer counts per g as
# 1 << (8 + n), bits 10 to 12 code the gyroscope range as 8000 >> n, and the
# low ten bits are the light reading. 4 and 2 give 4096 counts per g and
# plus or minus 2000 degrees per second, matching real AX6 recordings
_LIGHT_WORD = (4 << 13) | (2 << 10)
_ACCEL_COUNTS_PER_G = 4096
_GYRO_COUNTS_PER_DPS = 32768 / 2000

# temperature word @20 is a raw ADC reading that omconvert converts with
# (raw * 150 - 20500) / 1000 to get degrees Celsius.
# ref: omconvert.c:OmConvertPlayerSeek
_TEMP_SCALE = 150
_TEMP_ZERO = 20500

# device identity. These values are cosmetic, they only appear in metadata
_DEVICE_ID = 12345
_SESSION_ID = 1
_FIRMWARE_VERSION = 60
_BATTERY_BYTE = 196
_EVENTS_BYTE = 1

# recordings start at 2020-01-01 00:00:00 UTC, matching the committed test
# fixtures. The start is a whole second so that sector times are reproducible
START_EPOCH = 1577836800

# sectors are assembled a block at a time so that peak memory stays flat even
# for a recording of several hundred hours. 65536 sectors is 32 MB.
_SECTORS_PER_BLOCK = 65536

# Signal shape

# each cycle opens with one stationary hold per orientation and closes with
# forty seconds of movement

# auto-calibration chops the recording into ten second windows and keeps a
# window only if every axis stays below a small standard deviation across it.
# Those windows are measured from the first sample, and the two calibration
# entry points in omconvert disagree about the first sample time by one sample,
# so window boundaries cannot be assumed to line up with hold boundaries. Each
# hold therefore runs for twice the window length, which guarantees at least
# one window falls entirely inside it whatever the alignment.
# ref: native/vendored/omconvert/omcalibrate.c:OmCalibrateConfigInit
HOLD_SECONDS = 20
MOVEMENT_SECONDS = 40

# gravity direction during each hold. The six axis-aligned orientations give
# every axis a range far wider than the 0.3 g that a calibration fit requires
ORIENTATIONS = (
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0),
    (0.577, 0.577, 0.577),
    (-0.577, 0.577, 0.577),
)
STATIONARY_SECONDS = HOLD_SECONDS * len(ORIENTATIONS)
CYCLE_SECONDS = STATIONARY_SECONDS + MOVEMENT_SECONDS

# a hold is not perfectly still. This dither stays well under the 0.013 g
# standard deviation that marks a window as stationary
_DITHER_G = 0.001
_DITHER_HZ = 17.0

# the written accelerometer signal carries a known error, so auto-calibration
# has a real fit to perform rather than converging on identity immediately
SCALE_ERROR = np.array([1.02, 0.98, 1.01])
OFFSET_ERROR = np.array([0.010, -0.020, 0.005])

# temperature sweeps once per cycle rather than once per recording, so even a
# recording of only a few minutes covers the full range. Auto-calibration fits
# a temperature coefficient and needs that spread
TEMPERATURE_CENTRE_C = 20.0
TEMPERATURE_SWING_C = 2.0


@dataclass(frozen=True)
class RecordingSpec:
    """Everything that determines the contents of a generated recording.

    Parameters
    ----------
    hours :
        Recording length. The written length is rounded up to a whole number of
        sectors, so the exact length is :attr:`duration_s`.
    device :
        ``"AX3"`` for an accelerometer-only recording, ``"AX6"`` to also write
        a gyroscope stream.
    """

    hours: float
    device: str = "AX6"

    @property
    def channels(self) -> int:
        """Number of 16 bit channels stored per sample."""
        return _CHANNELS[self.device]

    @property
    def samples_per_sector(self) -> int:
        """Samples packed into the 480 byte payload of one sector."""
        return _SAMPLE_BYTES // (2 * self.channels)

    @property
    def sector_count(self) -> int:
        """Number of data sectors, rounded up to hold the whole recording."""
        requested = self.hours * 3600 * SAMPLE_RATE_HZ
        return -(-int(requested) // self.samples_per_sector)

    @property
    def sample_count(self) -> int:
        """Number of samples actually written."""
        return self.sector_count * self.samples_per_sector

    @property
    def duration_s(self) -> float:
        """Recording length in seconds, after rounding up to whole sectors."""
        return self.sample_count / SAMPLE_RATE_HZ

    @property
    def byte_count(self) -> int:
        """Size of the written file in bytes."""
        return (_HEADER_SECTORS + self.sector_count) * SECTOR_BYTES

    @property
    def filename(self) -> str:
        """Cache-friendly file name. Equal specs give equal names."""
        return f"{self.device.lower()}-{self.hours:g}h.cwa"


def write_cwa(spec: RecordingSpec, path: Path) -> Path:
    """Write the recording described by ``spec`` to ``path``.

    The file is written in blocks, so memory use does not grow with the
    recording length.
    """
    cycle = _cycle_samples(spec)
    with path.open("wb") as handle:
        handle.write(_header_bytes(spec))

        for first in range(0, spec.sector_count, _SECTORS_PER_BLOCK):
            count = min(_SECTORS_PER_BLOCK, spec.sector_count - first)
            handle.write(_data_sector_bytes(spec, cycle, first, count))

    return path


# Signal generation


def _cycle_samples(spec: RecordingSpec) -> np.ndarray:
    """Build the raw counts for one repeating cycle.

    Returns an ``(N, channels)`` array of little-endian 16 bit counts. The full
    recording is this array tiled to length, which keeps generation cheap.
    """
    time_s = np.arange(CYCLE_SECONDS * SAMPLE_RATE_HZ) / SAMPLE_RATE_HZ
    stationary = time_s < STATIONARY_SECONDS

    accel_counts = np.rint(_accel_g(time_s, stationary) * _ACCEL_COUNTS_PER_G)
    if spec.channels == 3:
        return accel_counts.astype("<i2")

    gyro_counts = np.rint(_gyro_dps(time_s, stationary) * _GYRO_COUNTS_PER_DPS)

    # gyroscope occupies channels 0 to 2 and accelerometer channels 3 to 5.
    # ref: omdata.c, "Slight hack for synchronous multi-axis"
    return np.column_stack((gyro_counts, accel_counts)).astype("<i2")


def _accel_g(time_s: np.ndarray, stationary: np.ndarray) -> np.ndarray:
    """Acceleration in g for one cycle, including the calibration error."""
    hold = (time_s // HOLD_SECONDS).astype(int) % len(ORIENTATIONS)
    held = np.array(ORIENTATIONS)[hold]
    held = held + _DITHER_G * np.sin(2 * np.pi * _DITHER_HZ * time_s)[:, None]

    moving = np.column_stack(
        (
            0.60 * np.sin(2 * np.pi * 1.9 * time_s)
            + 0.20 * np.sin(2 * np.pi * 0.4 * time_s),
            0.50 * np.cos(2 * np.pi * 2.3 * time_s)
            + 0.15 * np.sin(2 * np.pi * 0.7 * time_s),
            1.00 + 0.70 * np.sin(2 * np.pi * 1.9 * time_s + 0.9),
        )
    )

    true_g = np.where(stationary[:, None], held, moving)
    return true_g * SCALE_ERROR + OFFSET_ERROR


def _gyro_dps(time_s: np.ndarray, stationary: np.ndarray) -> np.ndarray:
    """Angular velocity in degrees per second for one cycle."""
    moving = np.column_stack(
        (
            120.0 * np.sin(2 * np.pi * 1.9 * time_s),
            80.0 * np.cos(2 * np.pi * 2.3 * time_s),
            45.0 * np.sin(2 * np.pi * 0.7 * time_s),
        )
    )
    return np.where(stationary[:, None], 0.0, moving)


# Sector assembly


def _data_sector_bytes(
    spec: RecordingSpec,
    cycle: np.ndarray,
    first_sector: int,
    sector_count: int,
) -> bytes:
    """Assemble a block of complete data sectors."""
    sectors = np.zeros((sector_count, SECTOR_BYTES), dtype=np.uint8)
    sector = np.arange(
        first_sector, first_sector + sector_count, dtype=np.int64
    )

    sectors[:, 0] = ord("A")
    sectors[:, 1] = ord("X")
    _put_u16(sectors, 2, _DATA_PAYLOAD_BYTES)
    _put_u32(sectors, 6, _SESSION_ID)
    # a break in the sequence starts a new segment, so it must be contiguous
    # ref: omdata.c:OmDataAddSubSector
    _put_u32(sectors, 10, sector)
    _put_u16(sectors, 18, _LIGHT_WORD)
    _put_u16(sectors, 20, _temperature_raw(spec, sector))
    sectors[:, 22] = _EVENTS_BYTE
    sectors[:, 23] = _BATTERY_BYTE
    sectors[:, 24] = _RATE_CODE
    sectors[:, 25] = (spec.channels << 4) | 2  # channels, signed 16 bit
    _put_u16(sectors, 28, spec.samples_per_sector)

    _put_sector_time(spec, sectors, sector)
    _put_samples(spec, sectors, cycle, first_sector, sector_count)
    _put_checksum(sectors)

    return sectors.tobytes()


def _temperature_raw(spec: RecordingSpec, sector: np.ndarray) -> np.ndarray:
    """Raw temperature ADC reading for each sector."""
    time_s = sector * spec.samples_per_sector / SAMPLE_RATE_HZ
    celsius = TEMPERATURE_CENTRE_C + TEMPERATURE_SWING_C * np.sin(
        2 * np.pi * time_s / CYCLE_SECONDS
    )
    return np.rint((celsius * 1000 + _TEMP_ZERO) / _TEMP_SCALE)


def _put_sector_time(
    spec: RecordingSpec, sectors: np.ndarray, sector: np.ndarray
) -> None:
    """Write the timestamp fields describing each sector's first sample.

    A CWA timestamp only stores whole seconds, so the sub-second part is
    carried in the device word @4 and the loader converts it back into a sample
    offset. Writing the negated conversion into the timestamp offset @26 leaves
    a net offset of zero, which places the timestamp on the sector's first
    sample. This is the same encoding that ``omsynth`` produces.
    ref: omdata.c:OmDataTimestampForSector
    """
    start = START_EPOCH + sector * spec.samples_per_sector / SAMPLE_RATE_HZ
    whole = np.floor(start).astype(np.int64)

    # the device word keeps 15 bits and the loader doubles them, so this
    # truncates to the nearest 2/65536 of a second.
    half_fraction = ((start - whole) * 32768).astype(np.int64)
    fraction = half_fraction << 1

    _put_u16(sectors, 4, 0x8000 | half_fraction)
    _put_u32(sectors, 14, _pack_timestamp(whole))
    _put_u16(sectors, 26, -((fraction * SAMPLE_RATE_HZ) >> 16) & 0xFFFF)


def _pack_timestamp(seconds: np.ndarray) -> np.ndarray:
    """Pack Unix seconds into the CWA year/month/day/hour/minute/second word.

    ref: omdata.c DATETIME_YEAR and friends
    """
    moment = seconds.astype("datetime64[s]")
    day = moment.astype("datetime64[D]")
    month = moment.astype("datetime64[M]")

    years = moment.astype("datetime64[Y]").astype(np.int64) + 1970 - 2000
    months = month.astype(np.int64) % 12 + 1
    days = (day - month).astype(np.int64) + 1
    second_of_day = (moment - day).astype(np.int64)
    hours, remainder = np.divmod(second_of_day, 3600)
    minutes, secs = np.divmod(remainder, 60)

    return (
        (years << 26)
        | (months << 22)
        | (days << 17)
        | (hours << 12)
        | (minutes << 6)
        | secs
    )


def _put_samples(
    spec: RecordingSpec,
    sectors: np.ndarray,
    cycle: np.ndarray,
    first_sector: int,
    sector_count: int,
) -> None:
    """Tile the repeating cycle into the sample payload of each sector."""
    first_sample = first_sector * spec.samples_per_sector
    index = np.arange(
        first_sample, first_sample + sector_count * spec.samples_per_sector
    )
    samples = cycle[index % len(cycle)]
    payload = samples.reshape(sector_count, -1).view(np.uint8)
    sectors[:, _SAMPLE_OFFSET : _SAMPLE_OFFSET + _SAMPLE_BYTES] = payload


def _put_checksum(sectors: np.ndarray) -> None:
    """Write the trailing word that makes each sector sum to zero.

    ref: omdata.c:OmDataProcessSectors
    """
    words = sectors.view("<u2")
    total = words[:, :-1].astype(np.uint32).sum(axis=1)
    _put_u16(sectors, _CHECKSUM_OFFSET, -total & 0xFFFF)


def _put_u16(sectors: np.ndarray, offset: int, value) -> None:
    """Write a little-endian 16 bit field into every sector of a block."""
    value = np.asarray(value, dtype=np.int64)
    sectors[:, offset] = value & 0xFF
    sectors[:, offset + 1] = (value >> 8) & 0xFF


def _put_u32(sectors: np.ndarray, offset: int, value) -> None:
    """Write a little-endian 32 bit field into every sector of a block."""
    value = np.asarray(value, dtype=np.int64)
    for byte in range(4):
        sectors[:, offset + byte] = (value >> (8 * byte)) & 0xFF


# Header


def _header_bytes(spec: RecordingSpec) -> bytes:
    """Build the two sector CWA header packet.

    Unused space is filled with 0xff, which the loader treats as empty. The
    header is not checksummed.
    ref: omdata.c:OmDataProcessSectors, "CWA Header"
    """
    header = bytearray(b"\xff" * (_HEADER_SECTORS * SECTOR_BYTES))
    start, stop = _pack_timestamp(
        np.array(
            [START_EPOCH, START_EPOCH + int(spec.duration_s)],
            dtype=np.int64,
        )
    )

    header[0:2] = b"MD"
    struct.pack_into("<H", header, 2, _HEADER_PAYLOAD_BYTES)
    struct.pack_into("<H", header, 5, _DEVICE_ID)
    struct.pack_into("<I", header, 7, _SESSION_ID)
    struct.pack_into("<H", header, 11, 0xFFFF)  # no upper device id
    struct.pack_into("<I", header, 13, int(start))
    struct.pack_into("<I", header, 17, int(stop))
    header[26] = 0  # debugging info
    struct.pack_into("<I", header, 32, 0)  # last clear time
    header[36] = _RATE_CODE
    struct.pack_into("<I", header, 37, 0)  # last change time
    header[41] = _FIRMWARE_VERSION

    return bytes(header)

"""Parity and calibration-outcome tests against an omgui reference export.

Fixture provenance
------------------
- ``omgui_test.cwa``: 6-channel recording (accel + gyro)
- ``omgui_test_autocal_100res.wav``: omgui export of that file with
  auto-calibrate enabled and resampling at 100 Hz

Why a single WAV
----------------
On this recording the file default rate is already 100 Hz and auto-calibration
does not converge (identity fallback). Other omgui option combinations
(calibrate on/off × 100 Hz / auto rate) produce bitwise-identical WAV output,
so only one reference file is kept.

Known calibration behaviour
---------------------------
Auto-calibration falls back to identity while reporting failure via
``Calibration.success is False`` and a non-zero ``error_code`` (observed
``-2``). Parity uses calibrate-on processing with that documented fallback.

WAV decoding
------------
Reference WAV stores int16-quantized channels. Physical units are recovered
from ``Scale-N`` entries in the LIST/INFO/ICMT comment:

    physical = int16 * (2 * range) / 65536

Channels 0-2 are accelerometer (range 8 g on this fixture). Channels 3-5 are
gyroscope (range 2000 dps). Auxiliary channels are ignored.

Comparisons use LSB-aware tolerances on interior samples (edge transients
trimmed). Exact float equality is inappropriate.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path

import numpy as np
import pytest

from omcwa import process_cwa

PARITY_SAMPLE_RATE_HZ = 100.0

EDGE_TRIM = 100
FRACTION_WITHIN_TOLERANCE = 0.999
LSB_MULTIPLIER = 1.5


def _decode_omgui_wav(
    path: Path,
) -> tuple[np.ndarray, np.ndarray, dict[int, float]]:
    """Decode an omgui-exported WAV without external dependencies."""
    data = path.read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        msg = f"not a RIFF/WAVE file: {path}"
        raise ValueError(msg)

    fmt: tuple[int, ...] | None = None
    sample_bytes: bytes | None = None
    comment = ""

    pos = 12
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        chunk_size = struct.unpack_from("<I", data, pos + 4)[0]
        body = data[pos + 8 : pos + 8 + chunk_size]

        if chunk_id == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", body[:16])
        elif chunk_id == b"data":
            sample_bytes = body
        elif chunk_id == b"LIST" and body[:4] == b"INFO":
            offset = 4
            while offset + 8 <= len(body):
                sub_id = body[offset : offset + 4]
                sub_size = struct.unpack_from("<I", body, offset + 4)[0]
                value = body[offset + 8 : offset + 8 + sub_size]

                if sub_id == b"ICMT":
                    comment = value.decode("utf-8", errors="replace")

                offset += 8 + sub_size + (sub_size % 2)
        pos += 8 + chunk_size + (chunk_size % 2)

    if fmt is None or sample_bytes is None:
        msg = f"missing fmt or data chunk in WAV: {path}"
        raise ValueError(msg)

    scales = {
        int(channel): float(value)
        for channel, value in re.findall(
            r"Scale-(\d+):\s*([0-9.+-eE]+)", comment
        )
    }
    if not scales:
        msg = f"no Scale-N entries found in WAV comment: {path}"
        raise ValueError(msg)

    num_channels = int(fmt[1])
    raw = np.frombuffer(sample_bytes, dtype="<i2").reshape(-1, num_channels)

    acc = np.empty((raw.shape[0], 3), dtype=np.float64)
    gyr = np.empty((raw.shape[0], 3), dtype=np.float64)

    for axis in range(3):
        acc_range = scales[axis + 1]
        lsb = (2.0 * acc_range) / 65536.0
        acc[:, axis] = raw[:, axis] * lsb

    for axis in range(3):
        gyr_range = scales[axis + 4]
        lsb = (2.0 * gyr_range) / 65536.0
        gyr[:, axis] = raw[:, axis + 3] * lsb

    return acc, gyr, scales


def test_process_cwa_matches_omgui_wav(
    omgui_cwa: Path,
    omgui_wav: Path,
) -> None:
    """process_cwa output matches omgui WAV within int16 LSB tolerance."""
    out = process_cwa(omgui_cwa, sample_rate_hz=PARITY_SAMPLE_RATE_HZ)
    ref_acc, ref_gyr, scales = _decode_omgui_wav(omgui_wav)

    assert out.sample_rate_hz == pytest.approx(PARITY_SAMPLE_RATE_HZ)
    assert out.gyr is not None
    assert out.acc.shape == ref_acc.shape
    assert out.gyr.shape == ref_gyr.shape

    acc_diff = out.acc[EDGE_TRIM:-EDGE_TRIM] - ref_acc[EDGE_TRIM:-EDGE_TRIM]
    gyr_diff = out.gyr[EDGE_TRIM:-EDGE_TRIM] - ref_gyr[EDGE_TRIM:-EDGE_TRIM]

    lsb_acc = (2.0 * scales[1]) / 65536.0
    lsb_gyr = (2.0 * scales[4]) / 65536.0

    acc_fraction = float(
        np.mean(np.max(np.abs(acc_diff), axis=1) <= (LSB_MULTIPLIER * lsb_acc))
    )
    gyr_fraction = float(
        np.mean(np.max(np.abs(gyr_diff), axis=1) <= (LSB_MULTIPLIER * lsb_gyr))
    )

    assert acc_fraction >= FRACTION_WITHIN_TOLERANCE
    assert gyr_fraction >= FRACTION_WITHIN_TOLERANCE


def test_auto_calibration_reports_fallback(omgui_cwa: Path) -> None:
    """Auto-calibration failure is observable on the omgui test fixture."""
    out = process_cwa(omgui_cwa, sample_rate_hz=PARITY_SAMPLE_RATE_HZ)

    assert out.calibration is not None
    assert out.calibration.success is False
    assert out.calibration.error_code != 0

#!/usr/bin/env python3
"""Regenerate committed CWA fixtures with reference OpenMovement binaries."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from fixtures_csv import (
    fixture_names,
    fixture_sample_rate_hz,
    write_fixture_csv,
)

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
TARGET_RATE_HZ = 100
INTERPOLATE_MODE = 3  # InterpolateMode.CUBIC
EXPECTED_CALIBRATION_RESULTS = {
    "cal_success": 0,
    "cal_failure": -1,
    "cal_failure_no_axis": -2,
}


def _resolve_binary(value: Path | None, name: str) -> Path:
    """Resolve an executable from a CLI path or ``PATH``."""
    candidate = value
    if candidate is None:
        located = shutil.which(name)
        if located is not None:
            candidate = Path(located)
    if (
        candidate is None
        or not candidate.is_file()
        or not os.access(candidate, os.X_OK)
    ):
        raise FileNotFoundError(
            f"{name} is not executable. Pass --{name} /path/to/{name}"
        )
    return candidate.resolve()


def _run_omsynth(binary: Path, csv_path: Path, cwa_path: Path) -> None:
    """Run omsynth to synthesise a CWA from a CSV input."""
    subprocess.run(
        [
            binary,
            csv_path,
            "-out",
            cwa_path,
            "-rate",
            str(TARGET_RATE_HZ),
            "-gyro",
            "2000",
        ],
        check=True,
    )


def _run_omconvert(
    binary: Path,
    cwa_path: Path,
    wav_path: Path,
    info_path: Path,
    *,
    calibrate: bool,
) -> None:
    """Run omconvert to write WAV output and an ``-info`` sidecar."""
    subprocess.run(
        [
            binary,
            cwa_path,
            "-resample",
            str(TARGET_RATE_HZ),
            "-calibrate",
            str(int(calibrate)),
            "-interpolate-mode",
            str(INTERPOLATE_MODE),
            "-out",
            wav_path,
            "-info",
            info_path,
        ],
        check=True,
    )


def _parse_info(path: Path) -> dict[str, str]:
    """Parse omconvert ``-info`` key/value lines into a flat mapping."""
    info: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        key, separator, value = line.partition(":")
        if separator:
            info[key.strip()] = value.strip()

    return info


def _calibration_oracle(info: dict[str, str]) -> dict[str, Any]:
    """Extract calibration coefficients from omconvert info output."""
    values = [float(value) for value in info["Calibration"].split(",")]
    if len(values) != 10:
        raise ValueError(
            f"expected 10 calibration values, received {len(values)}"
        )
    return {
        "error_code": int(info["Calibration-Result"]),
        "scale": values[0:3],
        "offset": values[3:6],
        "temp_offset": values[6:9],
        "reference_temperature": values[9],
        "stationary_count": int(info.get("Calibration-Stationary-Count", "0")),
        "svm_error_pre": float(
            info.get("Calibration-Stationary-Error-Pre", "0")
        ),
        "svm_error_post": float(
            info.get("Calibration-Stationary-Error-Post", "0")
        ),
    }


def _decode_wav(path: Path) -> tuple[np.ndarray, np.ndarray, float]:
    """Decode omconvert WAV into physical accel, gyro, and sample rate.

    Minimal reimplementation of the omconvert WAV import contract.
    """
    data = path.read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"not a RIFF/WAVE file: {path}")

    fmt: tuple[int, ...] | None = None
    sample_bytes: bytes | None = None
    comment = ""
    # Walk RIFF chunks. Pad odd-sized bodies to the next word boundary.
    # ref: native/vendored/omconvert/wav.c
    position = 12
    while position + 8 <= len(data):
        chunk_id = data[position : position + 4]
        chunk_size = struct.unpack_from("<I", data, position + 4)[0]
        body = data[position + 8 : position + 8 + chunk_size]

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
                    # ref: native/vendored/omconvert/README.md
                    comment = value.decode("utf-8", errors="replace")

                offset += 8 + sub_size + (sub_size % 2)
        position += 8 + chunk_size + (chunk_size % 2)

    if fmt is None or sample_bytes is None:
        raise ValueError(f"missing fmt or data chunk in WAV: {path}")

    # fmt: (audio_format, channels, sample_rate, ..., bits_per_sample)
    if fmt[0] not in {1, 0xFFFE} or fmt[5] != 16 or fmt[1] < 6:
        raise ValueError(
            "expected PCM16 or extensible PCM16 WAV with at least six "
            "sensor channels"
        )

    # Parse Scale-N from the ICMT comment.
    # ref: native/vendored/omconvert/README.md ("Importing the WAV file")
    # ref: native/vendored/omconvert/omconvert.c (Scale-N write/read)
    scales = {
        int(channel): float(value)
        for channel, value in re.findall(
            r"Scale-(\d+):\s*([0-9.+-eE]+)",
            comment,
        )
    }

    if any(channel not in scales for channel in range(1, 7)):
        raise ValueError("WAV comment is missing Scale-1 through Scale-6")

    raw = np.frombuffer(sample_bytes, dtype="<i2").reshape(-1, fmt[1])
    physical = np.empty((raw.shape[0], 6), dtype=np.float64)
    for axis in range(6):
        # physical = int16 * (2 * Scale-N) / 65536
        # ref: native/vendored/omconvert/omdata.c
        lsb = (2.0 * scales[axis + 1]) / 65536.0
        physical[:, axis] = raw[:, axis] * lsb

    return physical[:, :3], physical[:, 3:6], float(fmt[2])


def _write_output_oracle(
    wav_path: Path,
    npz_path: Path,
    *,
    compressed: bool,
) -> None:
    """Write accel/gyro NPZ golden oracles decoded from omconvert WAV output."""
    accel, gyro, output_rate = _decode_wav(wav_path)
    save = np.savez_compressed if compressed else np.savez
    save(
        npz_path,
        accel=accel,
        gyro=gyro,
        output_samples=accel.shape[0],
        output_rate=output_rate,
    )


def regenerate(omsynth: Path, omconvert: Path, golden_dir: Path) -> None:
    """Regenerate all artifacts, replacing committed files only on success."""
    golden_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omcwa-golden-") as temp:
        work_dir = Path(temp)
        artifacts: list[Path] = []

        for name in fixture_names():
            csv_path = work_dir / f"{name}.csv"
            cwa_path = work_dir / f"{name}.cwa"
            wav_path = work_dir / f"{name}.golden.wav"
            info_path = work_dir / f"{name}.golden.yml"

            write_fixture_csv(str(csv_path), name)
            if fixture_sample_rate_hz(name) != TARGET_RATE_HZ:
                raise ValueError(f"unexpected sample rate for {name}")
            _run_omsynth(omsynth, csv_path, cwa_path)
            # resample_only exercises identity calibration (calibrate=False).
            calibrate = name != "resample_only"
            _run_omconvert(
                omconvert,
                cwa_path,
                wav_path,
                info_path,
                calibrate=calibrate,
            )

            artifacts.append(cwa_path)

            info = _parse_info(info_path)
            expected_result = EXPECTED_CALIBRATION_RESULTS.get(name)
            if expected_result is not None:
                actual_result = int(info["Calibration-Result"])
                if actual_result != expected_result:
                    raise ValueError(
                        f"{name}: expected calibration result "
                        f"{expected_result}, received {actual_result}"
                    )

            if name == "resample_only":
                oracle = work_dir / "resample_only.golden.npz"
                _write_output_oracle(
                    wav_path,
                    oracle,
                    compressed=False,  # matches np.load usage in parity tests
                )
                artifacts.append(oracle)
            elif name == "cal_success":
                oracle = work_dir / "cal_success.golden.npz"
                _write_output_oracle(
                    wav_path,
                    oracle,
                    compressed=True,
                )
                artifacts.append(oracle)
                calibration_json = work_dir / "cal_success.golden.json"
                calibration_json.write_text(
                    json.dumps(_calibration_oracle(info), indent=2) + "\n",
                    encoding="utf-8",
                )
                artifacts.append(calibration_json)

        for artifact in artifacts:
            shutil.copyfile(artifact, golden_dir / artifact.name)


def main() -> None:
    """Parse CLI arguments and regenerate committed golden artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--omsynth",
        type=Path,
        help="path to the OpenMovement omsynth executable",
    )
    parser.add_argument(
        "--omconvert",
        type=Path,
        help="path to the OpenMovement omconvert executable",
    )
    parser.add_argument(
        "--golden-dir",
        type=Path,
        default=GOLDEN_DIR,
        help="output directory (default: tests/fixtures/golden)",
    )
    arguments = parser.parse_args()
    regenerate(
        _resolve_binary(arguments.omsynth, "omsynth"),
        _resolve_binary(arguments.omconvert, "omconvert"),
        arguments.golden_dir,
    )


if __name__ == "__main__":
    main()

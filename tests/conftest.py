"""Shared pytest fixtures for omcwa."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURE_CWA = "omgui_test.cwa"
FIXTURE_WAV = "omgui_test_autocal_100res.wav"
FIXTURE_ENV_VAR = "OMCWA_FIXTURE_DIR"


def resolve_omgui_fixtures() -> tuple[Path, Path] | None:
    """Return (cwa_path, wav_path) when omgui fixtures are available."""
    local_dir = Path(__file__).resolve().parent / "fixtures"
    local_cwa = local_dir / FIXTURE_CWA
    local_wav = local_dir / FIXTURE_WAV

    if local_cwa.is_file() and local_wav.is_file():
        return local_cwa, local_wav

    env_dir = os.environ.get(FIXTURE_ENV_VAR)
    if env_dir:
        env_path = Path(env_dir)
        env_cwa = env_path / FIXTURE_CWA
        env_wav = env_path / FIXTURE_WAV

        if env_cwa.is_file() and env_wav.is_file():
            return env_cwa, env_wav

    return None


@pytest.fixture(scope="session")
def omgui_fixtures() -> tuple[Path, Path]:
    """omgui CWA/WAV pair used for parity and calibration tests."""
    paths = resolve_omgui_fixtures()
    if paths is None:
        pytest.skip(
            "omgui fixtures not found. Place files under tests/fixtures/ "
            f"or set {FIXTURE_ENV_VAR} to a directory containing "
            f"{FIXTURE_CWA} and {FIXTURE_WAV}."
        )
    return paths


@pytest.fixture(scope="session")
def omgui_cwa(omgui_fixtures: tuple[Path, Path]) -> Path:
    """Path to the omgui-source CWA fixture."""
    return omgui_fixtures[0]


@pytest.fixture(scope="session")
def omgui_wav(omgui_fixtures: tuple[Path, Path]) -> Path:
    """Path to the omgui reference WAV (auto-calibrate, 100 Hz)."""
    return omgui_fixtures[1]

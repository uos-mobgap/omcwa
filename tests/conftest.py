"""Shared pytest fixtures for omcwa."""

from __future__ import annotations

from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    """Directory containing committed synthetic fixtures and oracles."""
    return GOLDEN_DIR


@pytest.fixture(scope="session")
def resample_only_cwa(golden_dir: Path) -> Path:
    """Synthetic waveform fixture for identity-calibration resampling."""
    return golden_dir / "resample_only.cwa"


@pytest.fixture(scope="session")
def cal_success_cwa(golden_dir: Path) -> Path:
    """Synthetic fixture whose auto-calibration succeeds."""
    return golden_dir / "cal_success.cwa"


@pytest.fixture(scope="session")
def cal_failure_cwa(golden_dir: Path) -> Path:
    """Synthetic fixture producing calibration error -1."""
    return golden_dir / "cal_failure.cwa"


@pytest.fixture(scope="session")
def cal_failure_no_axis_cwa(golden_dir: Path) -> Path:
    """Synthetic fixture producing calibration error -2."""
    return golden_dir / "cal_failure_no_axis.cwa"

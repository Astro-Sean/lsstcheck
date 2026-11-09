"""Shared fixtures: load the extensionless `lsstcheck` script as a module."""

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    loader = importlib.machinery.SourceFileLoader(
        "lsstcheck", str(ROOT / "lsstcheck")
    )
    spec = importlib.util.spec_from_loader("lsstcheck", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def lsc():
    """The lsstcheck module under test."""
    return _load()

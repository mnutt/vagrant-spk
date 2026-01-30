"""Shared fixtures for testing lima-spk and vagrant-spk."""

import importlib.machinery
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest


# Get the repository root directory
REPO_ROOT = Path(__file__).parent.parent


def load_script_as_module(script_name: str):
    """Load a Python script as a module without executing if __name__ == '__main__'.

    This handles scripts without .py extensions by using SourceFileLoader directly.
    """
    script_path = REPO_ROOT / script_name
    module_name = script_name.replace("-", "_")

    # Use SourceFileLoader for files without .py extension
    loader = importlib.machinery.SourceFileLoader(module_name, str(script_path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)

    # Add to sys.modules before execution to handle any self-imports
    sys.modules[module_name] = module

    # Execute the module
    spec.loader.exec_module(module)

    # Fix CODE_DIR which is calculated at module load time based on sys.argv[0]
    # When running under pytest, sys.argv[0] is pytest, not the script
    if hasattr(module, 'CODE_DIR'):
        module.CODE_DIR = str(REPO_ROOT)

    # Add metadata for test identification
    module._script_name = script_name
    module._script_path = str(script_path)

    return module


@pytest.fixture
def lima_spk():
    """Load lima-spk as a module."""
    return load_script_as_module("lima-spk")


@pytest.fixture
def vagrant_spk():
    """Load vagrant-spk as a module."""
    return load_script_as_module("vagrant-spk")


@pytest.fixture(params=["lima-spk", "vagrant-spk"])
def spk_script(request):
    """Parameterized fixture to test both scripts."""
    return load_script_as_module(request.param)


@pytest.fixture
def mock_work_directory(tmp_path):
    """Create a temporary work directory for testing."""
    return tmp_path


@pytest.fixture
def sandstorm_dir(tmp_path):
    """Create a temporary .sandstorm directory for testing."""
    sandstorm = tmp_path / ".sandstorm"
    sandstorm.mkdir()
    return sandstorm


@pytest.fixture
def mock_home(tmp_path, monkeypatch):
    """Create a mock home directory with .sandstorm folder."""
    home = tmp_path / "home"
    home.mkdir()
    sandstorm = home / ".sandstorm"
    sandstorm.mkdir()
    caches = sandstorm / "caches"
    caches.mkdir()

    monkeypatch.setenv("HOME", str(home))
    return home

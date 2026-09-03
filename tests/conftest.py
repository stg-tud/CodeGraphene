import os
import shutil
import pytest


@pytest.fixture(scope="session")
def use_real_joern():
    """Return True when the environment opts into running real Joern.

    Usage: set environment variable RUN_REAL_JOERN=1 and ensure `joern` is in PATH.
    """
    if os.environ.get("RUN_REAL_JOERN") in ("1", "true", "True") and shutil.which("joern"):
        return True
    return False

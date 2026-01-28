"""Integration test specific fixtures."""

from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Mark all tests in this directory as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def temp_home() -> Generator[str, None, None]:
    """Create a temporary home directory for testing."""
    with tempfile.TemporaryDirectory(prefix="dbx-test-home-") as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_volume() -> Generator[str, None, None]:
    """Create a temporary directory to use as a volume mount."""
    with tempfile.TemporaryDirectory(prefix="dbx-test-vol-") as tmpdir:
        # Create a test file in the volume
        test_file = os.path.join(tmpdir, "test-file.txt")
        with open(test_file, "w") as f:
            f.write("test content from host")
        yield tmpdir


# Common test images
DISTRO_IMAGES = {
    "alpine": "alpine:latest",
    "ubuntu": "ubuntu:22.04",
    "fedora": "fedora:latest",
    "debian": "debian:stable-slim",
    "archlinux": "archlinux:latest",
}


@pytest.fixture(params=list(DISTRO_IMAGES.keys()))
def distro_image(request: pytest.FixtureRequest) -> tuple[str, str]:
    """Parameterized fixture for testing multiple distros.

    Returns (distro_name, image_name) tuple.
    """
    return request.param, DISTRO_IMAGES[request.param]

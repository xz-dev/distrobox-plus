"""Tests for distrobox-ephemeral command."""

from __future__ import annotations

import re

import pytest

from distrobox_plus.commands.ephemeral import generate_ephemeral_name

pytestmark = [pytest.mark.integration, pytest.mark.ephemeral]


class TestEphemeralNameGeneration:
    """Test ephemeral name generation."""

    @pytest.mark.fast
    def test_generate_ephemeral_name_format(self):
        """Test that generated names match expected format."""
        name = generate_ephemeral_name()

        # Should match distrobox-XXXXXXXXXX pattern (mktemp uses [A-Za-z0-9])
        assert re.match(r"^distrobox-[A-Za-z0-9]{10}$", name)

    @pytest.mark.fast
    def test_generate_ephemeral_name_unique(self):
        """Test that generated names are unique."""
        names = [generate_ephemeral_name() for _ in range(100)]

        # All names should be unique
        assert len(set(names)) == len(names)


class TestEphemeralHelp:
    """Test ephemeral help output."""

    @pytest.mark.fast
    def test_ephemeral_help(self, distrobox):
        """Test ephemeral --help output."""
        result = distrobox.run("ephemeral", ["--help"])

        # Help should contain key information
        assert "distrobox version:" in result.stdout or "distrobox version:" in result.stderr
        assert "--root" in result.stdout or "--root" in result.stderr

    @pytest.mark.fast
    def test_ephemeral_version(self, distrobox):
        """Test ephemeral --version output."""
        result = distrobox.run("ephemeral", ["--version"])

        assert "distrobox:" in result.stdout or "distrobox:" in result.stderr

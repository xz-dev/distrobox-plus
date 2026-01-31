"""Unit tests for distrobox_plus.utils.builder module."""

from __future__ import annotations

from distrobox_plus.utils.builder import (
    generate_containerfile,
    get_boost_image_name,
    get_boost_image_tag,
)


class TestGetBoostImageName:
    """Tests for get_boost_image_name function."""

    def test_simple_name(self):
        """Test simple image name."""
        result = get_boost_image_name("alpine")
        assert result == "alpine:distrobox-plus"

    def test_name_with_tag(self):
        """Test image name with tag."""
        result = get_boost_image_name("alpine:latest")
        assert result == "alpine-latest:distrobox-plus"

    def test_name_with_registry(self):
        """Test image name with registry."""
        result = get_boost_image_name("docker.io/library/alpine")
        assert result == "docker.io-library-alpine:distrobox-plus"

    def test_uppercase_converted(self):
        """Test that uppercase is converted to lowercase."""
        result = get_boost_image_name("Ubuntu:22.04")
        assert result == "ubuntu-22.04:distrobox-plus"


class TestGetBoostImageTag:
    """Tests for get_boost_image_tag function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = get_boost_image_tag("alpine:latest")
        assert isinstance(result, str)

    def test_contains_boost(self):
        """Test that tag contains 'boost'."""
        result = get_boost_image_tag("alpine:latest")
        assert "-boost:" in result

    def test_same_inputs_same_hash(self):
        """Test that same inputs produce same hash."""
        result1 = get_boost_image_tag("alpine:latest", "git", "hook1", "hook2")
        result2 = get_boost_image_tag("alpine:latest", "git", "hook1", "hook2")
        assert result1 == result2

    def test_different_image_different_hash(self):
        """Test that different images produce different hashes."""
        result1 = get_boost_image_tag("alpine:latest")
        result2 = get_boost_image_tag("fedora:latest")
        assert result1 != result2

    def test_different_packages_different_hash(self):
        """Test that different packages produce different hashes."""
        result1 = get_boost_image_tag("alpine:latest", "git")
        result2 = get_boost_image_tag("alpine:latest", "vim")
        assert result1 != result2

    def test_different_hooks_different_hash(self):
        """Test that different hooks produce different hashes."""
        result1 = get_boost_image_tag("alpine:latest", "", "hook1")
        result2 = get_boost_image_tag("alpine:latest", "", "hook2")
        assert result1 != result2

    def test_hash_length(self):
        """Test that hash is 12 characters."""
        result = get_boost_image_tag("alpine:latest")
        # Format: name-boost:hash
        hash_part = result.split(":")[-1]
        assert len(hash_part) == 12


class TestGenerateContainerfile:
    """Tests for generate_containerfile function."""

    def test_starts_with_from_and_init_stage(self):
        """Test that Containerfile starts with FROM and init stage."""
        result = generate_containerfile("alpine:latest")
        assert result.startswith("FROM alpine:latest AS init")

    def test_contains_boost_marker(self):
        """Test that Containerfile creates boost marker."""
        result = generate_containerfile("alpine:latest")
        assert "touch /.distrobox-boost" in result

    def test_contains_upgrade(self):
        """Test that Containerfile upgrades packages."""
        result = generate_containerfile("alpine:latest")
        assert "# Upgrade existing packages" in result
        assert "RUN set -e" in result

    def test_contains_install(self):
        """Test that Containerfile installs dependencies."""
        result = generate_containerfile("alpine:latest")
        assert "# Install distrobox dependencies" in result

    def test_no_additional_packages_without_arg(self):
        """Test that additional packages section is absent without arg."""
        result = generate_containerfile("alpine:latest")
        assert "# Install additional packages" not in result

    def test_has_additional_packages_with_arg(self):
        """Test that additional packages section is present with arg."""
        result = generate_containerfile("alpine:latest", additional_packages="git vim")
        assert "# Install additional packages" in result
        assert "git vim" in result

    def test_no_init_hooks_without_arg(self):
        """Test that init hooks section is absent without arg."""
        result = generate_containerfile("alpine:latest")
        assert "# Init hooks" not in result

    def test_has_init_hooks_with_arg(self):
        """Test that init hooks section is present with arg."""
        result = generate_containerfile("alpine:latest", init_hooks="touch /tmp/test")
        assert "# Init hooks" in result
        assert "touch /tmp/test" in result

    def test_no_pre_init_hooks_without_arg(self):
        """Test that pre-init hooks section is absent without arg."""
        result = generate_containerfile("alpine:latest")
        assert "# Pre-init hooks" not in result

    def test_has_pre_init_hooks_with_arg(self):
        """Test that pre-init hooks section is present with arg."""
        result = generate_containerfile("alpine:latest", pre_init_hooks="echo hello")
        assert "# Pre-init hooks" in result
        assert "echo hello" in result

    def test_order_of_sections(self):
        """Test that sections appear in correct order with multi-stage build."""
        result = generate_containerfile(
            "alpine:latest",
            additional_packages="git",
            init_hooks="hook1",
            pre_init_hooks="hook0",
        )
        lines = result.split("\n")

        # Find positions
        init_stage_pos = None
        boost_pos = None
        upgrade_pos = None
        install_pos = None
        pre_hooks_stage_pos = None
        packages_stage_pos = None
        runner_stage_pos = None

        for i, line in enumerate(lines):
            if "FROM alpine:latest AS init" in line:
                init_stage_pos = i
            if "/.distrobox-boost" in line:
                boost_pos = i
            if "# Upgrade" in line:
                upgrade_pos = i
            if "# Install distrobox dependencies" in line:
                install_pos = i
            if "FROM init AS pre-hooks" in line:
                pre_hooks_stage_pos = i
            if "FROM pre-hooks AS packages" in line:
                packages_stage_pos = i
            if "FROM packages AS runner" in line:
                runner_stage_pos = i

        # Verify all stages present
        assert init_stage_pos is not None
        assert boost_pos is not None
        assert upgrade_pos is not None
        assert install_pos is not None
        assert pre_hooks_stage_pos is not None
        assert packages_stage_pos is not None
        assert runner_stage_pos is not None

        # Verify order within init stage
        assert init_stage_pos < boost_pos
        assert boost_pos < upgrade_pos
        assert upgrade_pos < install_pos

        # Verify stage order
        assert install_pos < pre_hooks_stage_pos
        assert pre_hooks_stage_pos < packages_stage_pos
        assert packages_stage_pos < runner_stage_pos

    def test_returns_multiline_string(self):
        """Test that result is a valid multiline Containerfile."""
        result = generate_containerfile("alpine:latest")
        lines = result.split("\n")
        assert len(lines) > 5  # Should have multiple lines
        assert lines[0].startswith("FROM")


class TestMultiStageBuild:
    """Tests for multi-stage build structure."""

    def test_multi_stage_all_options(self):
        """Test that all 4 stages are present when all options provided."""
        result = generate_containerfile(
            "alpine:latest",
            additional_packages="git vim",
            init_hooks="echo init",
            pre_init_hooks="echo pre",
        )

        assert "FROM alpine:latest AS init" in result
        assert "FROM init AS pre-hooks" in result
        assert "FROM pre-hooks AS packages" in result
        assert "FROM packages AS runner" in result

    def test_multi_stage_skip_pre_hooks(self):
        """Test that pre-hooks stage is skipped when no pre_init_hooks."""
        result = generate_containerfile(
            "alpine:latest",
            additional_packages="git",
            init_hooks="echo init",
        )

        assert "FROM alpine:latest AS init" in result
        assert "AS pre-hooks" not in result
        # packages should inherit from init directly
        assert "FROM init AS packages" in result
        assert "FROM packages AS runner" in result

    def test_multi_stage_skip_packages(self):
        """Test that packages stage is skipped when no additional_packages."""
        result = generate_containerfile(
            "alpine:latest",
            init_hooks="echo init",
            pre_init_hooks="echo pre",
        )

        assert "FROM alpine:latest AS init" in result
        assert "FROM init AS pre-hooks" in result
        assert "AS packages" not in result
        # runner should inherit from pre-hooks directly
        assert "FROM pre-hooks AS runner" in result

    def test_multi_stage_only_packages(self):
        """Test with only additional_packages."""
        result = generate_containerfile(
            "alpine:latest",
            additional_packages="git vim",
        )

        assert "FROM alpine:latest AS init" in result
        assert "AS pre-hooks" not in result
        assert "FROM init AS packages" in result
        assert "AS runner" not in result

    def test_multi_stage_base_only(self):
        """Test that only init stage exists when no optional args."""
        result = generate_containerfile("alpine:latest")

        assert "FROM alpine:latest AS init" in result
        assert "AS pre-hooks" not in result
        assert "AS packages" not in result
        assert "AS runner" not in result
        # Verify base content still present
        assert "touch /.distrobox-boost" in result
        assert "# Upgrade existing packages" in result
        assert "# Install distrobox dependencies" in result

    def test_stage_chain_init_to_runner(self):
        """Test correct FROM chain: init -> runner (no middle stages)."""
        result = generate_containerfile(
            "alpine:latest",
            init_hooks="echo init",
        )

        assert "FROM alpine:latest AS init" in result
        assert "FROM init AS runner" in result
        assert "AS pre-hooks" not in result
        assert "AS packages" not in result

    def test_stage_chain_with_pre_hooks_only(self):
        """Test correct FROM chain: init -> pre-hooks (no packages/runner)."""
        result = generate_containerfile(
            "alpine:latest",
            pre_init_hooks="echo pre",
        )

        assert "FROM alpine:latest AS init" in result
        assert "FROM init AS pre-hooks" in result
        assert "AS packages" not in result
        assert "AS runner" not in result

    def test_stage_chain_packages_and_runner(self):
        """Test correct FROM chain when skipping pre-hooks."""
        result = generate_containerfile(
            "alpine:latest",
            additional_packages="git",
            init_hooks="echo init",
        )

        # packages should come from init (not pre-hooks)
        assert "FROM init AS packages" in result
        # runner should come from packages
        assert "FROM packages AS runner" in result

    def test_stage_chain_pre_hooks_and_runner(self):
        """Test correct FROM chain when skipping packages."""
        result = generate_containerfile(
            "alpine:latest",
            init_hooks="echo init",
            pre_init_hooks="echo pre",
        )

        # pre-hooks from init
        assert "FROM init AS pre-hooks" in result
        # runner should come from pre-hooks (not packages)
        assert "FROM pre-hooks AS runner" in result

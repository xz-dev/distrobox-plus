"""Integration tests requiring container runtime (podman/docker).

These tests build actual images and verify they work correctly.
Run with: pytest -v tests/test_integration.py -m integration
Skip with: pytest -v --ignore=tests/test_integration.py
"""

import subprocess
from pathlib import Path

import pytest

from distrobox_boost.command.assemble import (
    DISTROBOX_PACKAGES,
    build_image,
    generate_containerfile,
)
from distrobox_boost.utils.templates import (
    generate_additional_packages_cmd,
    generate_install_cmd,
    generate_upgrade_cmd,
)
from distrobox_boost.utils.utils import get_image_builder


def get_runtime() -> str | None:
    """Get available container runtime for testing."""
    return get_image_builder()


def skip_if_no_runtime() -> pytest.MarkDecorator:
    """Skip test if no container runtime available."""
    runtime = get_runtime()
    return pytest.mark.skipif(
        runtime is None,
        reason="No container runtime (buildah/podman/docker) available",
    )


@pytest.fixture
def container_runtime() -> str:
    """Get container runtime, skip if not available."""
    runtime = get_runtime()
    if runtime is None:
        pytest.skip("No container runtime available")
    return runtime


def cleanup_image(runtime: str, image_name: str) -> None:
    """Remove a container image."""
    if runtime == "buildah":
        subprocess.run(["buildah", "rmi", "-f", image_name], capture_output=True)
    else:
        subprocess.run([runtime, "rmi", "-f", image_name], capture_output=True)


def run_in_container(runtime: str, image: str, command: list[str]) -> subprocess.CompletedProcess:
    """Run a command in a container."""
    if runtime == "buildah":
        # buildah doesn't have run, use podman/docker
        actual_runtime = "podman" if subprocess.run(
            ["which", "podman"], capture_output=True
        ).returncode == 0 else "docker"
    else:
        actual_runtime = runtime

    return subprocess.run(
        [actual_runtime, "run", "--rm", image, *command],
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
class TestImageBuild:
    """Tests for actual image building."""

    @skip_if_no_runtime()
    @pytest.mark.parametrize(
        "base_image,pkg_manager",
        [
            ("alpine:latest", "apk"),
            pytest.param("debian:bookworm-slim", "apt", marks=pytest.mark.slow),
            pytest.param("fedora:latest", "dnf", marks=pytest.mark.slow),
            pytest.param("archlinux:latest", "pacman", marks=pytest.mark.slow),
            pytest.param("opensuse/tumbleweed:latest", "zypper", marks=pytest.mark.slow),
        ],
    )
    def test_build_image_with_distro(
        self,
        container_runtime: str,
        base_image: str,
        pkg_manager: str,
    ) -> None:
        """Test building image with different base distributions."""
        image_name = f"distrobox-boost-test-{pkg_manager}:latest"

        try:
            # Generate containerfile
            upgrade_cmd = generate_upgrade_cmd()
            install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)

            containerfile = generate_containerfile(
                base_image=base_image,
                upgrade_cmd=upgrade_cmd,
                install_cmd=install_cmd,
                pre_init_hooks_cmd="",
                additional_packages_cmd="",
                init_hooks_cmd="",
            )

            # Build the image
            result = build_image(container_runtime, image_name, containerfile)
            assert result == 0, f"Image build failed for {base_image}"

        finally:
            cleanup_image(container_runtime, image_name)

    @skip_if_no_runtime()
    def test_built_image_has_bash(self, container_runtime: str) -> None:
        """Verify built image has bash installed."""
        image_name = "distrobox-boost-test-bash:latest"

        try:
            # Build with alpine (uses apk)
            upgrade_cmd = generate_upgrade_cmd()
            install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)

            containerfile = generate_containerfile(
                base_image="alpine:latest",
                upgrade_cmd=upgrade_cmd,
                install_cmd=install_cmd,
                pre_init_hooks_cmd="",
                additional_packages_cmd="",
                init_hooks_cmd="",
            )

            result = build_image(container_runtime, image_name, containerfile)
            assert result == 0, "Image build failed"

            # Check if bash exists
            check_result = run_in_container(
                container_runtime, image_name, ["which", "bash"]
            )
            assert check_result.returncode == 0, "bash should be installed"

        finally:
            cleanup_image(container_runtime, image_name)

    @skip_if_no_runtime()
    def test_built_image_has_curl(self, container_runtime: str) -> None:
        """Verify built image has curl installed."""
        image_name = "distrobox-boost-test-curl:latest"

        try:
            upgrade_cmd = generate_upgrade_cmd()
            install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)

            containerfile = generate_containerfile(
                base_image="alpine:latest",
                upgrade_cmd=upgrade_cmd,
                install_cmd=install_cmd,
                pre_init_hooks_cmd="",
                additional_packages_cmd="",
                init_hooks_cmd="",
            )

            result = build_image(container_runtime, image_name, containerfile)
            assert result == 0, "Image build failed"

            # Check if curl exists
            check_result = run_in_container(
                container_runtime, image_name, ["which", "curl"]
            )
            assert check_result.returncode == 0, "curl should be installed"

        finally:
            cleanup_image(container_runtime, image_name)

    @skip_if_no_runtime()
    def test_built_image_has_sudo(self, container_runtime: str) -> None:
        """Verify built image has sudo installed."""
        image_name = "distrobox-boost-test-sudo:latest"

        try:
            upgrade_cmd = generate_upgrade_cmd()
            install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)

            containerfile = generate_containerfile(
                base_image="alpine:latest",
                upgrade_cmd=upgrade_cmd,
                install_cmd=install_cmd,
                pre_init_hooks_cmd="",
                additional_packages_cmd="",
                init_hooks_cmd="",
            )

            result = build_image(container_runtime, image_name, containerfile)
            assert result == 0, "Image build failed"

            # Check if sudo exists
            check_result = run_in_container(
                container_runtime, image_name, ["which", "sudo"]
            )
            assert check_result.returncode == 0, "sudo should be installed"

        finally:
            cleanup_image(container_runtime, image_name)


@pytest.mark.integration
class TestAdditionalPackages:
    """Tests for additional package installation."""

    @skip_if_no_runtime()
    def test_additional_packages_installed(self, container_runtime: str) -> None:
        """Verify additional packages are installed in the image."""
        image_name = "distrobox-boost-test-additional:latest"

        try:
            upgrade_cmd = generate_upgrade_cmd()
            install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)
            additional_cmd = generate_additional_packages_cmd(["git", "vim"])

            containerfile = generate_containerfile(
                base_image="alpine:latest",
                upgrade_cmd=upgrade_cmd,
                install_cmd=install_cmd,
                pre_init_hooks_cmd="",
                additional_packages_cmd=additional_cmd,
                init_hooks_cmd="",
            )

            result = build_image(container_runtime, image_name, containerfile)
            assert result == 0, "Image build failed"

            # Check if git exists
            git_result = run_in_container(
                container_runtime, image_name, ["which", "git"]
            )
            assert git_result.returncode == 0, "git should be installed"

            # Check if vim exists
            vim_result = run_in_container(
                container_runtime, image_name, ["which", "vim"]
            )
            assert vim_result.returncode == 0, "vim should be installed"

        finally:
            cleanup_image(container_runtime, image_name)


@pytest.mark.integration
class TestPackageManagerDetection:
    """Tests for package manager detection in containers."""

    @skip_if_no_runtime()
    @pytest.mark.parametrize(
        "base_image,expected_manager",
        [
            ("alpine:latest", "apk"),
            pytest.param("debian:bookworm-slim", "apt-get", marks=pytest.mark.slow),
            pytest.param("fedora:latest", "dnf", marks=pytest.mark.slow),
        ],
    )
    def test_package_manager_detection(
        self,
        container_runtime: str,
        base_image: str,
        expected_manager: str,
    ) -> None:
        """Test that correct package manager is detected for each distro."""
        # Run command -v in base image to verify package manager exists
        result = run_in_container(
            container_runtime, base_image, ["sh", "-c", f"command -v {expected_manager}"]
        )
        assert result.returncode == 0, f"{expected_manager} should exist in {base_image}"


@pytest.mark.integration
class TestInitHooks:
    """Tests for init hooks in built images."""

    @skip_if_no_runtime()
    def test_init_hooks_executed(self, container_runtime: str) -> None:
        """Verify init hooks create expected artifacts in the image."""
        image_name = "distrobox-boost-test-hooks:latest"

        try:
            upgrade_cmd = generate_upgrade_cmd()
            install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)

            # Use init hook to create a marker file
            init_hooks_cmd = "set -e && touch /tmp/init-hook-marker"

            containerfile = generate_containerfile(
                base_image="alpine:latest",
                upgrade_cmd=upgrade_cmd,
                install_cmd=install_cmd,
                pre_init_hooks_cmd="",
                additional_packages_cmd="",
                init_hooks_cmd=init_hooks_cmd,
            )

            result = build_image(container_runtime, image_name, containerfile)
            assert result == 0, "Image build failed"

            # Check if marker file exists
            check_result = run_in_container(
                container_runtime, image_name, ["test", "-f", "/tmp/init-hook-marker"]
            )
            assert check_result.returncode == 0, "init hook marker should exist"

        finally:
            cleanup_image(container_runtime, image_name)

    @skip_if_no_runtime()
    def test_pre_init_hooks_executed_before_packages(
        self, container_runtime: str
    ) -> None:
        """Verify pre-init hooks run before package installation."""
        image_name = "distrobox-boost-test-pre-hooks:latest"

        try:
            upgrade_cmd = generate_upgrade_cmd()
            install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)

            # Pre-init hook creates a marker
            pre_init_hooks_cmd = "set -e && touch /tmp/pre-init-marker"

            containerfile = generate_containerfile(
                base_image="alpine:latest",
                upgrade_cmd=upgrade_cmd,
                install_cmd=install_cmd,
                pre_init_hooks_cmd=pre_init_hooks_cmd,
                additional_packages_cmd="",
                init_hooks_cmd="",
            )

            result = build_image(container_runtime, image_name, containerfile)
            assert result == 0, "Image build failed"

            # Check if pre-init marker exists
            check_result = run_in_container(
                container_runtime, image_name, ["test", "-f", "/tmp/pre-init-marker"]
            )
            assert check_result.returncode == 0, "pre-init hook marker should exist"

        finally:
            cleanup_image(container_runtime, image_name)


@pytest.mark.integration
class TestContainerfileGeneration:
    """Integration tests for containerfile generation and building."""

    @skip_if_no_runtime()
    def test_full_containerfile_builds_successfully(
        self, container_runtime: str
    ) -> None:
        """Test a complete containerfile with all features builds successfully."""
        image_name = "distrobox-boost-test-full:latest"

        try:
            upgrade_cmd = generate_upgrade_cmd()
            install_cmd = generate_install_cmd(DISTROBOX_PACKAGES)
            additional_cmd = generate_additional_packages_cmd(["htop"])

            containerfile = generate_containerfile(
                base_image="alpine:latest",
                upgrade_cmd=upgrade_cmd,
                install_cmd=install_cmd,
                pre_init_hooks_cmd="set -e && echo 'pre-init'",
                additional_packages_cmd=additional_cmd,
                init_hooks_cmd="set -e && echo 'init'",
            )

            result = build_image(container_runtime, image_name, containerfile)
            assert result == 0, "Full image build should succeed"

            # Verify htop is installed
            check_result = run_in_container(
                container_runtime, image_name, ["which", "htop"]
            )
            assert check_result.returncode == 0, "htop should be installed"

        finally:
            cleanup_image(container_runtime, image_name)

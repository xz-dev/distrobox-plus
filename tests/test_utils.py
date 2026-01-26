"""Tests for utils/utils.py."""

from unittest.mock import patch

from distrobox_boost.utils.utils import get_image_builder


class TestGetImageBuilder:
    """Tests for get_image_builder function."""

    @patch("shutil.which")
    def test_returns_buildah_when_available(self, mock_which: patch) -> None:
        """Should return 'buildah' when it is available."""
        mock_which.side_effect = lambda cmd: "/usr/bin/buildah" if cmd == "buildah" else None

        result = get_image_builder()
        assert result == "buildah"

    @patch("shutil.which")
    def test_returns_podman_when_no_buildah(self, mock_which: patch) -> None:
        """Should return 'podman' when buildah is not available."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "podman":
                return "/usr/bin/podman"
            return None

        mock_which.side_effect = which_side_effect

        result = get_image_builder()
        assert result == "podman"

    @patch("shutil.which")
    def test_returns_docker_when_no_others(self, mock_which: patch) -> None:
        """Should return 'docker' when buildah and podman are not available."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd == "docker":
                return "/usr/bin/docker"
            return None

        mock_which.side_effect = which_side_effect

        result = get_image_builder()
        assert result == "docker"

    @patch("shutil.which")
    def test_returns_none_when_none_available(self, mock_which: patch) -> None:
        """Should return None when no image builder is available."""
        mock_which.return_value = None

        result = get_image_builder()
        assert result is None

    @patch("shutil.which")
    def test_priority_order_buildah_over_podman(self, mock_which: patch) -> None:
        """Should prefer buildah over podman when both available."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd in ("buildah", "podman", "docker"):
                return f"/usr/bin/{cmd}"
            return None

        mock_which.side_effect = which_side_effect

        result = get_image_builder()
        assert result == "buildah"

    @patch("shutil.which")
    def test_priority_order_podman_over_docker(self, mock_which: patch) -> None:
        """Should prefer podman over docker when buildah not available."""
        def which_side_effect(cmd: str) -> str | None:
            if cmd in ("podman", "docker"):
                return f"/usr/bin/{cmd}"
            return None

        mock_which.side_effect = which_side_effect

        result = get_image_builder()
        assert result == "podman"

"""Tests for utils/config.py."""

from pathlib import Path

import pytest

from distrobox_boost.utils.config import (
    get_cache_dir,
    get_config_dir,
    get_container_cache_dir,
    get_container_config_dir,
    get_container_config_file,
)


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_returns_path(self, tmp_path: Path) -> None:
        """Should return a Path object."""
        result = get_config_dir(_user_config_dir=lambda _: str(tmp_path))
        assert isinstance(result, Path)

    def test_uses_app_name(self, tmp_path: Path) -> None:
        """Should use distrobox-boost as app name."""
        captured_app_name = None

        def mock_config_dir(app_name: str) -> str:
            nonlocal captured_app_name
            captured_app_name = app_name
            return str(tmp_path / app_name)

        get_config_dir(_user_config_dir=mock_config_dir)
        assert captured_app_name == "distrobox-boost"

    def test_does_not_create_directory(self, tmp_path: Path) -> None:
        """Should not create the base config directory (lazy creation)."""
        config_path = tmp_path / "config"
        result = get_config_dir(_user_config_dir=lambda _: str(config_path))
        assert result == config_path
        assert not config_path.exists()


class TestGetContainerConfigDir:
    """Tests for get_container_config_dir function."""

    def test_returns_path(self, tmp_path: Path) -> None:
        """Should return a Path object."""
        result = get_container_config_dir(
            "test-container", _user_config_dir=lambda _: str(tmp_path)
        )
        assert isinstance(result, Path)

    def test_appends_container_name(self, tmp_path: Path) -> None:
        """Should append container name to config dir."""
        result = get_container_config_dir(
            "my-container", _user_config_dir=lambda _: str(tmp_path)
        )
        assert result == tmp_path / "my-container"

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Should create the container config directory."""
        result = get_container_config_dir(
            "test-container", _user_config_dir=lambda _: str(tmp_path)
        )
        assert result.exists()
        assert result.is_dir()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Should be idempotent - calling twice should succeed."""
        result1 = get_container_config_dir(
            "test-container", _user_config_dir=lambda _: str(tmp_path)
        )
        result2 = get_container_config_dir(
            "test-container", _user_config_dir=lambda _: str(tmp_path)
        )
        assert result1 == result2
        assert result1.exists()


class TestGetContainerConfigFile:
    """Tests for get_container_config_file function."""

    def test_returns_path(self, tmp_path: Path) -> None:
        """Should return a Path object."""
        result = get_container_config_file(
            "test-container", _user_config_dir=lambda _: str(tmp_path)
        )
        assert isinstance(result, Path)

    def test_returns_distrobox_ini_path(self, tmp_path: Path) -> None:
        """Should return path to distrobox.ini file."""
        result = get_container_config_file(
            "my-container", _user_config_dir=lambda _: str(tmp_path)
        )
        assert result == tmp_path / "my-container" / "distrobox.ini"

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """Should create the parent directory but not the file."""
        result = get_container_config_file(
            "test-container", _user_config_dir=lambda _: str(tmp_path)
        )
        assert result.parent.exists()
        assert result.parent.is_dir()
        assert not result.exists()

    def test_file_not_created(self, tmp_path: Path) -> None:
        """Should not create the ini file itself."""
        result = get_container_config_file(
            "test-container", _user_config_dir=lambda _: str(tmp_path)
        )
        assert not result.exists()


class TestGetCacheDir:
    """Tests for get_cache_dir function."""

    def test_returns_path(self, tmp_path: Path) -> None:
        """Should return a Path object."""
        result = get_cache_dir(_user_cache_dir=lambda _: str(tmp_path))
        assert isinstance(result, Path)

    def test_uses_app_name(self, tmp_path: Path) -> None:
        """Should use distrobox-boost as app name."""
        captured_app_name = None

        def mock_cache_dir(app_name: str) -> str:
            nonlocal captured_app_name
            captured_app_name = app_name
            return str(tmp_path / app_name)

        get_cache_dir(_user_cache_dir=mock_cache_dir)
        assert captured_app_name == "distrobox-boost"

    def test_does_not_create_directory(self, tmp_path: Path) -> None:
        """Should not create the base cache directory (lazy creation)."""
        cache_path = tmp_path / "cache"
        result = get_cache_dir(_user_cache_dir=lambda _: str(cache_path))
        assert result == cache_path
        assert not cache_path.exists()


class TestGetContainerCacheDir:
    """Tests for get_container_cache_dir function."""

    def test_returns_path(self, tmp_path: Path) -> None:
        """Should return a Path object."""
        result = get_container_cache_dir(
            "test-container", _user_cache_dir=lambda _: str(tmp_path)
        )
        assert isinstance(result, Path)

    def test_appends_container_name(self, tmp_path: Path) -> None:
        """Should append container name to cache dir."""
        result = get_container_cache_dir(
            "my-container", _user_cache_dir=lambda _: str(tmp_path)
        )
        assert result == tmp_path / "my-container"

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Should create the container cache directory."""
        result = get_container_cache_dir(
            "test-container", _user_cache_dir=lambda _: str(tmp_path)
        )
        assert result.exists()
        assert result.is_dir()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Should be idempotent - calling twice should succeed."""
        result1 = get_container_cache_dir(
            "test-container", _user_cache_dir=lambda _: str(tmp_path)
        )
        result2 = get_container_cache_dir(
            "test-container", _user_cache_dir=lambda _: str(tmp_path)
        )
        assert result1 == result2
        assert result1.exists()

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        """Should create parent directories if needed."""
        nested_path = tmp_path / "deep" / "nested" / "path"
        result = get_container_cache_dir(
            "test-container", _user_cache_dir=lambda _: str(nested_path)
        )
        assert result.exists()
        assert result == nested_path / "test-container"

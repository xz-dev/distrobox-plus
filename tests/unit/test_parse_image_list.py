"""Tests for _parse_image_list function."""

from __future__ import annotations

from distrobox_plus.commands.create import _parse_image_list


class TestParseImageList:
    """Tests for markdown table image list parser."""

    def test_parse_single_image(self):
        """Parse table with single image per row."""
        content = """\
| Distro | Version | Images |
| --- | --- | --- |
| AlmaLinux | 9 | quay.io/almalinux:9 |
| Ubuntu | 22.04 | docker.io/ubuntu:22.04 |
"""
        result = _parse_image_list(content)
        assert result == ["docker.io/ubuntu:22.04", "quay.io/almalinux:9"]

    def test_parse_multiple_images_with_br(self):
        """Parse table with multiple images separated by <br>."""
        content = """\
| Distro | Version | Images |
| --- | --- | --- |
| AlmaLinux | 8 <br> 9 | quay.io/alma:8 <br> quay.io/alma:9 |
| Fedora | 40 | registry.fedora:40 |
"""
        result = _parse_image_list(content)
        assert result == [
            "quay.io/alma:8",
            "quay.io/alma:9",
            "registry.fedora:40",
        ]

    def test_parse_skips_separator_line(self):
        """Parser should skip separator line (--- or :---)."""
        content = """\
| Distro | Version | Images |
| :--- | :---: | ---: |
| Alpine | 3.19 | docker.io/alpine:3.19 |
"""
        result = _parse_image_list(content)
        assert "---" not in result
        assert ":---:" not in result
        assert result == ["docker.io/alpine:3.19"]

    def test_parse_ignores_tables_without_images_header(self):
        """Parser should ignore tables without Images column."""
        content = """\
| Other | Table | Here |
| --- | --- | --- |
| Foo | bar | docker.io/should-be-ignored:latest |

| Distro | Version | Images |
| --- | --- | --- |
| Alpine | 3.19 | docker.io/alpine:3.19 |
"""
        result = _parse_image_list(content)
        assert "docker.io/should-be-ignored:latest" not in result
        assert result == ["docker.io/alpine:3.19"]

    def test_parse_stops_at_table_end(self):
        """Parser should stop when table ends (non-pipe line)."""
        content = """\
| Distro | Version | Images |
| --- | --- | --- |
| Alpine | 3.19 | docker.io/alpine:3.19 |

Some text after table.

| Another | Table | Images |
| --- | --- | --- |
| Foo | bar | docker.io/another:latest |
"""
        result = _parse_image_list(content)
        # Should include both tables since both have Images header
        assert "docker.io/alpine:3.19" in result
        assert "docker.io/another:latest" in result

    def test_parse_empty_content(self):
        """Parse empty content returns empty list."""
        result = _parse_image_list("")
        assert result == []

    def test_parse_no_images_column(self):
        """Parse content without Images column returns empty."""
        content = """\
| Distro | Version | Link |
| --- | --- | --- |
| Alpine | 3.19 | https://example.com |
"""
        result = _parse_image_list(content)
        assert result == []

    def test_parse_deduplicates_images(self):
        """Parser should deduplicate identical images."""
        content = """\
| Distro | Version | Images |
| --- | --- | --- |
| AlmaLinux | 8 | quay.io/alma:latest <br> quay.io/alma:latest |
| AlmaLinux | 9 | quay.io/alma:latest |
"""
        result = _parse_image_list(content)
        assert result == ["quay.io/alma:latest"]

    def test_parse_strips_whitespace(self):
        """Parser should strip whitespace from image names."""
        content = """\
| Distro | Version | Images |
| --- | --- | --- |
| Alpine |  3.19  |   docker.io/alpine:3.19   |
"""
        result = _parse_image_list(content)
        assert result == ["docker.io/alpine:3.19"]

    def test_parse_handles_empty_cells(self):
        """Parser should handle empty image cells gracefully."""
        content = """\
| Distro | Version | Images |
| --- | --- | --- |
| AlmaLinux | 9 |  |
| Alpine | 3.19 | docker.io/alpine:3.19 |
"""
        result = _parse_image_list(content)
        assert result == ["docker.io/alpine:3.19"]

    def test_parse_returns_sorted_list(self):
        """Parser should return sorted list."""
        content = """\
| Distro | Version | Images |
| --- | --- | --- |
| Zzz | 1 | zzz:latest |
| Aaa | 1 | aaa:latest |
| Mmm | 1 | mmm:latest |
"""
        result = _parse_image_list(content)
        assert result == ["aaa:latest", "mmm:latest", "zzz:latest"]

    def test_parse_images_column_different_position(self):
        """Parser should find Images column regardless of position."""
        content = """\
| Images | Distro | Version |
| --- | --- | --- |
| docker.io/alpine:3.19 | Alpine | 3.19 |
"""
        result = _parse_image_list(content)
        assert result == ["docker.io/alpine:3.19"]

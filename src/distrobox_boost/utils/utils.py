"""Utility functions."""

import shutil


def get_image_builder() -> str | None:
    """Detect available image builder (buildah, podman, or docker).

    Priority: buildah > podman > docker
    buildah is preferred as it's specialized for building images.
    """
    for builder in ("buildah", "podman", "docker"):
        if shutil.which(builder):
            return builder
    return None

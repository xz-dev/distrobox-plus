"""Custom exceptions for distrobox-plus."""

from __future__ import annotations


class DistroboxError(Exception):
    """Base exception for distrobox-plus errors."""

    exit_code: int = 1

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class ContainerManagerError(DistroboxError):
    """Error related to container manager operations."""

    pass


class ContainerManagerNotFoundError(ContainerManagerError):
    """No container manager found on the system."""

    exit_code = 127


class InvalidContainerManagerError(ContainerManagerError):
    """Invalid container manager specified."""

    pass

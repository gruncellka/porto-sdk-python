"""Path validation using stat/exists + is_file."""

from pathlib import Path

from ...errors import ConfigurationError, PortoErrorCode


def ensure_path_is_file(data_path: Path, relative_path: str) -> None:
    """Ensure path exists and is a regular file."""
    absolute_path = data_path / relative_path
    if not absolute_path.exists():
        raise ConfigurationError(
            f"Required porto-data path not found: '{relative_path}'.",
            PortoErrorCode.PORTO_DATA_NOT_FOUND,
            status_code=500,
        )
    if not absolute_path.is_file():
        raise ConfigurationError(
            f"Porto-data path is a directory, not a file: '{relative_path}'.",
            PortoErrorCode.PORTO_DATA_NOT_FOUND,
            status_code=500,
        )

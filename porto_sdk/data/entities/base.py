"""
Base Entity Loader - Abstract base class for all entity loaders

All entity loaders inherit from this class and implement:
- load(): Transform JSON data to typed objects
- get_data(): Return loaded entity data
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseEntityLoader(ABC):
    """
    Base class for all entity loaders

    Each entity loader:
    1. Loads JSON data for that entity
    2. Transforms JSON to typed objects
    3. Provides query methods specific to that entity
    4. Handles entity-specific business logic
    """

    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        """
        Initialize entity loader

        Args:
            data_path: Path to porto-data directory
            checksum_map: Pre-built checksum map from metadata.json
        """
        self.data_path = data_path
        self.checksum_map = checksum_map

    @abstractmethod
    def load(self, data: dict[str, Any]) -> None:
        """
        Load and transform entity data from JSON

        Args:
            data: Parsed JSON data from file
        """

    @abstractmethod
    def get_data(self) -> Any:
        """
        Get loaded entity data

        Returns:
            Loaded entity data (type depends on entity)
        """

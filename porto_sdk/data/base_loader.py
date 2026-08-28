"""
Base Loader - Common file loading, checksum verification, and dependency resolution

Handles all common operations shared across entity loaders:
- File loading and parsing
- Checksum verification
- Metadata loading
- Data links loading
- Dependency resolution (topological sort)
"""

import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from .graph_normalize import normalize_resolution_graph
from .types import ResolutionGraph


class BaseLoader:
    """
    Base loader with common file loading operations

    Provides:
    - File loading with checksum verification
    - Metadata loading and checksum map building
    - Data links loading
    - Dependency resolution (topological sort)
    """

    def __init__(self, data_path: Path, verify_checksums: bool = True):
        self.data_path = data_path
        self.verify_checksums = verify_checksums
        self._metadata: dict[str, Any] | None = None
        self.checksum_map: dict[str, str] = {}  # path -> checksum from metadata

    def load_metadata(self) -> dict[str, Any] | None:
        """
        Load metadata.json to understand entity structure

        Metadata defines all entities and their file paths.
        Entity keys match file_type values in JSON files.
        """
        try:
            # Load metadata without checksum verification (chicken-and-egg problem)
            relative_path = "metadata.json"
            file_path = self.data_path / relative_path
            with open(file_path, "r", encoding="utf-8") as f:
                self._metadata = json.load(f)

            # Build checksum map after loading metadata
            if self._metadata:
                self._build_checksum_map()

            return self._metadata
        except Exception:
            # Metadata is optional - if not found, continue without it
            return None

    def _build_checksum_map(self) -> None:
        """Build path -> checksum map from metadata.json (source of truth)"""
        if not self._metadata:
            return
        self.checksum_map = {}
        for entity_data in self._iter_metadata_entities():
            for key in ("data", "schema"):
                info = entity_data.get(key, {})
                path = info.get("path", "")
                checksum = info.get("checksum", "")
                if path and checksum:
                    normalized_path = path.replace("\\", "/")
                    self.checksum_map[normalized_path] = checksum

    def _iter_metadata_entities(self):
        """Yield entity dicts from either the flat ``entities`` map or the sectioned
        metadata layout (policy, formats, registry, global, providers)."""
        if not self._metadata:
            return

        def walk(node: Any) -> None:  # type: ignore[misc]
            if not isinstance(node, dict):
                return
            if "data" in node or "schema" in node:
                yield node
                return
            for value in node.values():
                yield from walk(value)  # type: ignore[func-returns-value, misc]

        if "entities" in self._metadata:
            for entity in (self._metadata.get("entities") or {}).values():
                yield entity
            return

        for section in ("policy", "formats", "registry", "global", "providers"):
            block = self._metadata.get(section)
            if block:
                yield from walk(block)  # type: ignore[func-returns-value, misc]

    def _resolve_relative_path(self, filename: str) -> str:
        """Resolve porto-data relative path (root layout)."""
        return filename

    def load_data(self, filename: str) -> dict[str, Any]:
        """
        Load and parse a porto-data JSON file

        Verifies checksum if enabled and metadata is available.
        Uses metadata.json as source of truth for file paths and checksums.
        """
        relative_path = self._resolve_relative_path(filename)
        file_path = self.data_path / relative_path

        try:
            if self.verify_checksums:
                self._verify_file_checksum(file_path, relative_path)

            with open(file_path, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return data
        except Exception as e:
            raise RuntimeError(f"Failed to load porto-data file: {filename}. Error: {e}")

    def _get_metadata_entity_keys(self):
        """Return set of entity type names from metadata."""
        if "entities" in self._metadata:  # type: ignore[operator]
            return set((self._metadata.get("entities") or {}).keys())  # type: ignore[union-attr]
        keys: set[str] = set()
        for section in ("policy", "formats", "registry", "global"):
            block = self._metadata.get(section) or {}  # type: ignore[union-attr]
            keys.update(block.keys())
        for provider_entities in (self._metadata.get("providers") or {}).values():  # type: ignore[union-attr]
            if isinstance(provider_entities, dict):
                keys.update(provider_entities.keys())
        return keys

    def load_resolution_graph(self) -> ResolutionGraph:
        """Load provider graph.json."""
        provider = getattr(self, "provider", None) or "deutschepost"
        for relative_path in (
            f"providers/{provider}/graph.json",
            "graph.json",
        ):
            try:
                data = self.load_data(relative_path)
                break
            except RuntimeError:
                data = None
        if not data:
            raise RuntimeError("Missing graph.json in porto-data")

        file_type = data.get("file_type")
        if self._metadata and file_type:
            valid_types = self._get_metadata_entity_keys()
            if file_type not in valid_types:
                raise RuntimeError(
                    f"File_type '{file_type}' not found in metadata.json. "
                    f"Expected one of: {', '.join(sorted(valid_types))}"
                )

        return normalize_resolution_graph(data)

    def _verify_file_checksum(self, file_path: Path, relative_path: str) -> None:
        """
        Verify file checksum using metadata.json as source of truth.
        Simple lookup from pre-built checksum map.
        """
        if not self.checksum_map:
            return  # No metadata or checksums available

        # Normalize path for lookup
        normalized_path = relative_path.replace("\\", "/")
        expected_checksum = self.checksum_map.get(normalized_path)

        if not expected_checksum:
            return  # No checksum recorded for this file — nothing to verify

        # Calculate and compare checksum (same logic as porto-data project)
        with open(file_path, "rb") as f:
            actual_checksum = hashlib.sha256(f.read()).hexdigest()

        if actual_checksum != expected_checksum:
            raise RuntimeError(
                f"Checksum verification failed for {relative_path}. "
                f"Expected: {expected_checksum}, Actual: {actual_checksum}. "
                f"File may be corrupted or tampered with."
            )

    def calculate_load_order(self, resolution_graph: ResolutionGraph) -> list[str]:
        """
        Calculate file load order using topological sort of dependencies

        Handles circular dependencies by breaking cycles (loads zones before restrictions
        if there's a cycle between them).

        Returns list of file names in correct load order.
        """
        # Build dependency graph
        graph: dict[str, set[str]] = defaultdict(set)
        file_to_key: dict[str, str] = {}

        for key, dep_info in resolution_graph.dependencies.items():
            file_name = dep_info["file"]
            file_to_key[file_name] = key
            for dep_file in dep_info.get("depends_on", []):
                graph[file_name].add(dep_file)

        # Topological sort
        in_degree: dict[str, int] = defaultdict(int)
        for file_name in file_to_key:
            in_degree[file_name] = 0

        for file_name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[file_name] += 1

        queue = deque([f for f, degree in in_degree.items() if degree == 0])
        load_order: list[str] = []
        processed: set[str] = set()

        while queue:
            file_name = queue.popleft()
            if file_name in processed:
                continue
            load_order.append(file_name)
            processed.add(file_name)

            # Find files that depend on this one
            for other_file, deps in graph.items():
                if file_name in deps:
                    in_degree[other_file] -= 1
                    if in_degree[other_file] == 0:
                        queue.append(other_file)

        # Handle circular dependencies: if zones and restrictions both remain unprocessed,
        # break the cycle by loading zones first (it has fewer dependencies)
        remaining = [f for f in file_to_key if f not in processed]
        if "zones.json" in remaining and "restrictions.json" in remaining:
            # Break cycle: load zones first, then restrictions
            if "zones.json" not in load_order:
                load_order.append("zones.json")
                processed.add("zones.json")
            if "restrictions.json" not in load_order:
                load_order.append("restrictions.json")
                processed.add("restrictions.json")
            remaining = [f for f in remaining if f not in ["zones.json", "restrictions.json"]]

        # Add any remaining files (shouldn't happen, but handle gracefully)
        for file_name in remaining:
            if file_name not in processed:
                load_order.append(file_name)
                processed.add(file_name)

        return load_order

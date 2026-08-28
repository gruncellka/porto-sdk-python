"""Provider conditional rules (e.g. Swiss Post thickness surcharge)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseEntityLoader


@dataclass
class PortoProviderRules:
    rules: list[dict[str, Any]] = field(default_factory=list)


class RulesLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._rules = PortoProviderRules()

    def load(self, data: dict[str, Any]) -> None:
        self._rules = PortoProviderRules(rules=list(data.get("rules") or []))

    def get_data(self) -> PortoProviderRules:
        return self._rules

    def get_rules(self) -> list[dict[str, Any]]:
        return self._rules.rules

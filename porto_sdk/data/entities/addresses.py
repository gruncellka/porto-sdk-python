"""Addresses entity loader — formats/addresses.json"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from re import Pattern
from typing import Any

from .base import BaseEntityLoader


@dataclass
class AddressFormKind:
    kind: str
    required: list[str]


@dataclass
class AddressJurisdictionForm:
    """Jurisdiction-level address catalog (postal pattern + form kinds)."""

    jurisdiction: str
    standard: str
    postal_code_pattern: str
    forms: list[AddressFormKind]
    max_line_length: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    _compiled: Pattern[str] | None = field(default=None, repr=False, compare=False)

    def postal_code_re(self) -> Pattern[str]:
        if self._compiled is None:
            self._compiled = re.compile(self.postal_code_pattern)
        return self._compiled

    def get_kind(self, kind: str) -> AddressFormKind | None:
        for form in self.forms:
            if form.kind == kind:
                return form
        return None


class AddressesLoader(BaseEntityLoader):
    def __init__(self, data_path: Path, checksum_map: dict[str, str]):
        super().__init__(data_path, checksum_map)
        self._forms: dict[str, AddressJurisdictionForm] = {}

    def load(self, data: dict[str, Any]) -> None:
        self._forms = {}
        jurisdictions = data.get("jurisdictions") or {}
        for jurisdiction, payload in jurisdictions.items():
            if not isinstance(payload, dict):
                continue
            postal = payload.get("postal_code") or {}
            pattern = postal.get("pattern") if isinstance(postal, dict) else None
            if not isinstance(pattern, str) or not pattern:
                continue
            standard = payload.get("standard")
            if not isinstance(standard, str) or not standard:
                continue
            forms_raw = payload.get("forms") or []
            if not isinstance(forms_raw, list) or not forms_raw:
                continue
            kinds: list[AddressFormKind] = []
            for row in forms_raw:
                if not isinstance(row, dict):
                    continue
                kind = row.get("kind")
                required = row.get("required") or []
                if not isinstance(kind, str) or not isinstance(required, list):
                    continue
                kinds.append(AddressFormKind(kind=kind, required=[str(f) for f in required]))
            if not kinds:
                continue
            max_line = payload.get("max_line_length")
            self._forms[str(jurisdiction).upper()] = AddressJurisdictionForm(
                jurisdiction=str(jurisdiction).upper(),
                standard=standard,
                postal_code_pattern=pattern,
                forms=kinds,
                max_line_length=int(max_line) if isinstance(max_line, int) else None,
                raw=payload,
            )

    def get_data(self) -> dict[str, AddressJurisdictionForm]:
        return self._forms

    def get_form(self, jurisdiction: str) -> AddressJurisdictionForm | None:
        return self._forms.get(str(jurisdiction).upper())

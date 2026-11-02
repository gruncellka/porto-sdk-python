"""Step definitions for sdk/core/status.feature."""

from __future__ import annotations

import json

from pytest_bdd import parsers, then

from tests.support.porto_features_path import get_porto_features_root


@then(parsers.parse('"{code}" should be declared in the PortoStatus catalog'))
def porto_status_declared(code: str) -> None:
    path = get_porto_features_root() / "statuses.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    declared = {str(row["code"]) for row in doc["codes"]}
    assert code in declared

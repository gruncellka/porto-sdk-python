# Porto SDK Python — Bugbot

Scope: this repo only (`gruncellka-porto-sdk` / `porto-sdk-python`). Flag cross-SDK risks; do not prescribe consumer-app changes.

## Blocking

### 1) Behavior change without tests

PR changes `porto_sdk/**` resolver, adapter, or CLI behavior and does not update `tests/**`.

- Bug: `Behavior change without tests`
- Body: `Add or update unit, integration, or BDD coverage. Run make check.`
- Label: `quality`

### 2) BDD batch contract drift

PR changes `tests/bdd/steps/**`, `tests/bdd/runner/**`, or `scripts/run_bdd_batches.py` without either matching TypeScript `batches.ts` ids or a PR note of intentional one-sided drift.

- Bug: `BDD batch contract drift risk`
- Body: `Keep batch ids aligned with porto-features and the TypeScript SDK runner.`
- Labels: `integration`, `quality`

### 3) Non-registry dependency in committed manifest

`pyproject.toml` (or committed hook config) adds `file:`, `resources/`, or editable local paths to dependency specs.

- Bug: `Non-registry dependency in committed manifest`
- Body: `Committed manifests use PyPI semver only. Run make registry.`
- Label: `release-blocker`

### 4) Execution manifest vs wire tables

Execution wiring reads product/checkout codes from `execution.json` instead of `graph.edges.wire`, or gates billing/execution without `execution.json` billing/execution lists.

- Bug: `SDK conflates execution manifest with wire tables`
- Body: `execution.json = wire + billing/execution methods; graph.edges.wire = checkout codes.`
- Labels: `architecture`, `integration`

## Non-blocking

### 5) Mark geometry hardcoded

Mark/stamp IO hardcodes mm/px instead of `marks.calibrations[]` from porto-data.

- Bug: `Mark geometry hardcoded instead of catalog calibrations`
- Label: `maintainability`

### 6) Untracked TODO/FIXME

TODO/FIXME without issue reference (`#123`).

- Bug: `Untracked TODO/FIXME comment`
- Label: `maintainability`

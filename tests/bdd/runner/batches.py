"""Single source of truth for @sdk BDD batch definitions (Python SDK).

Keep ids, order, and globs aligned with sdks/porto-sdk-typescript/tests/bdd/runner/batches.ts
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BddBatchGroup(StrEnum):
    CLI = "cli"
    CORE = "core"
    PROVIDER = "provider"
    ADAPTERS = "adapters"


@dataclass(frozen=True, slots=True)
class BddBatch:
    """One runnable slice of test_bdd.py scenarios."""

    id: str
    label: str
    group: BddBatchGroup
    feature_glob: str | None = None
    keyword_filter: str | None = None
    tags: str | None = None
    publish_gated: bool = False

    def validate(self) -> None:
        if not self.feature_glob and not self.keyword_filter:
            raise ValueError(f"batch {self.id!r} needs feature_glob and/or keyword_filter")


BDD_BATCHES: tuple[BddBatch, ...] = (
    BddBatch(
        id="cli-core",
        label="CLI · core",
        group=BddBatchGroup.CLI,
        feature_glob="core/cli.feature",
    ),
    BddBatch(
        id="cli-deutschepost",
        label="CLI · deutschepost",
        group=BddBatchGroup.CLI,
        feature_glob="providers/deutschepost/cli.feature",
    ),
    BddBatch(
        id="cli-ukrposhta",
        label="CLI · ukrposhta",
        group=BddBatchGroup.CLI,
        feature_glob="providers/ukrposhta/cli.feature",
    ),
    BddBatch(
        id="cli-laposte",
        label="CLI · laposte",
        group=BddBatchGroup.CLI,
        feature_glob="providers/laposte/cli.feature",
    ),
    BddBatch(
        id="cli-swisspost",
        label="CLI · swisspost",
        group=BddBatchGroup.CLI,
        feature_glob="providers/swisspost/cli.feature",
    ),
    BddBatch(
        id="core-data",
        label="Core · data access",
        group=BddBatchGroup.CORE,
        feature_glob="core/data.feature",
    ),
    BddBatch(
        id="core-metadata",
        label="Core · metadata",
        group=BddBatchGroup.CORE,
        feature_glob="core/metadata.feature",
    ),
    BddBatch(
        id="core-resolution",
        label="Core · public resolution",
        group=BddBatchGroup.CORE,
        feature_glob="core/resolution.feature",
    ),
    BddBatch(
        id="core-restrictions",
        label="Core · restrictions",
        group=BddBatchGroup.CORE,
        feature_glob="core/restrictions.feature",
    ),
    BddBatch(
        id="core-validation",
        label="Core · validation",
        group=BddBatchGroup.CORE,
        feature_glob="core/validation.feature",
    ),
    BddBatch(
        id="core-errors",
        label="Core · normalized errors",
        group=BddBatchGroup.CORE,
        feature_glob="core/errors.feature",
    ),
    BddBatch(
        id="core-mark",
        label="Core · mark",
        group=BddBatchGroup.CORE,
        feature_glob="core/mark.feature",
    ),
    BddBatch(
        id="deutschepost-resolution",
        label="Deutsche Post · resolution",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/deutschepost/resolution.feature",
    ),
    BddBatch(
        id="deutschepost-pricing",
        label="Deutsche Post · pricing",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/deutschepost/pricing.feature",
    ),
    BddBatch(
        id="deutschepost-services",
        label="Deutsche Post · services",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/deutschepost/services.feature",
    ),
    BddBatch(
        id="deutschepost-products",
        label="Deutsche Post · products",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/deutschepost/products.feature",
    ),
    BddBatch(
        id="ukrposhta-resolution",
        label="Ukrposhta · resolution",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/ukrposhta/resolution.feature",
    ),
    BddBatch(
        id="ukrposhta-products",
        label="Ukrposhta · products",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/ukrposhta/products.feature",
    ),
    BddBatch(
        id="laposte-resolution",
        label="La Poste · resolution",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/laposte/resolution.feature",
    ),
    BddBatch(
        id="laposte-products",
        label="La Poste · products",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/laposte/products.feature",
    ),
    BddBatch(
        id="swisspost-resolution",
        label="Swiss Post · resolution",
        group=BddBatchGroup.PROVIDER,
        feature_glob="providers/swisspost/resolution.feature",
    ),
    BddBatch(
        id="adapters-internetmarke-errors",
        label="Adapters · Internetmarke errors",
        group=BddBatchGroup.ADAPTERS,
        feature_glob="deutschepost/internetmarke/errors.feature",
    ),
    BddBatch(
        id="adapters-internetmarke-marks-canary",
        label="Adapters · Internetmarke marks canary",
        group=BddBatchGroup.ADAPTERS,
        feature_glob="deutschepost/internetmarke/marks.feature",
        keyword_filter="purchase_mark_with_pricing",
        tags="@adapters and @canary",
        publish_gated=True,
    ),
    BddBatch(
        id="adapters-internetmarke-marks-full",
        label="Adapters · Internetmarke marks full",
        group=BddBatchGroup.ADAPTERS,
        feature_glob="deutschepost/internetmarke/marks.feature",
        tags="@adapters and (@canary or @heavy)",
        publish_gated=True,
    ),
)


def batches_for(
    *,
    batch_id: str | None = None,
    group: BddBatchGroup | None = None,
) -> list[BddBatch]:
    selected = list(BDD_BATCHES)
    if group is not None:
        selected = [b for b in selected if b.group == group]
    if batch_id is not None:
        selected = [b for b in selected if b.id == batch_id]
        if not selected:
            known = ", ".join(b.id for b in BDD_BATCHES)
            raise SystemExit(f"Unknown batch {batch_id!r}. Known: {known}")
    else:
        selected = [b for b in selected if not b.publish_gated]
    for batch in selected:
        batch.validate()
    return selected

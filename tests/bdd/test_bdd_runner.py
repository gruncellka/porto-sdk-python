"""Tests for BDD batch runner helpers."""

from pathlib import Path
from xml.etree.ElementTree import Element

from tests.bdd.runner.batches import BDD_BATCHES, BddBatchGroup, batches_for
from tests.bdd.runner.providers import PROVIDER_IDS
from tests.bdd.runner.reporter import Reporter
from tests.bdd.runner.runner import _parse_junit


def test_cli_batches_follow_provider_bundle_order():
    cli_provider_ids = [
        b.id.removeprefix("cli-")
        for b in batches_for(group=BddBatchGroup.CLI)
        if b.id.startswith("cli-") and b.id != "cli-core"
    ]
    assert cli_provider_ids == list(PROVIDER_IDS)


def test_batches_for_group_cli():
    cli = batches_for(group=BddBatchGroup.CLI)
    assert len(cli) == 5
    assert cli[0].feature_glob == "core/cli.feature"
    assert cli[1].feature_glob == "providers/deutschepost/cli.feature"
    assert cli[-1].feature_glob == "providers/swisspost/cli.feature"


def test_batches_for_unknown_batch_exits():
    try:
        batches_for(batch_id="does-not-exist")
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("expected SystemExit")


def test_parse_junit_counts_failures(tmp_path: Path):
    junit = tmp_path / "case.xml"
    root = Element("testsuite")
    ok = Element("testcase", name="test_ok")
    bad = Element("testcase", name="test_bad")
    bad.append(Element("failure", message="boom"))
    root.extend([ok, bad])
    from xml.etree.ElementTree import ElementTree

    ElementTree(root).write(junit, encoding="unicode")

    passed, failed, skipped, errors, names, scenarios = _parse_junit(junit)
    assert passed == 1
    assert failed == 1
    assert skipped == 0
    assert errors == 0
    assert names == ["test_bad"]
    assert len(scenarios) == 2


def test_all_batches_have_unique_ids():
    ids = [b.id for b in BDD_BATCHES]
    assert len(ids) == len(set(ids))


def test_print_batch_list_is_grouped(capsys):
    Reporter().print_batch_list(BDD_BATCHES)
    out = capsys.readouterr().out
    assert "BDD batches (24)" in out
    assert "cli-core" in out
    assert "swisspost-resolution" in out
    assert "make sdk" in out
    assert out.index("cli-core") < out.index("core-data")
    assert out.index("core-data") < out.index("deutschepost-resolution")


def test_batches_for_group_adapters_excludes_paid():
    adapters = batches_for(group=BddBatchGroup.ADAPTERS)
    assert [b.id for b in adapters] == ["adapters-internetmarke-errors"]


def test_batch_publish_gated_only_by_id():
    canary = batches_for(batch_id="adapters-internetmarke-marks-canary")
    assert canary[0].publish_gated is True
    assert batches_for()  # default excludes publish_gated
    assert all(not b.publish_gated for b in batches_for())

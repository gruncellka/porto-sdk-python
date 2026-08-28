"""Execute @sdk BDD batches with visible progress and machine-readable summaries."""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from tests.bdd.runner.batches import BDD_BATCHES, BddBatch, BddBatchGroup, batches_for
from tests.bdd.runner.reporter import BatchResult, Reporter, ScenarioResult
from tests.support.porto_features_path import get_porto_data_path, get_porto_features_root

SDK_ROOT = Path(__file__).resolve().parents[3]

_ACTIVE_PROC: subprocess.Popen[str] | None = None

_NOISE_PATTERNS = (
    "warnings summary",
    "test session starts",
    "collected ",
    "deselected",
    "docs.pytest.org",
    "generated xml file",
    "plugins:",
    "platform ",
    "rootdir:",
    "configfile:",
    "asyncio:",
    "=====",
    "-----",
    "passed, ",
    "PytestUnknownMarkWarning",
    "DeprecationWarning",
)


def _resolve_pytest() -> Path:
    for name in (".venv", "venv"):
        candidate = SDK_ROOT / name / "bin" / "pytest"
        if candidate.is_file():
            return candidate
    pytest = Path(sys.executable).parent / "pytest"
    if pytest.is_file():
        return pytest
    raise SystemExit("pytest not found — run: python -m venv .venv && pip install -e '.[dev]'")


def _scenario_status(case: ET.Element) -> tuple[str, str | None]:
    failure = case.find("failure")
    if failure is not None:
        return "failed", (failure.text or failure.attrib.get("message", "")).strip() or None
    error = case.find("error")
    if error is not None:
        return "error", (error.text or error.attrib.get("message", "")).strip() or None
    if case.attrib.get("skipped") is not None or case.find("skipped") is not None:
        return "skipped", None
    return "passed", None


def _parse_junit(path: Path) -> tuple[int, int, int, int, list[str], list[ScenarioResult]]:
    if not path.is_file():
        return 0, 0, 0, 0, [], []

    root = ET.parse(path).getroot()
    failed_names: list[str] = []
    scenarios: list[ScenarioResult] = []
    passed = failed = skipped = errors = 0

    for case in root.iter("testcase"):
        name = case.attrib.get("name", "?")
        duration = float(case.attrib.get("time", "0") or 0)
        status, message = _scenario_status(case)
        scenarios.append(
            ScenarioResult(name=name, status=status, duration_s=duration, message=message)
        )

        if status == "failed":
            failed += 1
            failed_names.append(name)
        elif status == "error":
            errors += 1
            failed_names.append(name)
        elif status == "skipped":
            skipped += 1
        else:
            passed += 1

    return passed, failed, skipped, errors, failed_names, scenarios


def _default_env(features_path: Path, data_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PORTO_FEATURES_PATH", str(features_path.resolve()))
    env.setdefault("PORTO_DATA_PATH", str(data_path.resolve()))
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _terminate_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith(".") and "passed" not in stripped.lower():
        return True
    lower = stripped.lower()
    return any(token in lower for token in _NOISE_PATTERNS)


def _apply_batch_env(env: dict[str, str], batch: BddBatch) -> dict[str, str]:
    batch_env = env.copy()
    batch_env["BDD_FEATURE_TREE"] = "adapters" if batch.group == BddBatchGroup.ADAPTERS else "sdk"
    if batch.feature_glob:
        batch_env["BDD_FEATURE_GLOB"] = batch.feature_glob
    else:
        batch_env.pop("BDD_FEATURE_GLOB", None)
    return batch_env


def _collect_batch_tests(
    pytest_bin: Path,
    batch: BddBatch,
    env: dict[str, str],
    *,
    apply_keyword: bool = True,
) -> list[str]:
    batch_env = _apply_batch_env(env, batch)

    cmd = [
        str(pytest_bin),
        "tests/bdd/test_bdd.py",
        "--collect-only",
        "-q",
        "--disable-warnings",
    ]
    if apply_keyword and batch.keyword_filter:
        cmd.extend(["-k", batch.keyword_filter])

    proc = subprocess.run(
        cmd,
        cwd=SDK_ROOT,
        env=batch_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    names: list[str] = []
    for line in proc.stdout.splitlines():
        match = re.search(r"::(test_[^\s]+)", line)
        if match:
            names.append(match.group(1))
    return names


def _batch_scope(
    pytest_bin: Path,
    batch: BddBatch,
    env: dict[str, str],
) -> tuple[list[str], int, int]:
    selected = _collect_batch_tests(pytest_bin, batch, env, apply_keyword=True)
    in_file = _collect_batch_tests(pytest_bin, batch, env, apply_keyword=False)
    in_scope = len(in_file)
    deselected = max(in_scope - len(selected), 0)
    return selected, in_scope, deselected


def _stream_pytest_output(
    stdout: TextIO,
    *,
    reporter: Reporter,
    verbose: bool,
) -> None:
    for line in stdout:
        stripped = line.rstrip()
        if verbose:
            if not _is_noise_line(stripped):
                sys.stdout.write(line)
                sys.stdout.flush()
        reporter.batch_progress(line)


def _sigint_handler(_signum: int, _frame: object) -> None:
    if _ACTIVE_PROC is not None and _ACTIVE_PROC.poll() is None:
        _terminate_process(_ACTIVE_PROC)
    raise KeyboardInterrupt


def run_batch(
    batch: BddBatch,
    *,
    pytest_bin: Path,
    env: dict[str, str],
    run_dir: Path,
    reporter: Reporter,
    verbose: bool = False,
) -> BatchResult:
    global _ACTIVE_PROC

    batch_env = _apply_batch_env(env, batch)

    junit_path = run_dir / f"{batch.id}.xml"
    pending_tests, in_scope, deselected = _batch_scope(pytest_bin, batch, env)
    reporter.begin_batch()

    cmd = [
        str(pytest_bin),
        "tests/bdd/test_bdd.py",
        "--tb=line",
        "--color=yes",
        "-rN",
        "--disable-warnings",
        "--no-header",
        "--no-summary",
        f"--junitxml={junit_path}",
        "-v",
    ]
    if batch.keyword_filter:
        cmd.extend(["-k", batch.keyword_filter])

    started = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=SDK_ROOT,
        env=batch_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    _ACTIVE_PROC = proc
    interrupted = False
    try:
        assert proc.stdout is not None
        _stream_pytest_output(proc.stdout, reporter=reporter, verbose=verbose)
        exit_code = proc.wait()
    except KeyboardInterrupt:
        interrupted = True
        _terminate_process(proc)
        exit_code = proc.wait() if proc.poll() is None else proc.returncode or 130
    finally:
        _ACTIVE_PROC = None

    duration_s = time.monotonic() - started
    passed, failed, skipped, errors, failed_tests, scenarios = _parse_junit(junit_path)

    result = BatchResult(
        batch_id=batch.id,
        label=batch.label,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        duration_s=duration_s,
        exit_code=130 if interrupted else (exit_code or 0),
        failed_tests=failed_tests,
        scenarios=scenarios,
        junit_path=str(junit_path),
        interrupted=interrupted,
        in_scope=in_scope,
        deselected=deselected,
    )
    reporter.print_batch_scenarios(result)
    return result


def run_batches(
    selected: list[BddBatch],
    *,
    features_path: Path,
    data_path: Path,
    run_dir: Path | None = None,
    verbose: bool = False,
) -> int:
    pytest_bin = _resolve_pytest()
    env = _default_env(features_path, data_path)
    reporter = Reporter()

    if run_dir is None:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        run_dir = SDK_ROOT / "artifacts" / "bdd" / stamp

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _sigint_handler)

    results: list[BatchResult] = []
    interrupted = False
    interrupted_label: str | None = None

    try:
        for index, batch in enumerate(selected, start=1):
            reporter.batch_start(index, len(selected), batch.label, batch.id)
            result = run_batch(
                batch,
                pytest_bin=pytest_bin,
                env=env,
                run_dir=run_dir,
                reporter=reporter,
                verbose=verbose,
            )
            reporter.batch_close(result)
            results.append(result)

            if result.interrupted:
                interrupted = True
                interrupted_label = batch.label
                break
    except KeyboardInterrupt:
        interrupted = True
        interrupted_label = interrupted_label or (
            selected[len(results)].label if len(results) < len(selected) else None
        )
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    pending = len(selected) - len(results) if interrupted else 0

    return reporter.write_summary(
        results,
        run_dir,
        interrupted=interrupted,
        pending_batches=pending,
        interrupted_label=interrupted_label,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run @sdk BDD scenarios in readable batches")
    parser.add_argument("--group", choices=[g.value for g in BddBatchGroup], help="Run one group")
    parser.add_argument("--batch", help="Run a single batch id")
    parser.add_argument("--list", action="store_true", help="List batch ids and exit")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Also show raw pytest lines (scenario lines always shown)",
    )
    parser.add_argument("--features-path", type=Path, default=None)
    parser.add_argument("--data-path", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.list:
        Reporter().print_batch_list(BDD_BATCHES)
        return 0

    group = BddBatchGroup(args.group) if args.group else None
    selected = batches_for(batch_id=args.batch, group=group)
    if not selected and not args.batch and not args.group:
        selected = batches_for()

    features_path = args.features_path
    if features_path is None:
        env_features = os.environ.get("PORTO_FEATURES_PATH")
        features_path = Path(env_features) if env_features else get_porto_features_root()

    data_path = args.data_path
    if data_path is None:
        env_data = os.environ.get("PORTO_DATA_PATH")
        data_path = Path(env_data) if env_data else Path(get_porto_data_path())

    try:
        return run_batches(
            selected,
            features_path=features_path,
            data_path=data_path,
            verbose=args.verbose,
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

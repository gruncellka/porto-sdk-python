"""Terminal reporter for BDD batch runs (Licko Ops–inspired layout)."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tests.bdd.runner.batches import BddBatch, BddBatchGroup

PREFIX = "bdd"
LINE_WIDTH = 88


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    name: str
    status: str  # passed | failed | skipped | error
    duration_s: float = 0.0
    message: str | None = None


@dataclass
class BatchResult:
    batch_id: str
    label: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_s: float = 0.0
    exit_code: int = 0
    failed_tests: list[str] = field(default_factory=list)
    scenarios: list[ScenarioResult] = field(default_factory=list)
    junit_path: str | None = None
    interrupted: bool = False
    in_scope: int = 0
    deselected: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors

    @property
    def ok(self) -> bool:
        return (
            not self.interrupted and self.exit_code == 0 and self.failed == 0 and self.errors == 0
        )


def humanize_scenario_name(raw: str) -> str:
    """Turn pytest-bdd test id into readable scenario label."""
    name = raw.removeprefix("test_")
    name = re.sub(r"^(deutschepost|ukrposhta|laposte|swisspost)_", "", name)
    words = name.replace("_", " ").split()
    label = " ".join(word.capitalize() for word in words)
    return label.replace(" Json ", " JSON ").replace(" Json", " JSON")


class Reporter:
    def __init__(self) -> None:
        self.use_color = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
        self._live_names: set[str] = set()

    def begin_batch(self) -> None:
        self._live_names = set()

    def _c(self, code: str, text: str) -> str:
        if not self.use_color:
            return text
        return f"\033[{code}m{text}\033[0m"

    def bold(self, text: str) -> str:
        return self._c("1", text)

    def green(self, text: str) -> str:
        return self._c("32", text)

    def red(self, text: str) -> str:
        return self._c("31", text)

    def yellow(self, text: str) -> str:
        return self._c("33", text)

    def cyan(self, text: str) -> str:
        return self._c("36", text)

    def dim(self, text: str) -> str:
        return self._c("2", text)

    def _tag(self) -> str:
        return self.cyan(f"[{PREFIX}]")

    def _body_width(self) -> int:
        return LINE_WIDTH - len(PREFIX) - 3  # [bdd] + space

    def _pad(self, count: int) -> str:
        return " " * max(count, 0)

    def _rule(self, width: int | None = None) -> str:
        return self.dim("─" * (width if width is not None else self._body_width()))

    def hr(self) -> None:
        print(f"{self._tag()} {self._rule()}")

    def header(self, title: str) -> None:
        print()
        self.hr()
        print(f"{self._tag()} {self.bold(title)}")
        self.hr()

    def meta(self, label: str, value: str) -> None:
        print(f"{self._tag()} {self.dim(f'{label}:')} {value}")

    def batch_start(self, index: int, total: int, label: str, batch_id: str) -> None:
        print()
        title = f"[{index}/{total}] {label}  ({batch_id})"
        fill = max(self._body_width() - len(title) - 4, 0)
        print(f"{self._tag()} {self.yellow('┌─')} {self.bold(title)} {self._rule(fill)}")

    def print_batch_list(self, batches: tuple[BddBatch, ...] | list[BddBatch]) -> None:
        """Readable catalog of @sdk BDD batches (`make sdk`)."""
        total = len(batches)
        id_width = max(len(batch.id) for batch in batches)

        self.header(f"BDD batches ({total})")
        self.meta("run sdk", "make sdk")
        self.meta("run adapters", "make adapters")
        print(f"{self._tag()} {self.dim('│')}")

        index = 0
        for group in BddBatchGroup:
            group_batches = [batch for batch in batches if batch.group == group]
            if not group_batches:
                continue

            print(
                f"{self._tag()} {self.cyan(group.value)} "
                f"{self.dim(f'({len(group_batches)} batch{"es" if len(group_batches) != 1 else ""})')}"
            )

            for batch in group_batches:
                index += 1
                print(
                    f"{self._tag()} {self.dim('│')}  "
                    f"{self.dim(f'{index:>2}.')}  "
                    f"{self.bold(batch.id.ljust(id_width))}  "
                    f"{batch.label}"
                )
                detail_parts: list[str] = []
                if batch.feature_glob:
                    detail_parts.append(batch.feature_glob)
                if batch.keyword_filter:
                    detail_parts.append(f"-k {batch.keyword_filter}")
                if detail_parts:
                    print(
                        f"{self._tag()} {self.dim('│')}      {self.dim(' · '.join(detail_parts))}"
                    )

            print(f"{self._tag()} {self.dim('│')}")

        self.hr()

    def _format_batch_summary_tail(self, result: BatchResult, outcome: str) -> str:
        ran = f"{result.total}/{result.in_scope}" if result.in_scope > 0 else str(result.total)
        failures = (
            self.green("0")
            if result.failed + result.errors == 0
            else self.red(str(result.failed + result.errors))
        )
        parts = [
            f"{self.dim('summary ran=')}{self.bold(ran)}",
        ]
        if result.deselected > 0:
            parts.append(f"{self.dim('deselected=')}{self.yellow(str(result.deselected))}")
        parts.extend(
            [
                f"{self.dim('failures=')}{failures}",
                f"{self.dim('status=')}{outcome}",
            ]
        )
        return "  ".join(parts)

    def batch_close(self, result: BatchResult) -> None:
        if result.interrupted:
            outcome = self.yellow("INTERRUPTED")
        elif result.ok:
            outcome = self.green("OK")
        else:
            outcome = self.red("FAIL")
        print(
            f"{self._tag()} {self.yellow('└─')} {self._format_batch_summary_tail(result, outcome)}"
        )

    def status_badge(self, status: str) -> str:
        if status == "passed":
            return self.green("[OK]")
        if status == "skipped":
            return self.yellow("[SKIP]")
        if status == "error":
            return self.red("[ERR]")
        return self.red("[FAIL]")

    def scenario_line(self, scenario: ScenarioResult) -> None:
        label = humanize_scenario_name(scenario.name)
        timing = self.dim(f" ({scenario.duration_s:.2f}s)") if scenario.duration_s > 0 else ""
        print(
            f"{self._tag()} {self.dim('│')}  {self.status_badge(scenario.status)}  {label}{timing}"
        )
        if scenario.message and scenario.status in {"failed", "error"}:
            for line in scenario.message.splitlines()[:4]:
                stripped = line.strip()
                if stripped:
                    print(f"{self._tag()} {self.dim('│')}     {self.dim(stripped)}")
        self._live_names.add(scenario.name)
        sys.stdout.flush()

    def print_batch_scenarios(self, result: BatchResult) -> None:
        for scenario in result.scenarios:
            if scenario.name in self._live_names:
                if scenario.message and scenario.status in {"failed", "error"}:
                    for line in scenario.message.splitlines()[:4]:
                        stripped = line.strip()
                        if stripped:
                            print(f"{self._tag()} {self.dim('│')}     {self.dim(stripped)}")
                continue
            self.scenario_line(scenario)

    def batch_progress(self, line: str) -> None:
        stripped = line.rstrip()
        if not stripped:
            return
        if (
            " FAILED " in stripped
            or stripped.startswith("FAILED ")
            or " ERROR " in stripped
            or stripped.startswith("ERROR ")
        ):
            print(f"{self._tag()} {self.dim('│')}  {self.red(stripped)}")
        elif "::test_" in stripped and any(
            token in stripped for token in ("PASSED", "FAILED", "ERROR", "SKIPPED")
        ):
            if "PASSED" in stripped:
                status = "passed"
            elif "SKIPPED" in stripped:
                status = "skipped"
            elif "ERROR" in stripped:
                status = "error"
            else:
                status = "failed"
            match = re.search(r"::(test_[^\s]+)", stripped)
            name = match.group(1) if match else stripped
            self.scenario_line(ScenarioResult(name=name, status=status))

    def _summary_batch_line(self, result: BatchResult, label_width: int) -> None:
        if result.interrupted:
            badge = self.yellow("[…]")
            outcome = self.yellow("INTERRUPTED")
        elif result.ok:
            badge = self.green("[OK]")
            outcome = self.green("OK")
        else:
            badge = self.red("[FAIL]")
            outcome = self.red("FAIL")

        if result.in_scope > 0:
            counts = f"{result.total}/{result.in_scope}"
        elif result.total:
            counts = str(result.total)
        else:
            counts = "—"
        deselected = (
            f"  {self.dim('deselected=')}{self.yellow(str(result.deselected))}"
            if result.deselected > 0
            else ""
        )
        print(
            f"{self._tag()} {self.dim('│')}  {badge}  "
            f"{result.label:<{label_width}}  "
            f"{self.dim('ran=')}{counts}{deselected}  "
            f"{self.dim('time=')}{result.duration_s:>5.1f}s  "
            f"{outcome}"
        )

    def write_summary(
        self,
        results: list[BatchResult],
        run_dir: Path,
        *,
        interrupted: bool = False,
        pending_batches: int = 0,
        interrupted_label: str | None = None,
    ) -> int:
        total_passed = sum(r.passed for r in results)
        total_failed = sum(r.failed for r in results)
        total_errors = sum(r.errors for r in results)
        total_skipped = sum(r.skipped for r in results)
        total_tests = sum(r.total for r in results)
        failed_batches = [r for r in results if not r.ok and not r.interrupted]
        passed_batches = sum(1 for r in results if r.ok)
        total_duration = sum(r.duration_s for r in results)

        print()
        self.hr()
        title = "total"
        fill = max(self._body_width() - len(title) - 4, 0)
        print(f"{self._tag()} {self.yellow('┌─')} {self.bold(title)} {self._rule(fill)}")
        print(
            f"{self._tag()} {self.dim('│')}   "
            f"{self.dim('summary batches=')}{self.bold(str(len(results)))}  "
            f"{self.dim('scenarios=')}{self.bold(str(total_tests))}  "
            f"{self.dim('passed=')}{self.green(str(total_passed)) if total_passed else self.bold('0')}  "
            f"{self.dim('failed=')}"
            + (self.green("0") if total_failed == 0 else self.red(str(total_failed)))
            + f"  {self.dim('errors=')}"
            + (self.green("0") if total_errors == 0 else self.red(str(total_errors)))
            + f"  {self.dim('time=')}{total_duration:.1f}s"
        )
        if pending_batches:
            print(
                f"{self._tag()} {self.dim('│')}   "
                f"{self.yellow(f'{pending_batches} batch(es) not started')}"
            )
        print(f"{self._tag()} {self.dim('│')}")

        label_width = max((len(r.label) for r in results), default=10)
        current_group: str | None = None
        for result in results:
            group = result.batch_id.split("-", 1)[0]
            if group != current_group:
                current_group = group
                print(f"{self._tag()} {self.dim('│')}  {self.cyan(group)}")
            self._summary_batch_line(result, label_width)

        print(f"{self._tag()} {self.yellow('└─')}")
        self.hr()

        if failed_batches:
            print()
            print(f"{self._tag()} {self.red(self.bold('Failed scenarios'))}")
            for batch in failed_batches:
                print(f"{self._tag()}   {self.red(batch.label)} {self.dim(f'({batch.batch_id})')}")
                for name in batch.failed_tests:
                    print(f"{self._tag()}     • {humanize_scenario_name(name)}")
                if not batch.failed_tests:
                    print(f"{self._tag()}     • see {batch.junit_path or 'pytest output'}")

        summary = {
            "passed_batches": passed_batches,
            "failed_batches": len(failed_batches),
            "interrupted": interrupted,
            "pending_batches": pending_batches,
            "interrupted_label": interrupted_label,
            "duration_s": total_duration,
            "tests": {
                "total": total_tests,
                "passed": total_passed,
                "failed": total_failed,
                "errors": total_errors,
                "skipped": total_skipped,
            },
            "batches": [asdict(r) for r in results],
        }
        run_dir.mkdir(parents=True, exist_ok=True)
        summary_path = run_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        latest = run_dir.parent / "latest"
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(run_dir.name, target_is_directory=True)

        print()
        if interrupted:
            where = interrupted_label or "current batch"
            print(
                f"{self._tag()} {self.bold('RESULT')}  "
                f"{self.yellow('INTERRUPTED')} {self.dim(f'during {where}')}"
            )
            print(f"{self._tag()} {self.dim(f'partial report → {summary_path}')}")
            return 130

        if failed_batches:
            print(
                f"{self._tag()} {self.bold('RESULT')}  "
                f"{self.red('FAILED')} {self.dim(f'{len(failed_batches)} batch(es), {total_failed + total_errors} scenario(s)')}"
            )
            print(f"{self._tag()} {self.dim(f'report → {summary_path}')}")
            return 1

        print(
            f"{self._tag()} {self.bold('RESULT')}  "
            f"{self.green('OK')} {self.dim(f'{passed_batches} batches, {total_passed} scenarios')}"
        )
        print(f"{self._tag()} {self.dim(f'report → {summary_path}')}")
        return 0

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TestFailure:
    test_name: str
    error_type: str = ""
    message: str = ""
    file_path: str = ""
    line_number: int = 0


@dataclass
class TestReport:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total: int = 0
    failures: list[TestFailure] = field(default_factory=list)
    summary: str = ""
    duration: float = 0.0


def parse_pytest_output(stdout: str, stderr: str = "") -> TestReport:
    text = stdout + "\n" + stderr
    report = TestReport()

    summary_match = re.search(r"=+\s*(.*?)\s*=+\s*$", text, re.MULTILINE)
    if summary_match:
        report.summary = summary_match.group(1)

    counts = re.findall(
        r"(\d+)\s+(passed|failed|error|skipped|warning)",
        report.summary,
    )
    for count_str, kind in counts:
        count = int(count_str)
        if kind == "passed":
            report.passed = count
        elif kind == "failed":
            report.failed = count
        elif kind == "error":
            report.errors = count
        elif kind == "skipped":
            report.skipped = count
    report.total = report.passed + report.failed + report.errors

    duration_match = re.search(r"in\s+([\d.]+)s", report.summary)
    if duration_match:
        report.duration = float(duration_match.group(1))

    failure_blocks = re.findall(
        r"FAILED\s+(\S+?)(?:\s+-\s+(.+))?$",
        text,
        re.MULTILINE,
    )
    for test_id, reason in failure_blocks:
        parts = test_id.rsplit("::", 1)
        fpath = parts[0] if len(parts) > 1 else ""
        name = parts[-1]
        report.failures.append(
            TestFailure(
                test_name=name,
                message=reason.strip() if reason else "",
                file_path=fpath,
            )
        )

    return report

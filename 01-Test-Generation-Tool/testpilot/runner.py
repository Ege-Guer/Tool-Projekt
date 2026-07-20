"""
Sandbox-Runner: fuehrt eine generierte pytest-Suite gegen den Code aus und misst
Line- und Branch-Coverage mit coverage.py.

Diese Komponente ist die "Fitness-Evaluation" der Suche (VL7): sie liefert die
numerischen Werte (Coverage, bestandene Tests, Laufzeit), die den agentischen
Loop und die Pareto-Optimierung leiten.

Hinweis (Verantwortung / Sicherheit, VL "Datenschutz & Verantwortung"):
Es wird von einem LLM generierter Code ausgefuehrt. Das geschieht bewusst in einem
temporaeren, isolierten Verzeichnis und mit Timeout. Fuer den produktiven Einsatz
sollte zusaetzlich ein Container-/Ressourcen-Sandbox verwendet werden.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from .models import CoverageReport, TestExecution

MODULE_NAME = "module_under_test"
TEST_NAME = "test_module_under_test"

_MAX_OUTPUT = 8000  # Zeichen, um die UI/den Report nicht zu fluten


def _truncate(text: str) -> str:
    if len(text) > _MAX_OUTPUT:
        return text[:_MAX_OUTPUT] + "\n... [gekuerzt]"
    return text


def _parse_junit(xml_path: str) -> tuple[TestExecution, bool]:
    """Liest die JUnit-XML von pytest. Rueckgabe: (execution, xml_vorhanden)."""
    execu = TestExecution()
    if not os.path.exists(xml_path):
        execu.collect_error = True
        return execu, False
    try:
        root = ET.parse(xml_path).getroot()
    except ET.ParseError:
        execu.collect_error = True
        return execu, False

    # root kann <testsuites> oder <testsuite> sein
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    for suite in suites:
        tests = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))
        execu.collected += tests
        execu.failed += failures
        execu.errors += errors
        execu.duration += float(suite.get("time", 0.0) or 0.0)
        execu.passed += max(0, tests - failures - errors - skipped)

        for case in suite.findall("testcase"):
            for tag in ("failure", "error"):
                el = case.find(tag)
                if el is not None:
                    msg = (el.get("message") or el.text or "").strip()
                    name = case.get("name", "?")
                    if msg:
                        execu.failure_messages.append(f"{name}: {msg.splitlines()[0][:200]}")
    return execu, True


def _parse_coverage(json_path: str) -> CoverageReport:
    """Liest die coverage.py-JSON und extrahiert Line- + Branch-Coverage."""
    report = CoverageReport()
    if not os.path.exists(json_path):
        return report
    try:
        data = json.load(open(json_path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return report

    # Datei des zu testenden Moduls heraussuchen
    target = None
    for path, info in data.get("files", {}).items():
        if os.path.basename(path).startswith(MODULE_NAME):
            target = info
            break
    if target is None:
        # Fallback: totals verwenden
        target = {"summary": data.get("totals", {}),
                  "missing_lines": [], "missing_branches": []}

    s = target.get("summary", {})
    report.covered_lines = s.get("covered_lines", 0)
    report.num_statements = s.get("num_statements", 0)
    report.num_branches = s.get("num_branches", 0)
    report.covered_branches = s.get("covered_branches", 0)
    report.missing_lines = target.get("missing_lines", []) or []
    report.missing_branches = target.get("missing_branches", []) or []

    if report.num_statements > 0:
        report.line_percent = round(100.0 * report.covered_lines / report.num_statements, 1)
    if report.num_branches > 0:
        report.branch_percent = round(100.0 * report.covered_branches / report.num_branches, 1)
    else:
        # Kein Branch im Code -> Branch-Coverage = Line-Coverage (nichts zu verzweigen)
        report.branch_percent = report.line_percent
    return report


def run_suite(source_code: str, test_code: str, timeout: int = 60,
              keep_dir: bool = False) -> tuple[TestExecution, CoverageReport, str]:
    """Fuehrt `test_code` gegen `source_code` aus.

    Returns: (TestExecution, CoverageReport, debug_dir)
    """
    workdir = tempfile.mkdtemp(prefix="testpilot_")
    module_path = os.path.join(workdir, f"{MODULE_NAME}.py")
    test_path = os.path.join(workdir, f"{TEST_NAME}.py")
    junit_path = os.path.join(workdir, "report.xml")
    covjson_path = os.path.join(workdir, "coverage.json")

    with open(module_path, "w", encoding="utf-8") as fh:
        fh.write(source_code)
    with open(test_path, "w", encoding="utf-8") as fh:
        fh.write(test_code)

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["COVERAGE_FILE"] = os.path.join(workdir, ".coverage")

    # 1) pytest unter coverage laufen lassen (mit Branch-Coverage!)
    run_cmd = [
        sys.executable, "-m", "coverage", "run",
        "--branch", f"--source={MODULE_NAME}",
        "-m", "pytest", f"{TEST_NAME}.py",
        f"--junitxml={os.path.basename(junit_path)}",
        "-q", "-p", "no:cacheprovider", "-o", "addopts=",
    ]
    start = time.time()
    wall = 0.0
    try:
        proc = subprocess.run(run_cmd, cwd=workdir, env=env, timeout=timeout,
                              capture_output=True, text=True)
        wall = time.time() - start
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        execu = TestExecution(collect_error=True, duration=float(timeout),
                              stderr="TIMEOUT: pytest ueberschritt das Zeitlimit.")
        if not keep_dir:
            shutil.rmtree(workdir, ignore_errors=True)
        return execu, CoverageReport(), ""

    # 2) coverage in JSON exportieren
    try:
        subprocess.run([sys.executable, "-m", "coverage", "json",
                        "-o", os.path.basename(covjson_path)],
                       cwd=workdir, env=env, timeout=30,
                       capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        pass

    execu, xml_found = _parse_junit(junit_path)
    execu.stdout = _truncate(stdout)
    execu.stderr = _truncate(stderr)
    # Laufzeit fuer Pareto-Objective: bevorzugt JUnit-Zeit, sonst Wall-Clock
    if execu.duration <= 0:
        execu.duration = round(wall, 3)

    # Kein XML => Collection/Import fehlgeschlagen (Suite "kompiliert" nicht)
    if not xml_found:
        execu.collect_error = True

    coverage = _parse_coverage(covjson_path)

    if not keep_dir:
        shutil.rmtree(workdir, ignore_errors=True)
        workdir = ""
    return execu, coverage, workdir


def quick_syntax_check(test_code: str) -> str | None:
    """Prueft, ob der Testcode ueberhaupt geparst werden kann (Kompilierungsrate).

    Spart einen teuren pytest-Lauf, wenn der generierte Code Syntaxfehler hat.
    """
    import ast as _ast
    try:
        _ast.parse(test_code)
        return None
    except SyntaxError as exc:
        return f"SyntaxError Zeile {exc.lineno}: {exc.msg}"

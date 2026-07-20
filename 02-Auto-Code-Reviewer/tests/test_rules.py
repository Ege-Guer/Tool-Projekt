"""Unit-Tests fuer den regelbasierten Analyzer und die JSON-Extraktion.

Ausfuehren:  pytest -q   (im Ordner 02-Auto-Code-Reviewer)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from codereviewer import analyze_source, rules            # noqa: E402
from codereviewer.llm import extract_json, extract_code   # noqa: E402


def _titles(source):
    struct = analyze_source(source, "t")
    return [f.title for f in rules.analyze(struct)], rules.analyze(struct)


def test_mutable_default_detected():
    _, findings = _titles("def f(x=[]):\n    x.append(1)\n    return x\n")
    assert any("Default" in f.title for f in findings)
    assert any(f.severity == "high" for f in findings)


def test_bare_except_detected():
    _, findings = _titles("def f():\n    try:\n        pass\n    except:\n        pass\n")
    cats = {f.title for f in findings}
    assert any("except" in t.lower() for t in cats)


def test_compare_none_detected():
    _, findings = _titles("def f(x):\n    return x == None\n")
    assert any("None" in f.title for f in findings)
    assert all(f.severity in {"low", "info"} for f in findings if "None" in f.title)


def test_eval_flagged_as_security_high():
    _, findings = _titles("def f(s):\n    return eval(s)\n")
    evals = [f for f in findings if "eval" in f.title.lower()]
    assert evals and evals[0].category == "security" and evals[0].severity == "high"


def test_hardcoded_secret_detected():
    _, findings = _titles('API_KEY = "sk-live-abc123"\n')
    assert any(f.category == "security" for f in findings)


def test_assert_tuple_detected():
    _, findings = _titles("def f(x):\n    assert (x > 0, 'msg')\n")
    assert any("assert" in f.title.lower() for f in findings)


def test_clean_code_has_no_high_findings():
    src = ('def add(a, b):\n    """Addiert zwei Zahlen."""\n    return a + b\n')
    _, findings = _titles(src)
    assert all(f.severity != "high" for f in findings)


def test_extract_json_from_fence():
    txt = 'Hier:\n```json\n[{"line": 1, "title": "x"}]\n```\nfertig'
    data = extract_json(txt)
    assert isinstance(data, list) and data[0]["line"] == 1


def test_extract_json_bare_array():
    assert extract_json('[{"a": 1}]') == [{"a": 1}]


def test_extract_code_from_fence():
    assert "def f" in extract_code("```python\ndef f():\n    pass\n```")

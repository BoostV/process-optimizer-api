"""Lint test: no stray print() in production code.

Tests in this repo configure their own logging; production code MUST
route everything through ``logging`` so operators can filter, level-
gate, and route messages in production. ``print`` calls bypass that.
"""

import ast
import pathlib

import pytest

OPTIMIZERAPI_ROOT = pathlib.Path(__file__).parent.parent / "optimizerapi"


def _all_python_files() -> list[pathlib.Path]:
    return [p for p in OPTIMIZERAPI_ROOT.rglob("*.py") if p.is_file()]


@pytest.mark.parametrize("path", _all_python_files(), ids=lambda p: str(p.relative_to(OPTIMIZERAPI_ROOT.parent)))
def test_no_print_calls(path):
    """No `print()` call is allowed under optimizerapi/."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    assert not offenders, (
        f"{path}: found print() calls at line(s) {offenders}. "
        "Use logging.getLogger(__name__) instead."
    )

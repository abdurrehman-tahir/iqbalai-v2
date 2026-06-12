"""Unit tests for the FastAPI route contract checker (T-225).

Loads `scripts/check_response_model.py` by path (it lives at the repo root, not
under the importable `app` package) and exercises it against synthetic router
files written to a tmp dir.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_CHECKER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_response_model.py"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_response_model", _CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_COMPLIANT = """
from fastapi import APIRouter
router = APIRouter()

@router.get("/", response_model=dict, operation_id="list_things")
async def list_things() -> dict:
    return {}
"""

_MISSING_RESPONSE_MODEL = """
from fastapi import APIRouter
router = APIRouter()

@router.get("/", operation_id="list_things")
async def list_things() -> dict:
    return {}
"""

_MISSING_OPERATION_ID = """
from fastapi import APIRouter
router = APIRouter()

@router.post("/", response_model=dict)
async def make_thing() -> dict:
    return {}
"""


def test_compliant_route_has_no_violations(tmp_path: Path) -> None:
    f = tmp_path / "router.py"
    f.write_text(_COMPLIANT)
    checker = _load_checker()
    assert checker.check_file(f) == []


def test_missing_response_model_is_flagged(tmp_path: Path) -> None:
    f = tmp_path / "router.py"
    f.write_text(_MISSING_RESPONSE_MODEL)
    checker = _load_checker()
    violations = checker.check_file(f)
    assert len(violations) == 1
    assert "response_model" in violations[0]


def test_missing_operation_id_is_flagged(tmp_path: Path) -> None:
    f = tmp_path / "router.py"
    f.write_text(_MISSING_OPERATION_ID)
    checker = _load_checker()
    violations = checker.check_file(f)
    assert len(violations) == 1
    assert "operation_id" in violations[0]


def test_non_route_decorators_are_ignored(tmp_path: Path) -> None:
    """A bare async function with no route decorator must not be flagged."""
    f = tmp_path / "service.py"
    f.write_text("async def fetch() -> dict:\n    return {}\n")
    checker = _load_checker()
    assert checker.check_file(f) == []


def test_live_routes_all_compliant() -> None:
    """The real app routers must pass the gate (regression guard for T-225)."""
    checker = _load_checker()
    app_root = Path(__file__).resolve().parents[1] / "app"
    violations: list[str] = []
    for p in app_root.rglob("router.py"):
        violations.extend(checker.check_file(p))
    assert violations == [], "\n".join(violations)

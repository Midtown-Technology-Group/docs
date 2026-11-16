"""Unit tests for version_policy.py (run: python -m pytest -q .github/scripts)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from packaging.version import Version

sys.path.insert(0, str(Path(__file__).resolve().parent))

import version_policy as vp  # noqa: E402


def descriptor(version: str) -> str:
    return f"slug: bifrost-docs\nname: Bifrost Docs\nversion: {version}\n"


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "SECURITY.md",
        "docs/CUTOVER_RUNBOOK.md",
        "docs/DESIGN_SYSTEM_PROVENANCE.json",
        "tests/test_folders.py",
        ".github/workflows/ci.yml",
        ".github/scripts/version_policy.py",
        "apps/bifrost-docs/README.md",
        "apps/bifrost-docs/src/app.test.tsx",
        "apps/bifrost-docs/src/lib/deep/thing.test.ts",
        "apps/bifrost-docs/scripts/browser-qa.cjs",
    ],
)
def test_non_deployable_paths(path: str) -> None:
    assert not vp.is_deployable(path)


@pytest.mark.parametrize(
    "path",
    [
        "bifrost.solution.yaml",
        "requirements.txt",
        ".bifrost/tables.yaml",
        "functions/docs_search.py",
        "modules/indexing.py",
        "apps/bifrost-docs/package.json",
        "apps/bifrost-docs/package-lock.json",
        "apps/bifrost-docs/src/app.tsx",
        "apps/bifrost-docs/src/test-utils.ts",
        "apps/bifrost-docs/vite.config.ts",
        "tests.py",
        "docsite/index.html",
        "LICENSE",
    ],
)
def test_deployable_paths(path: str) -> None:
    assert vp.is_deployable(path)


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("0.1.3", "0.1.3+mtg.1"),
        ("0.1.3+mtg.1", "0.1.3+mtg.2"),
        ("0.1.3+mtg.9", "0.1.3+mtg.10"),
        ("0.1.4", "0.1.4+mtg.1"),
    ],
)
def test_suggest_next(base: str, expected: str) -> None:
    suggestion = vp.suggest_next(Version(base))
    assert suggestion == expected
    assert Version(suggestion) > Version(base)


def test_pep440_ordering_matches_release_flow() -> None:
    assert Version("0.1.3") < Version("0.1.3+mtg.1") < Version("0.1.3+mtg.2") < Version("0.1.4")


def test_non_deployable_change_needs_no_bump() -> None:
    ok, message = vp.evaluate(
        ["README.md", ".github/workflows/ci.yml", "tests/test_x.py"],
        descriptor("0.1.3"),
        descriptor("0.1.3"),
    )
    assert ok, message


def test_deployable_change_without_bump_fails_with_suggestion() -> None:
    ok, message = vp.evaluate(
        ["functions/docs_search.py", "README.md"],
        descriptor("0.1.3+mtg.1"),
        descriptor("0.1.3+mtg.1"),
    )
    assert not ok
    assert "0.1.3+mtg.2" in message
    assert "functions/docs_search.py" in message
    assert "README.md" not in message


def test_deployable_change_with_downgrade_fails() -> None:
    ok, _ = vp.evaluate(["modules/x.py"], descriptor("0.1.3+mtg.2"), descriptor("0.1.3+mtg.1"))
    assert not ok


@pytest.mark.parametrize("head", ["0.1.3+mtg.1", "0.1.4", "0.2.0"])
def test_deployable_change_with_bump_passes(head: str) -> None:
    ok, message = vp.evaluate(["modules/x.py"], descriptor("0.1.3"), descriptor(head))
    assert ok, message


def test_invalid_head_version_fails() -> None:
    ok, message = vp.evaluate(["modules/x.py"], descriptor("0.1.3"), descriptor("next"))
    assert not ok
    assert "PEP 440" in message
    assert "0.1.3+mtg.1" in message


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "mtg")
    _git(tmp_path, "config", "user.email", "ci@example.invalid")
    _git(tmp_path, "config", "user.name", "CI")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "bifrost.solution.yaml").write_text(descriptor("0.1.3"))
    (tmp_path / "modules").mkdir()
    (tmp_path / "modules/x.py").write_text("x = 1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "feature")
    return tmp_path


def _commit(repo: Path, path: str, text: str) -> str:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text)
    _git(repo, "add", path)
    _git(repo, "commit", "-q", "-m", f"change {path}")
    return _git(repo, "rev-parse", "HEAD")


def _run(repo: Path, monkeypatch: pytest.MonkeyPatch, base: str, head: str) -> int:
    monkeypatch.chdir(repo)
    return vp.main(["--base", base, "--head", head])


def test_main_end_to_end(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = _git(repo, "rev-parse", "mtg")
    head = _commit(repo, "docs/NOTES.md", "notes\n")
    assert _run(repo, monkeypatch, base, head) == 0

    head = _commit(repo, "modules/x.py", "x = 2\n")
    assert _run(repo, monkeypatch, base, head) == 1

    head = _commit(repo, "bifrost.solution.yaml", descriptor("0.1.3+mtg.1"))
    assert _run(repo, monkeypatch, base, head) == 0


def test_main_ignores_changes_that_landed_on_base(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    head = _commit(repo, "tests/test_y.py", "def test_y(): pass\n")
    _git(repo, "checkout", "-q", "mtg")
    base = _commit(repo, "modules/x.py", "x = 3\n")
    _git(repo, "checkout", "-q", "feature")
    # The base moved on with a deployable change; the PR itself only touches tests.
    assert _run(repo, monkeypatch, base, head) == 0

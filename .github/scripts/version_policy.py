#!/usr/bin/env python3
"""Require a Solution version bump for deployable changes merged into ``mtg``.

Bifrost polls ``version:`` in ``bifrost.solution.yaml`` on the followed branch
and only offers an update when it increases (compared with ``packaging``). A
deployable change merged without a bump would never reach installs.

Usage (from a full-history checkout)::

    python .github/scripts/version_policy.py --base <base-sha> --head <head-sha>

Exit codes: 0 = policy satisfied, 1 = version bump missing or invalid.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence

import yaml
from packaging.version import InvalidVersion, Version

DESCRIPTOR = "bifrost.solution.yaml"
LOCAL_LABEL = "mtg"

# Paths that never change what an install runs. Everything else is deployable.
NON_DEPLOYABLE_PATTERNS: tuple[str, ...] = (
    "docs/**",
    "**/*.md",
    "tests/**",
    ".github/**",
    "apps/*/src/**/*.test.*",
    "apps/*/scripts/**",
)


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a path glob: ``*`` stays within a segment, ``**/`` spans any depth."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


_NON_DEPLOYABLE = tuple(_glob_to_regex(p) for p in NON_DEPLOYABLE_PATTERNS)


def is_deployable(path: str) -> bool:
    return not any(rx.match(path) for rx in _NON_DEPLOYABLE)


def deployable_paths(paths: Iterable[str]) -> list[str]:
    return sorted({p for p in paths if p and is_deployable(p)})


def parse_descriptor_version(text: str | None) -> Version | None:
    """Return the descriptor's version, or None when the file is absent."""
    if text is None:
        return None
    data = yaml.safe_load(text) or {}
    raw = data.get("version")
    if raw is None:
        raise ValueError(f"{DESCRIPTOR} has no `version:` field")
    try:
        return Version(str(raw))
    except InvalidVersion as exc:
        raise ValueError(f"{DESCRIPTOR} version {raw!r} is not a valid PEP 440 version") from exc


def suggest_next(base: Version | None, label: str = LOCAL_LABEL) -> str:
    """Next ``<public>+<label>.N`` version after ``base``."""
    if base is None:
        return f"0.1.0+{label}.1"
    match = re.fullmatch(rf"{re.escape(label)}\.(\d+)", base.local or "")
    n = int(match.group(1)) + 1 if match else 1
    return f"{base.public}+{label}.{n}"


def evaluate(
    changed: Iterable[str], base_text: str | None, head_text: str | None
) -> tuple[bool, str]:
    """Return (ok, message) for a PR's changed paths and descriptor contents."""
    deployable = deployable_paths(changed)
    if not deployable:
        return True, "No deployable paths changed; no version bump required."

    listing = "\n".join(f"  - {p}" for p in deployable)
    try:
        base = parse_descriptor_version(base_text)
    except ValueError as exc:
        base = None
        print(f"warning: ignoring unreadable base descriptor: {exc}", file=sys.stderr)
    suggestion = suggest_next(base)
    try:
        head = parse_descriptor_version(head_text)
    except ValueError as exc:
        return False, f"{exc}.\nSuggested version: {suggestion}\nDeployable changes:\n{listing}"
    if head is None:
        return False, f"{DESCRIPTOR} is missing on the head branch.\nDeployable changes:\n{listing}"

    if base is None or head > base:
        return True, f"Version bumped: {base} -> {head}. Deployable changes:\n{listing}"
    return False, (
        f"This PR changes deployable paths but {DESCRIPTOR} version is {head}, which is "
        f"not greater than the base version {base}.\n"
        f"Bump `version:` in {DESCRIPTOR} to {suggestion} "
        f"(or a newer upstream release) so Bifrost installs following this branch see the update.\n"
        f"Deployable changes:\n{listing}"
    )


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _show(rev: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{rev}:{path}"], capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="PR base commit (the target branch tip)")
    parser.add_argument("--head", required=True, help="PR head commit")
    args = parser.parse_args(argv)

    # Three-dot diff: only what the PR introduces since it forked from the base.
    changed = _git("diff", "--name-only", "--no-renames", f"{args.base}...{args.head}").splitlines()
    ok, message = evaluate(changed, _show(args.base, DESCRIPTOR), _show(args.head, DESCRIPTOR))
    if ok:
        print(message)
        return 0
    print(f"::error file={DESCRIPTOR},title=Version bump required::{message.splitlines()[0]}")
    print(message)
    return 1


if __name__ == "__main__":
    sys.exit(main())

"""Distribution-level guards for the shareable Bifrost Docs Solution."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from packaging.version import InvalidVersion, Version


ROOT = Path(__file__).resolve().parents[1]


def test_solution_distribution_has_no_instance_sdk_or_private_delivery_artifacts() -> None:
    """A public Solution must bind its SDK and deployment evidence at install time."""
    descriptor = yaml.safe_load((ROOT / "bifrost.solution.yaml").read_text())
    package = json.loads((ROOT / "apps/bifrost-docs/package.json").read_text())
    lockfile = (ROOT / "apps/bifrost-docs/package-lock.json").read_text()
    lockfile_data = json.loads(lockfile)
    bootstrap = (ROOT / "apps/bifrost-docs/src/main.tsx").read_text()
    vite_config = (ROOT / "apps/bifrost-docs/vite.config.ts").read_text()
    readme = (ROOT / "README.md").read_text()

    # Forks and downstream installs may carry PEP 440 local labels such as
    # ``0.1.3+site.1``; the platform compares versions with ``packaging``.
    version = str(descriptor["version"])
    try:
        Version(version)
    except InvalidVersion as exc:
        raise AssertionError(f"descriptor version {version!r} is not PEP 440") from exc
    assert descriptor["allow_outbound_access"] is False

    # The instance SDK is installed at build time and never recorded in the
    # distributed manifests.
    lock_root = lockfile_data["packages"][""]
    for manifest in (package, lock_root):
        for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            assert "bifrost" not in manifest.get(section, {})
    assert '"node_modules/bifrost"' not in lockfile
    assert "/api/sdk/download" not in json.dumps(package)
    assert "/api/sdk/download" not in lockfile

    # Vitest is a locked dev dependency; any version range is acceptable as
    # long as package.json and the lockfile agree.
    vitest_spec = package["devDependencies"].get("vitest")
    assert isinstance(vitest_spec, str) and vitest_spec
    assert "vitest" not in package.get("dependencies", {})
    assert lock_root["devDependencies"].get("vitest") == vitest_spec
    assert lockfile_data["packages"]["node_modules/vitest"]["dev"] is True
    assert "VITE_BIFROST_SOLUTION_ID" in vite_config
    assert "solutionId: import.meta.env.VITE_BIFROST_SOLUTION_ID" in bootstrap
    assert "window.location.origin" not in bootstrap
    assert '"auth", "token"' not in vite_config
    assert "https://github.com/gobifrost/docs" in readme
    assert "Bifrost #791" in readme
    assert "optional IT Glue migration" in readme
    assert "Optional AI profile" in readme

    assert not (ROOT / ".impeccable").exists()
    assert not (ROOT / "docs/browser-evidence").exists()
    for retired in (
        "DELIVERY_EVIDENCE.md",
        "OPENCODE_HANDOFF.md",
        "PLATFORM_POLICY_PR_HANDOFF.md",
        "APP_PARITY_REVIEW.md",
        "FEATURE_PARITY_MATRIX.md",
        "UI_MIGRATION_MATRIX.md",
        "UI_VISUAL_REVIEW_20261003.md",
        "2026-08-13-cutover-impact-audit.md",
        "input-trust-remediation-2026-10-06.md",
    ):
        assert not (ROOT / "docs" / retired).exists()

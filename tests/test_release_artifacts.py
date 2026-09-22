from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_composite_action_invokes_github_triage_and_writes_a_summary() -> None:
    manifest = yaml.load(
        (ROOT / "action.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

    assert manifest["runs"]["using"] == "composite"
    script = "\n".join(step.get("run", "") for step in manifest["runs"]["steps"])
    assert "windjev triage" in script
    assert "--issue-number" in script
    assert "GITHUB_STEP_SUMMARY" in script


def test_project_is_licensed_under_apache_2() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert 'license = "Apache-2.0"' in pyproject
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text


def test_readme_defaults_to_chinese_and_links_both_languages() -> None:
    chinese = (ROOT / "README.md").read_text(encoding="utf-8")
    english = (ROOT / "README_EN.md").read_text(encoding="utf-8")

    assert "简体中文 | [English](README_EN.md)" in chinese
    assert "[简体中文](README.md) | English" in english


def test_ci_and_protected_release_workflows_are_present() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    for version in ("3.11", "3.12", "3.13", "3.14"):
        assert version in ci
    assert "uv run pytest" in ci
    assert "environment: pypi" in release
    assert "pypa/gh-action-pypi-publish" in release

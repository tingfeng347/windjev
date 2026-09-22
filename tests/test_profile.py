import pytest
from pydantic import ValidationError

from windjev import TriageProfile, load_profile


def test_apply_mode_rejects_a_moving_model_alias() -> None:
    with pytest.raises(ValidationError, match="immutable model version"):
        TriageProfile.model_validate(
            {
                "version": 1,
                "mode": "apply",
                "model": "jev-latest",
                "areas": {"api": "Public API"},
                "routes": {"backend": "Backend maintainers"},
                "labels": {
                    "type": {"bug": "type: bug"},
                    "area": {"api": "area: api"},
                    "priority": {"high": "priority: high"},
                    "route": {"backend": "route: backend"},
                    "review": "needs-human-review",
                },
            }
        )


def test_load_profile_reads_versioned_yaml(tmp_path) -> None:
    path = tmp_path / ".windjev.yml"
    path.write_text(
        """
version: 1
mode: observe
model: jev-latest
areas:
  api: Public API
routes:
  backend: Backend maintainers
labels:
  type:
    bug: "type: bug"
  area:
    api: "area: api"
  priority:
    high: "priority: high"
  route:
    backend: "route: backend"
  review: needs-human-review
""".lstrip(),
        encoding="utf-8",
    )

    profile = load_profile(path)

    assert profile.mode == "observe"
    assert profile.confidence.priority == 0.75


def test_profile_rejects_duplicate_managed_labels() -> None:
    with pytest.raises(ValidationError, match="Managed Labels must be unique"):
        TriageProfile.model_validate(
            {
                "version": 1,
                "mode": "observe",
                "model": "jev-latest",
                "areas": {"api": "Public API"},
                "routes": {"backend": "Backend maintainers"},
                "labels": {
                    "type": {"bug": "triage"},
                    "area": {"api": "triage"},
                    "priority": {"high": "priority: high"},
                    "route": {"backend": "route: backend"},
                    "review": "needs-human-review",
                },
            }
        )

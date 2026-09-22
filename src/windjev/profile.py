from pathlib import Path

import yaml

from .issue_triage import TriageProfile


def load_profile(path: str | Path) -> TriageProfile:
    with Path(path).open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    return TriageProfile.model_validate(data)

from typing import Any, Self

import pytest
from typesafe_sdk import (
    Choice,
    ChoiceAnswer,
    Noul,
    NoulAnswer,
    Score,
    ScoreAnswer,
    SystemOneResponse,
    Usage,
)

from windjev import ChoiceQuestion, NoulQuestion, ScoreQuestion, TypeSafeJevProvider


class FakeTypeSafeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def system_one(
        self, *, state: Any, questions: Any, model: str
    ) -> SystemOneResponse:
        self.calls.append({"state": state, "questions": questions, "model": model})
        return SystemOneResponse(
            model="jev-1.13.0",
            usage=Usage(input_tokens=120, output_tokens=4),
            answers={
                "type": ChoiceAnswer(
                    choice="bug",
                    confidence=0.96,
                    probabilities={"bug": 0.96, "feature": 0.04},
                ),
                "priority": ScoreAnswer(
                    score=2.1,
                    confidence=0.84,
                    legend={0: "low", 1: "medium", 2: "high", 3: "critical"},
                    probabilities={0: 0.01, 1: 0.10, 2: 0.84, 3: 0.05},
                ),
                "reply": NoulAnswer(noul=0.9),
            },
        )


@pytest.mark.asyncio
async def test_typesafe_provider_normalizes_one_parallel_request() -> None:
    client = FakeTypeSafeClient()
    provider = TypeSafeJevProvider(client_factory=lambda **kwargs: client)

    response = await provider.decide(
        state={"issue": {"title": "Broken endpoint"}},
        questions={
            "type": ChoiceQuestion(
                instructions="What kind?",
                criteria={"bug": "Broken", "feature": "New"},
            ),
            "priority": ScoreQuestion(
                instructions="How urgent?",
                levels={
                    "low": "Can wait",
                    "medium": "Normal",
                    "high": "Prompt",
                    "critical": "Immediate",
                },
            ),
            "reply": NoulQuestion(
                instructions="Should someone reply?",
                criteria="A response is needed to move the issue forward.",
            ),
        },
        model="jev-latest",
    )

    assert len(client.calls) == 1
    assert isinstance(client.calls[0]["questions"]["type"], Choice)
    assert isinstance(client.calls[0]["questions"]["priority"], Score)
    assert isinstance(client.calls[0]["questions"]["reply"], Noul)
    assert client.calls[0]["questions"]["reply"].criteria == {
        "true": "A response is needed to move the issue forward."
    }
    assert response.model == "jev-1.13.0"
    assert response.usage == {"input_tokens": 120, "output_tokens": 4}
    assert response.judgments["type"].value == "bug"
    assert response.judgments["priority"].model_dump() == {
        "value": "high",
        "confidence": 0.84,
        "probabilities": {
            "low": 0.01,
            "medium": 0.10,
            "high": 0.84,
            "critical": 0.05,
        },
    }
    assert response.judgments["reply"].model_dump() == {
        "value": True,
        "confidence": 0.8,
        "probabilities": {"no": pytest.approx(0.1), "yes": 0.9},
    }

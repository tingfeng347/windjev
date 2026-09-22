from __future__ import annotations

from collections.abc import Callable, Mapping
from time import perf_counter
from typing import Any

from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    ChoiceAnswer,
    Noul,
    NoulAnswer,
    RetryPolicy,
    Score,
    ScoreAnswer,
    TypeSafeError,
)

from .decision import (
    ChoiceQuestion,
    DecisionResponse,
    Judgment,
    Question,
    ScoreQuestion,
)
from .errors import ProviderError


class TypeSafeJevProvider:
    def __init__(
        self,
        *,
        client_factory: Callable[..., Any] = AsyncTypeSafeClient,
        attempt_timeout: float = 10.0,
        overall_timeout: float = 30.0,
    ) -> None:
        self._client_factory = client_factory
        self._attempt_timeout = attempt_timeout
        self._retry = RetryPolicy(max_retries=2, timeout=overall_timeout)

    async def decide(
        self,
        *,
        state: Mapping[str, Any],
        questions: Mapping[str, Question],
        model: str,
    ) -> DecisionResponse:
        sdk_questions = {
            name: self._to_sdk_question(question)
            for name, question in questions.items()
        }
        started = perf_counter()
        try:
            async with self._client_factory(
                timeout=self._attempt_timeout,
                retry=self._retry,
            ) as client:
                response = await client.system_one(
                    state=dict(state),
                    questions=sdk_questions,
                    model=model,
                )
        except TypeSafeError as error:
            raise ProviderError(str(error)) from error

        try:
            judgments = {
                name: self._to_judgment(answer, questions[name])
                for name, answer in response.answers.items()
            }
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError(
                "TypeSafe returned an invalid decision response"
            ) from error
        return DecisionResponse(
            judgments=judgments,
            provider="typesafe",
            model=response.model,
            usage=response.usage.model_dump(exclude_none=True),
            timing={"elapsed_ms": round((perf_counter() - started) * 1000, 3)},
        )

    @staticmethod
    def _to_sdk_question(question: Question) -> Choice | Score | Noul:
        if isinstance(question, ChoiceQuestion):
            return Choice(
                instructions=question.instructions,
                criteria=question.criteria,
            )
        if isinstance(question, ScoreQuestion):
            return Score(
                instructions=question.instructions,
                criteria=list(question.levels.values()),
            )
        return Noul(
            instructions=question.instructions,
            criteria={"true": question.criteria},
        )

    @staticmethod
    def _to_judgment(answer: Any, question: Question) -> Judgment:
        if isinstance(answer, ChoiceAnswer):
            return Judgment(
                value=answer.choice,
                confidence=answer.confidence,
                probabilities=answer.probabilities,
            )
        if isinstance(answer, ScoreAnswer) and isinstance(question, ScoreQuestion):
            levels = list(question.levels)
            selected_index = min(max(round(answer.score), 0), len(levels) - 1)
            return Judgment(
                value=levels[selected_index],
                confidence=answer.confidence,
                probabilities={
                    levels[index]: probability
                    for index, probability in answer.probabilities.items()
                    if 0 <= index < len(levels)
                },
            )
        if isinstance(answer, NoulAnswer):
            return Judgment(
                value=answer.noul >= 0.5,
                confidence=abs(answer.noul - 0.5) * 2,
                probabilities={"no": 1 - answer.noul, "yes": answer.noul},
            )
        raise ValueError("TypeSafe returned an answer that does not match its question")

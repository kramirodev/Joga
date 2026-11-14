"""Triagem determinística de denúncias (Fase 17A)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

CATEGORY_WEIGHTS: dict[str, int] = {
    "THREAT": 70,
    "SEXUAL": 65,
    "HATE": 60,
    "HARASSMENT": 50,
    "OTHER": 30,
    "SPAM": 15,
}
CLASSIFIER_VERSION = "rules_v1"


@dataclass(frozen=True)
class ModerationClassification:
    priority: int
    severity: str
    signals: dict[str, int | str]


class ModerationClassifier(Protocol):
    """Contrato substituível; não aplica medidas."""

    def classify(
        self,
        *,
        category: str,
        prior_reports: int,
        context_messages: int,
        description_length: int,
    ) -> ModerationClassification: ...


class RuleBasedModerationClassifier:
    """Prioriza por categoria, reincidência e contexto, sem custo externo."""

    def classify(
        self,
        *,
        category: str,
        prior_reports: int,
        context_messages: int,
        description_length: int,
    ) -> ModerationClassification:
        category_weight = CATEGORY_WEIGHTS.get(category, CATEGORY_WEIGHTS["OTHER"])
        recurrence = min(15, max(0, prior_reports) * 5)
        context = min(10, max(0, context_messages) * 2)
        length = 5 if description_length >= 200 else 0
        priority = min(100, category_weight + recurrence + context + length)
        severity = "HIGH" if priority >= 70 else "MEDIUM" if priority >= 40 else "LOW"
        return ModerationClassification(
            priority=priority,
            severity=severity,
            signals={
                "category_weight": category_weight,
                "prior_reports": prior_reports,
                "context_messages": context_messages,
                "description_length_bucket": length,
                "classifier_version": CLASSIFIER_VERSION,
            },
        )


DEFAULT_CLASSIFIER: ModerationClassifier = RuleBasedModerationClassifier()

__all__ = [
    "CATEGORY_WEIGHTS",
    "CLASSIFIER_VERSION",
    "DEFAULT_CLASSIFIER",
    "ModerationClassification",
    "ModerationClassifier",
    "RuleBasedModerationClassifier",
]

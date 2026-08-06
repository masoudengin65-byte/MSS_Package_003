"""Explainable shadow-score value object (Sprint 82)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ShadowScore:
    score: int
    confidence: float
    components: dict[str, int | str] = field(default_factory=dict)
    available_components: int = 0
    positive_components: int = 0
    negative_components: int = 0
    mode: str = "SHADOW_ONLY"


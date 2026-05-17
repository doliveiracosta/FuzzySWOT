"""Typed data structures for Fuzzy SWOT projects."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .constants import HIERARCHY_WEIGHTS


@dataclass(slots=True)
class Project:
    name: str = "Analise SWOT Fuzzy"
    organization: str = ""
    responsible: str = ""
    judgment_mode: str = "Individual por avaliador"
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class Evaluator:
    name: str
    area: str = ""
    hierarchical_function: str = "Outros"
    role_detail: str = ""
    weight: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("O avaliador precisa ter nome.")
        # The evaluator weight is always derived from the hierarchy table.
        self.weight = float(HIERARCHY_WEIGHTS.get(self.hierarchical_function, HIERARCHY_WEIGHTS["Outros"]))

    @property
    def key(self) -> str:
        return f"{self.name} | {self.hierarchical_function} | {self.area}"

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)

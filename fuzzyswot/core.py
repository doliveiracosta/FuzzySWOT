"""Business logic for Fuzzy SWOT prioritization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .constants import FUZZY_COLOR_SCALE, FUZZY_SCALE, TOWS_MATRIX_NAME


@dataclass(slots=True)
class ConsolidationResult:
    consolidated: pd.DataFrame
    consensus: dict[str, pd.DataFrame]
    ranking: pd.DataFrame
    used_weights: pd.DataFrame
    tows_strategies: pd.DataFrame
    strategic_profile: pd.DataFrame
    statistical_confidence: pd.DataFrame


def _rounded_scale_value(value: float) -> float:
    return round(float(np.clip(value, 0.0, 1.0)), 1)


def fuzzy_label(value: float) -> str:
    """Return the linguistic label closest to a fuzzy value."""

    return FUZZY_SCALE[_rounded_scale_value(value)]


def fuzzy_color(value: float) -> str:
    """Return the UI color for a fuzzy value."""

    return FUZZY_COLOR_SCALE[_rounded_scale_value(value)]


def normalize_items(items: Sequence[str]) -> list[str]:
    """Strip empty SWOT item labels while preserving user order."""

    return [str(item).strip() for item in items if str(item).strip()]


def matrix_definitions(
    strengths: Sequence[str],
    weaknesses: Sequence[str],
    opportunities: Sequence[str],
    threats: Sequence[str],
) -> dict[str, tuple[list[str], list[str], str]]:
    """Return available matrix definitions for a SWOT project."""

    organization = normalize_items([*strengths, *weaknesses])
    environment = normalize_items([*opportunities, *threats])
    if not organization or not environment:
        return {}

    return {
        TOWS_MATRIX_NAME: (
            organization,
            environment,
            "Relacione fatores internos com fatores externos. SO = ofensiva, ST = defensiva, "
            "WO = melhoria, WT = sobrevivencia.",
        )
    }


def default_matrix(rows: Sequence[str], columns: Sequence[str], value: float = 0.5) -> pd.DataFrame:
    """Create a default fuzzy judgment matrix."""

    rounded = _rounded_scale_value(value)
    return pd.DataFrame(rounded, index=normalize_items(rows), columns=normalize_items(columns))


def validate_fuzzy_matrix(matrix: pd.DataFrame) -> pd.DataFrame:
    """Return a numeric matrix and fail early when values are outside the fuzzy range."""

    if matrix.empty:
        raise ValueError("A matriz nao pode estar vazia.")
    numeric = matrix.astype(float)
    if numeric.isna().any().any():
        raise ValueError("A matriz contem valores vazios ou invalidos.")
    if ((numeric < 0.0) | (numeric > 1.0)).any().any():
        raise ValueError("Todos os julgamentos fuzzy devem estar entre 0 e 1.")
    return numeric


def _validate_compatible_matrices(matrices: Sequence[pd.DataFrame]) -> list[pd.DataFrame]:
    if not matrices:
        raise ValueError("Informe pelo menos uma matriz.")

    numeric = [validate_fuzzy_matrix(matrix) for matrix in matrices]
    first = numeric[0]
    for matrix in numeric[1:]:
        if matrix.shape != first.shape:
            raise ValueError("Todas as matrizes precisam ter a mesma dimensao.")
        if list(matrix.index) != list(first.index) or list(matrix.columns) != list(first.columns):
            raise ValueError("Todas as matrizes precisam ter as mesmas linhas e colunas.")
    return numeric


def weighted_average_matrices(matrices: Sequence[pd.DataFrame], weights: Sequence[float]) -> pd.DataFrame:
    """Consolidate evaluator matrices with a weighted average."""

    numeric = _validate_compatible_matrices(matrices)
    if len(numeric) != len(weights):
        raise ValueError("A quantidade de pesos precisa bater com a quantidade de matrizes.")

    numeric_weights = np.asarray(weights, dtype=float)
    if np.isnan(numeric_weights).any():
        raise ValueError("Os pesos nao podem conter valores vazios.")
    if (numeric_weights < 0).any():
        raise ValueError("Os pesos nao podem ser negativos.")

    total_weight = numeric_weights.sum()
    if total_weight <= 0:
        raise ValueError("A soma dos pesos deve ser maior que zero.")

    stack = np.stack([matrix.values for matrix in numeric], axis=0)
    consolidated = np.average(stack, axis=0, weights=numeric_weights)
    return pd.DataFrame(consolidated, index=numeric[0].index, columns=numeric[0].columns)


def consensus_indicators(matrices: Sequence[pd.DataFrame], divergence_threshold: float = 0.25) -> dict[str, pd.DataFrame]:
    """Calculate mean, standard deviation, amplitude and divergence alerts."""

    numeric = _validate_compatible_matrices(matrices)
    if divergence_threshold < 0:
        raise ValueError("O limite de divergencia nao pode ser negativo.")

    stack = np.stack([matrix.values for matrix in numeric], axis=0)
    mean = np.mean(stack, axis=0)
    std = np.std(stack, axis=0, ddof=0)
    amplitude = np.max(stack, axis=0) - np.min(stack, axis=0)
    alert = np.where(amplitude >= divergence_threshold, "Alta divergencia", "Convergente")

    return {
        "media": pd.DataFrame(mean, index=numeric[0].index, columns=numeric[0].columns),
        "desvio_padrao": pd.DataFrame(std, index=numeric[0].index, columns=numeric[0].columns),
        "amplitude": pd.DataFrame(amplitude, index=numeric[0].index, columns=numeric[0].columns),
        "alerta": pd.DataFrame(alert, index=numeric[0].index, columns=numeric[0].columns),
    }


def ranking_from_matrix(matrix: pd.DataFrame) -> pd.DataFrame:
    """Rank row items by average fuzzy priority."""

    numeric = validate_fuzzy_matrix(matrix)
    series = numeric.mean(axis=1).sort_values(ascending=False)
    ranking = series.reset_index()
    ranking.columns = ["elemento", "prioridade_fuzzy"]
    ranking.insert(0, "posicao", range(1, len(ranking) + 1))
    return ranking


def _rank_vector_from_matrix(matrix: pd.DataFrame) -> pd.Series:
    numeric = validate_fuzzy_matrix(matrix)
    priorities = numeric.mean(axis=1)
    return priorities.rank(ascending=False, method="average")


def spearman_between_matrices(first: pd.DataFrame, second: pd.DataFrame) -> float:
    """Calculate Spearman correlation between row rankings of two matrices."""

    first_ranks = _rank_vector_from_matrix(first)
    second_ranks = _rank_vector_from_matrix(second)
    common = [item for item in first_ranks.index if item in second_ranks.index]
    if len(common) < 2:
        return 1.0

    x = first_ranks.loc[common].astype(float)
    y = second_ranks.loc[common].astype(float)
    x_std = float(x.std(ddof=0))
    y_std = float(y.std(ddof=0))
    if x_std == 0.0 or y_std == 0.0:
        return 1.0 if x.equals(y) else 0.0
    return round(float(x.corr(y)), 4)


def kendall_w_from_matrices(matrices: Sequence[pd.DataFrame]) -> float:
    """Calculate Kendall's W for agreement among evaluator row rankings."""

    numeric = _validate_compatible_matrices(matrices)
    if len(numeric) < 2 or numeric[0].shape[0] < 2:
        return 1.0

    rank_rows = [_rank_vector_from_matrix(matrix) for matrix in numeric]
    ranks = pd.DataFrame(rank_rows)
    rank_sums = ranks.sum(axis=0)
    mean_rank_sum = float(rank_sums.mean())
    s_value = float(((rank_sums - mean_rank_sum) ** 2).sum())
    evaluators = len(numeric)
    items = numeric[0].shape[0]
    denominator = (evaluators**2) * (items**3 - items)
    if denominator == 0:
        return 1.0
    return round(float(12 * s_value / denominator), 4)


def sensitivity_to_evaluator_weights(
    matrices: Sequence[pd.DataFrame],
    weights: Sequence[float],
    iterations: int = 100,
    variation: float = 0.2,
) -> dict[str, float | str]:
    """Estimate ranking robustness under deterministic perturbations of evaluator weights."""

    numeric = _validate_compatible_matrices(matrices)
    numeric_weights = np.asarray(weights, dtype=float)
    if len(numeric) < 2:
        return {
            "top1_stability_percent": 100.0,
            "mean_spearman": 1.0,
            "min_spearman": 1.0,
            "baseline_top1": ranking_from_matrix(weighted_average_matrices(numeric, numeric_weights)).iloc[0]["elemento"],
        }

    baseline = weighted_average_matrices(numeric, numeric_weights)
    baseline_ranking = ranking_from_matrix(baseline)
    baseline_top1 = str(baseline_ranking.iloc[0]["elemento"])

    top1_matches = 0
    spearman_values: list[float] = []
    for iteration in range(iterations):
        factors = []
        for index in range(len(numeric_weights)):
            raw = ((iteration + 1) * (index + 3) * 37) % 1000
            unit = raw / 999.0
            factors.append(1 - variation + (2 * variation * unit))
        perturbed_weights = numeric_weights * np.asarray(factors, dtype=float)
        perturbed = weighted_average_matrices(numeric, perturbed_weights)
        perturbed_ranking = ranking_from_matrix(perturbed)
        if str(perturbed_ranking.iloc[0]["elemento"]) == baseline_top1:
            top1_matches += 1
        spearman_values.append(spearman_between_matrices(baseline, perturbed))

    return {
        "top1_stability_percent": round(100.0 * top1_matches / iterations, 2),
        "mean_spearman": round(float(np.mean(spearman_values)), 4),
        "min_spearman": round(float(np.min(spearman_values)), 4),
        "baseline_top1": baseline_top1,
    }


def _percent_level(value: float, *, inverse: bool = False) -> str:
    if inverse:
        if value <= 10:
            return "Baixo"
        if value <= 25:
            return "Moderado"
        return "Alto"
    if value >= 90:
        return "Alto"
    if value >= 70:
        return "Moderado"
    return "Baixo"


def _correlation_level(value: float) -> str:
    if value >= 0.90:
        return "Muito alto"
    if value >= 0.70:
        return "Alto"
    if value >= 0.40:
        return "Moderado"
    return "Baixo"


def _kendall_level(value: float) -> str:
    if value >= 0.80:
        return "Alta concordancia"
    if value >= 0.60:
        return "Boa concordancia"
    if value >= 0.30:
        return "Concordancia moderada"
    return "Baixa concordancia"


def statistical_confidence_indicators(
    matrices: Sequence[pd.DataFrame],
    weights: Sequence[float],
    consolidated: pd.DataFrame,
    consensus: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Return executive statistical confidence indicators after consolidation."""

    numeric = _validate_compatible_matrices(matrices)
    amplitude_df = consensus["amplitude"].astype(float)
    alert_df = consensus["alerta"].astype(str)
    total_cells = int(amplitude_df.size)
    divergent_cells = int((alert_df == "Alta divergencia").values.sum())
    convergence_rate = 100.0 * (total_cells - divergent_cells) / total_cells if total_cells else 0.0
    divergence_rate = 100.0 * divergent_cells / total_cells if total_cells else 0.0
    mean_divergence = float(amplitude_df.values.mean()) if total_cells else 0.0
    max_divergence = float(amplitude_df.values.max()) if total_cells else 0.0
    max_position = amplitude_df.stack().astype(float).idxmax() if total_cells else ("-", "-")
    simple_consolidated = weighted_average_matrices(numeric, [1.0] * len(numeric))
    spearman_simple_weighted = spearman_between_matrices(simple_consolidated, consolidated)
    kendall_w = kendall_w_from_matrices(numeric)
    sensitivity = sensitivity_to_evaluator_weights(numeric, weights)

    rows = [
        {
            "indicador": "Consenso geral",
            "valor": f"{convergence_rate:.1f}%",
            "classificacao": _percent_level(convergence_rate),
            "leitura": "Percentual de cruzamentos sem alta divergencia entre avaliadores.",
        },
        {
            "indicador": "Divergencia geral",
            "valor": f"{divergence_rate:.1f}%",
            "classificacao": _percent_level(divergence_rate, inverse=True),
            "leitura": "Percentual de cruzamentos marcados como alta divergencia.",
        },
        {
            "indicador": "Divergencia media",
            "valor": f"{mean_divergence:.3f}",
            "classificacao": _percent_level(mean_divergence * 100, inverse=True),
            "leitura": "Amplitude media entre maior e menor julgamento na escala fuzzy.",
        },
        {
            "indicador": "Maior ponto de conflito",
            "valor": f"{max_position[0]} x {max_position[1]} ({max_divergence:.3f})",
            "classificacao": _percent_level(max_divergence * 100, inverse=True),
            "leitura": "Relacionamento com maior diferenca entre avaliadores.",
        },
        {
            "indicador": "Kendall W",
            "valor": f"{kendall_w:.3f}",
            "classificacao": _kendall_level(kendall_w),
            "leitura": "Concordancia entre rankings dos avaliadores; quanto mais perto de 1, maior alinhamento.",
        },
        {
            "indicador": "Spearman simples vs ponderado",
            "valor": f"{spearman_simple_weighted:.3f}",
            "classificacao": _correlation_level(spearman_simple_weighted),
            "leitura": "Similaridade entre ranking por media simples e ranking ponderado por hierarquia.",
        },
        {
            "indicador": "Sensibilidade dos pesos",
            "valor": f"{sensitivity['top1_stability_percent']:.1f}% top-1",
            "classificacao": _percent_level(float(sensitivity["top1_stability_percent"])),
            "leitura": (
                f"Estabilidade do primeiro colocado sob variacao de pesos; Spearman medio "
                f"{float(sensitivity['mean_spearman']):.3f}."
            ),
        },
    ]
    return pd.DataFrame(rows)


def _tows_category(
    row_label: str,
    column_label: str,
    strengths: Sequence[str],
    weaknesses: Sequence[str],
    opportunities: Sequence[str],
    threats: Sequence[str],
) -> dict[str, str] | None:
    strengths_set = set(strengths)
    weaknesses_set = set(weaknesses)
    opportunities_set = set(opportunities)
    threats_set = set(threats)

    if row_label in strengths_set and column_label in opportunities_set:
        return {
            "quadrante": "SO",
            "tipo_estrategia": "Estrategia ofensiva / alavancagem",
            "interpretacao": "Usar uma forca interna para aproveitar uma oportunidade externa.",
            "direcionamento": "Priorizar crescimento, expansao, diferenciacao ou aceleracao estrategica.",
        }
    if row_label in strengths_set and column_label in threats_set:
        return {
            "quadrante": "ST",
            "tipo_estrategia": "Estrategia defensiva / protecao",
            "interpretacao": "Usar uma forca interna para reduzir ou enfrentar uma ameaca externa.",
            "direcionamento": "Priorizar protecao competitiva, mitigacao de riscos e resposta estrategica.",
        }
    if row_label in weaknesses_set and column_label in opportunities_set:
        return {
            "quadrante": "WO",
            "tipo_estrategia": "Estrategia de melhoria / reorientacao",
            "interpretacao": "Reduzir uma fraqueza interna para aproveitar uma oportunidade externa.",
            "direcionamento": "Priorizar melhoria, capacitacao, reestruturacao ou reforco organizacional.",
        }
    if row_label in weaknesses_set and column_label in threats_set:
        return {
            "quadrante": "WT",
            "tipo_estrategia": "Estrategia de sobrevivencia / contencao",
            "interpretacao": "Reduzir uma fraqueza interna e diminuir exposicao a uma ameaca externa.",
            "direcionamento": "Priorizar contencao, correcao de vulnerabilidades e reducao de danos.",
        }
    return None


def generate_tows_strategies(
    consolidated_matrix: pd.DataFrame,
    strengths: Sequence[str],
    weaknesses: Sequence[str],
    opportunities: Sequence[str],
    threats: Sequence[str],
) -> pd.DataFrame:
    """Generate sorted TOWS strategy candidates from a consolidated matrix."""

    numeric = validate_fuzzy_matrix(consolidated_matrix)
    records: list[dict[str, str | float]] = []

    for row_label in numeric.index:
        for column_label in numeric.columns:
            category = _tows_category(row_label, column_label, strengths, weaknesses, opportunities, threats)
            if category is None:
                continue
            records.append(
                {
                    "quadrante": category["quadrante"],
                    "tipo_estrategia": category["tipo_estrategia"],
                    "fator_interno": row_label,
                    "fator_externo": column_label,
                    "prioridade_fuzzy": float(numeric.loc[row_label, column_label]),
                    "interpretacao": category["interpretacao"],
                    "direcionamento": category["direcionamento"],
                }
            )

    strategies = pd.DataFrame(records)
    if strategies.empty:
        return strategies

    strategies = strategies.sort_values(["prioridade_fuzzy", "quadrante"], ascending=[False, True]).reset_index(drop=True)
    strategies.insert(0, "posicao", range(1, len(strategies) + 1))
    return strategies


def strategic_profile_from_tows(tows_strategies: pd.DataFrame) -> pd.DataFrame:
    """Summarize TOWS strategies into an executive strategic posture."""

    if tows_strategies.empty:
        return pd.DataFrame()

    quadrant_labels = {
        "SO": {
            "perfil_estrategico": "Ofensivo / crescimento",
            "leitura_executiva": (
                "Predominam relacoes entre forcas e oportunidades. A leitura sugere postura de crescimento, "
                "expansao, alavancagem de capacidades internas e captura ativa de oportunidades externas."
            ),
        },
        "ST": {
            "perfil_estrategico": "Defensivo / conservador",
            "leitura_executiva": (
                "Predominam relacoes entre forcas e ameacas. A leitura sugere postura conservadora, com uso "
                "das capacidades internas para proteger o negocio, reduzir riscos e preservar posicao competitiva."
            ),
        },
        "WO": {
            "perfil_estrategico": "Reorientacao / adaptativo",
            "leitura_executiva": (
                "Predominam relacoes entre fraquezas e oportunidades. A leitura sugere necessidade de melhoria, "
                "capacitacao ou reorientacao interna para aproveitar oportunidades externas."
            ),
        },
        "WT": {
            "perfil_estrategico": "Reativo / sobrevivencia",
            "leitura_executiva": (
                "Predominam relacoes entre fraquezas e ameacas. A leitura sugere postura reativa, com foco em "
                "contencao, reducao de vulnerabilidades e protecao contra perdas."
            ),
        },
    }

    records: list[dict[str, str | float | int]] = []
    total_intensity = float(tows_strategies["prioridade_fuzzy"].sum())
    grouped = tows_strategies.groupby("quadrante", sort=False)

    for quadrant in ["SO", "ST", "WO", "WT"]:
        subset = grouped.get_group(quadrant) if quadrant in grouped.groups else pd.DataFrame()
        intensity = float(subset["prioridade_fuzzy"].sum()) if not subset.empty else 0.0
        share = (100.0 * intensity / total_intensity) if total_intensity > 0 else 0.0
        mean_priority = float(subset["prioridade_fuzzy"].mean()) if not subset.empty else 0.0
        max_priority = float(subset["prioridade_fuzzy"].max()) if not subset.empty else 0.0
        records.append(
            {
                "quadrante": quadrant,
                "perfil_estrategico": quadrant_labels[quadrant]["perfil_estrategico"],
                "intensidade_total": round(intensity, 4),
                "participacao_percentual": round(share, 2),
                "prioridade_media": round(mean_priority, 4),
                "maior_prioridade": round(max_priority, 4),
                "quantidade_estrategias": int(len(subset)),
                "leitura_executiva": quadrant_labels[quadrant]["leitura_executiva"],
            }
        )

    profile = pd.DataFrame(records)
    profile = profile.sort_values(
        ["intensidade_total", "maior_prioridade", "prioridade_media"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    profile.insert(0, "posicao", range(1, len(profile) + 1))
    profile["status"] = ["Predominante" if index == 0 else "Secundario" for index in range(len(profile))]
    return profile


def consolidate_matrices(
    matrices_by_evaluator: Mapping[str, pd.DataFrame],
    evaluator_weights: Mapping[str, float],
    matrix_name: str,
    strengths: Sequence[str],
    weaknesses: Sequence[str],
    opportunities: Sequence[str],
    threats: Sequence[str],
    method: str = "weighted",
    divergence_threshold: float = 0.25,
) -> ConsolidationResult:
    """Consolidate one matrix type and return every derived result."""

    if not matrices_by_evaluator:
        raise ValueError("Nenhuma matriz foi informada para consolidacao.")

    matrices: list[pd.DataFrame] = []
    weights: list[float] = []
    used_weights: list[dict[str, str | float]] = []

    for evaluator_key, matrix in matrices_by_evaluator.items():
        weight = float(evaluator_weights.get(evaluator_key, 1.0)) if method == "weighted" else 1.0
        matrices.append(matrix)
        weights.append(weight)
        used_weights.append({"avaliador": evaluator_key, "matriz": matrix_name, "peso_aplicado": weight})

    consolidated = weighted_average_matrices(matrices, weights)
    consensus = consensus_indicators(matrices, divergence_threshold=divergence_threshold)
    ranking = ranking_from_matrix(consolidated)
    statistical_confidence = statistical_confidence_indicators(matrices, weights, consolidated, consensus)
    tows = (
        generate_tows_strategies(consolidated, strengths, weaknesses, opportunities, threats)
        if matrix_name == TOWS_MATRIX_NAME
        else pd.DataFrame()
    )
    strategic_profile = strategic_profile_from_tows(tows) if matrix_name == TOWS_MATRIX_NAME else pd.DataFrame()

    return ConsolidationResult(
        consolidated=consolidated,
        consensus=consensus,
        ranking=ranking,
        used_weights=pd.DataFrame(used_weights),
        tows_strategies=tows,
        strategic_profile=strategic_profile,
        statistical_confidence=statistical_confidence,
    )

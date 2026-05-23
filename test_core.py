import unittest

import pandas as pd

from fuzzyswot.constants import TOWS_MATRIX_NAME
from fuzzyswot.core import (
    consensus_indicators,
    consolidate_matrices,
    default_matrix,
    generate_tows_strategies,
    ranking_from_matrix,
    strategic_profile_from_tows,
    weighted_average_matrices,
)
from fuzzyswot.exports import pdf_bytes
from fuzzyswot.models import Evaluator


class CoreTests(unittest.TestCase):
    def test_evaluator_weight_is_automatic_from_hierarchy(self):
        evaluator = Evaluator(name="Ana", hierarchical_function="Diretor", weight=0.1)

        self.assertAlmostEqual(evaluator.weight, 0.8)

    def test_weighted_average_matrices(self):
        first = pd.DataFrame([[0.2, 0.4], [0.6, 0.8]], index=["A", "B"], columns=["X", "Y"])
        second = pd.DataFrame([[0.8, 0.6], [0.4, 0.2]], index=["A", "B"], columns=["X", "Y"])

        result = weighted_average_matrices([first, second], [1, 3])

        self.assertAlmostEqual(result.loc["A", "X"], 0.65)
        self.assertAlmostEqual(result.loc["B", "Y"], 0.35)

    def test_consensus_indicators_flags_divergence(self):
        first = pd.DataFrame([[0.1]], index=["A"], columns=["X"])
        second = pd.DataFrame([[0.7]], index=["A"], columns=["X"])

        result = consensus_indicators([first, second], divergence_threshold=0.25)

        self.assertEqual(result["alerta"].loc["A", "X"], "Alta divergencia")
        self.assertAlmostEqual(result["amplitude"].loc["A", "X"], 0.6)

    def test_ranking_from_matrix(self):
        matrix = pd.DataFrame([[0.9, 0.7], [0.2, 0.4]], index=["A", "B"], columns=["X", "Y"])

        ranking = ranking_from_matrix(matrix)

        self.assertEqual(ranking.iloc[0]["elemento"], "A")
        self.assertAlmostEqual(ranking.iloc[0]["prioridade_fuzzy"], 0.8)

    def test_generate_tows_strategies_orders_by_priority(self):
        matrix = pd.DataFrame(
            [[0.4, 0.9], [0.8, 0.2]],
            index=["Forca 1", "Fraqueza 1"],
            columns=["Oportunidade 1", "Ameaca 1"],
        )

        result = generate_tows_strategies(
            matrix,
            strengths=["Forca 1"],
            weaknesses=["Fraqueza 1"],
            opportunities=["Oportunidade 1"],
            threats=["Ameaca 1"],
        )

        self.assertEqual(result.iloc[0]["quadrante"], "ST")
        self.assertAlmostEqual(result.iloc[0]["prioridade_fuzzy"], 0.9)
        self.assertEqual(set(result["quadrante"]), {"SO", "ST", "WO", "WT"})

    def test_consolidate_matrices_generates_tows(self):
        rows = ["Forca 1", "Fraqueza 1"]
        columns = ["Oportunidade 1", "Ameaca 1"]
        matrix = default_matrix(rows, columns, 0.7)
        result = consolidate_matrices(
            {"Ana | Diretor | Estrategia": matrix},
            {"Ana | Diretor | Estrategia": 0.8},
            TOWS_MATRIX_NAME,
            strengths=["Forca 1"],
            weaknesses=["Fraqueza 1"],
            opportunities=["Oportunidade 1"],
            threats=["Ameaca 1"],
        )

        self.assertEqual(len(result.tows_strategies), 4)
        self.assertFalse(result.strategic_profile.empty)
        self.assertEqual(result.ranking.iloc[0]["elemento"], "Forca 1")

    def test_strategic_profile_identifies_dominant_quadrant(self):
        strategies = pd.DataFrame(
            [
                {"quadrante": "SO", "prioridade_fuzzy": 0.9},
                {"quadrante": "SO", "prioridade_fuzzy": 0.8},
                {"quadrante": "ST", "prioridade_fuzzy": 0.3},
                {"quadrante": "WO", "prioridade_fuzzy": 0.2},
                {"quadrante": "WT", "prioridade_fuzzy": 0.1},
            ]
        )

        profile = strategic_profile_from_tows(strategies)

        self.assertEqual(profile.iloc[0]["quadrante"], "SO")
        self.assertEqual(profile.iloc[0]["status"], "Predominante")
        self.assertIn("Ofensivo", profile.iloc[0]["perfil_estrategico"])

    def test_mismatched_matrices_fail(self):
        first = pd.DataFrame([[0.2]], index=["A"], columns=["X"])
        second = pd.DataFrame([[0.2]], index=["B"], columns=["X"])

        with self.assertRaises(ValueError):
            weighted_average_matrices([first, second], [1, 1])

    def test_pdf_accepts_consensus_indicators(self):
        ranking = pd.DataFrame([{"posicao": 1, "elemento": "Forca 1", "prioridade_fuzzy": 0.8}])
        consensus = {
            TOWS_MATRIX_NAME: {
                "amplitude": pd.DataFrame([[0.6]], index=["Forca 1"], columns=["Oportunidade 1"]),
                "alerta": pd.DataFrame([["Alta divergencia"]], index=["Forca 1"], columns=["Oportunidade 1"]),
            }
        }

        content = pdf_bytes(
            project={"name": "Teste"},
            evaluators=[{"name": "Ana"}, {"name": "Bruno"}],
            strengths=["Forca 1"],
            weaknesses=["Fraqueza 1"],
            opportunities=["Oportunidade 1"],
            threats=["Ameaca 1"],
            rankings={TOWS_MATRIX_NAME: ranking},
            consensus=consensus,
            divergence_rate_threshold=10.0,
            tows_strategies=pd.DataFrame(),
            strategic_profile=pd.DataFrame(),
        )

        self.assertGreater(len(content), 1000)


if __name__ == "__main__":
    unittest.main()

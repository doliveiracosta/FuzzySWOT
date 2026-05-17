"""Shared constants for Fuzzy SWOT analysis."""

APP_NAME = "FuzzySWOT Strategy Prioritizer"
APP_OWNER = "David de Oliveira Costa"
APP_OWNER_LABEL = f"Desenvolvido por {APP_OWNER}"

FUZZY_SCALE = {
    0.0: "Falso / nenhuma relacao",
    0.1: "Quase falso",
    0.2: "Bastante falso",
    0.3: "Algo falso",
    0.4: "Mais falso que verdadeiro",
    0.5: "Tao falso quanto verdadeiro",
    0.6: "Mais verdadeiro que falso",
    0.7: "Algo verdadeiro",
    0.8: "Bastante verdadeiro",
    0.9: "Quase verdadeiro",
    1.0: "Verdadeiro / relacao maxima",
}

FUZZY_COLOR_SCALE = {
    0.0: "#b71c1c",
    0.1: "#d32f2f",
    0.2: "#f44336",
    0.3: "#ef6c00",
    0.4: "#fb8c00",
    0.5: "#fdd835",
    0.6: "#c0ca33",
    0.7: "#7cb342",
    0.8: "#43a047",
    0.9: "#2e7d32",
    1.0: "#1b5e20",
}

HIERARCHY_WEIGHTS = {
    "Presidente do Conselho": 1.00,
    "CEO / Presidente Executivo": 0.90,
    "Diretor": 0.80,
    "Gerente": 0.70,
    "Coordenador / Supervisor": 0.60,
    "Especialista / Analista": 0.50,
    "Consultor externo": 0.50,
    "Outros": 0.40,
}

TOWS_MATRIX_NAME = "Matriz TOWS: Forcas/Fraquezas x Oportunidades/Ameacas"


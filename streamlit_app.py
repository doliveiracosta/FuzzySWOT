"""Streamlit MVP for the Fuzzy SWOT Strategy Prioritizer."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from textwrap import dedent

import pandas as pd
import streamlit as st

from fuzzyswot.constants import FUZZY_SCALE, HIERARCHY_WEIGHTS, TOWS_MATRIX_NAME
from fuzzyswot.core import (
    consolidate_matrices,
    default_matrix,
    fuzzy_color,
    fuzzy_label,
    matrix_definitions,
    normalize_items,
)
from fuzzyswot.exports import pdf_bytes, write_pdf_report
from fuzzyswot.models import Evaluator, Project

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
PDF_FILE_NAME = "relatorio_consultivo_fuzzy_swot.pdf"
PUBLIC_MODE_VALUES = {"public", "cloud", "production"}


def public_deployment_enabled() -> bool:
    env_mode = os.getenv("FUZZYSWOT_DEPLOYMENT_MODE", "").lower()
    if env_mode in PUBLIC_MODE_VALUES:
        return True

    try:
        secret_mode = str(st.secrets.get("FUZZYSWOT_DEPLOYMENT_MODE", "")).lower()
    except Exception:
        secret_mode = ""
    return secret_mode in PUBLIC_MODE_VALUES


def init_state() -> None:
    defaults = {
        "project": Project().to_dict(),
        "evaluators": [],
        "strengths": ["Marca reconhecida", "Equipe experiente", "Base de clientes ativa"],
        "weaknesses": ["Processos manuais", "Baixa integracao de dados", "Dependencia de poucos canais"],
        "opportunities": ["Novos mercados digitais", "Parcerias estrategicas", "Automacao com IA"],
        "threats": ["Concorrencia intensa", "Mudancas regulatorias", "Pressao de custos"],
        "matrices": {},
        "consolidated": {},
        "consensus": {},
        "rankings": {},
        "tows_strategies": pd.DataFrame(),
        "last_pdf_path": "",
    }
    for key, value in defaults

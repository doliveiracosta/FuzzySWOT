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
STEPS = ["Projeto", "Itens SWOT", "Avaliadores", "Matrizes", "Consolidacao", "Exportacao"]


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
        "current_step": 0,
        "notice": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def go_to_step(index: int, notice: str = "") -> None:
    st.session_state.current_step = max(0, min(index, len(STEPS) - 1))
    st.session_state.notice = notice
    st.rerun()


def go_next(notice: str = "") -> None:
    go_to_step(st.session_state.current_step + 1, notice)


def parse_lines(value: str) -> list[str]:
    return normalize_items(value.splitlines())


def lines_value(items: list[str]) -> str:
    return "\n".join(items)


def stable_key(*parts: str) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def evaluator_weights() -> dict[str, float]:
    return {Evaluator(**item).key: Evaluator(**item).weight for item in st.session_state.evaluators}


def matrix_completion_status(matrix_name: str, evaluator_options: list[str]) -> tuple[list[str], list[str]]:
    completed = [
        evaluator
        for evaluator in evaluator_options
        if (evaluator, matrix_name) in st.session_state.matrices
    ]
    pending = [evaluator for evaluator in evaluator_options if evaluator not in completed]
    return completed, pending


def render_fuzzy_scale() -> None:
    blocks = []
    for value, label in FUZZY_SCALE.items():
        text_color = "#111111" if value in {0.4, 0.5, 0.6} else "#ffffff"
        blocks.append(
            f'<div class="fuzzy-scale-item" style="background:{fuzzy_color(value)}; color:{text_color};">'
            f"<strong>{value:.1f}</strong><span>{label}</span></div>"
        )

    st.markdown(
        dedent(
            f"""
            <style>
            .fuzzy-scale {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
                gap: 6px;
                margin: 0.4rem 0 1.2rem;
            }}
            .fuzzy-scale-item {{
                min-height: 68px;
                border-radius: 6px;
                padding: 8px 7px;
                box-shadow: inset 0 0 0 1px rgba(0,0,0,.08);
            }}
            .fuzzy-scale-item strong {{
                display: block;
                font-size: 1rem;
                line-height: 1.1;
            }}
            .fuzzy-scale-item span {{
                display: block;
                margin-top: 4px;
                font-size: .74rem;
                line-height: 1.15;
            }}
            .fuzzy-chip {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 32px;
                width: 100%;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: .78rem;
                font-weight: 600;
                line-height: 1.15;
                text-align: center;
                box-shadow: inset 0 0 0 1px rgba(0,0,0,.08);
            }}
            </style>
            <div class="fuzzy-scale">{''.join(blocks)}</div>
            """
        ),
        unsafe_allow_html=True,
    )


def fuzzy_chip(value: float) -> str:
    rounded = round(float(value), 1)
    text_color = "#111111" if rounded in {0.4, 0.5, 0.6} else "#ffffff"
    return (
        f'<div class="fuzzy-chip" style="background:{fuzzy_color(rounded)}; color:{text_color};">'
        f"{rounded:.1f} - {fuzzy_label(rounded)}</div>"
    )


def project_inputs() -> None:
    st.subheader("Projeto")
    with st.form("project_form"):
        project = st.session_state.project
        name = st.text_input("Projeto", project.get("name", "Analise SWOT Fuzzy"))
        organization = st.text_input("Organizacao", project.get("organization", ""))
        responsible = st.text_input("Responsavel", project.get("responsible", ""))
        judgment_mode = st.selectbox(
            "Modalidade de julgamento",
            ["Individual por avaliador", "Coletivo em workshop", "Hibrido"],
            index=["Individual por avaliador", "Coletivo em workshop", "Hibrido"].index(
                project.get("judgment_mode", "Individual por avaliador")
            ),
        )
        description = st.text_area("Descricao", project.get("description", ""), height=100)
        if st.form_submit_button("Salvar projeto", type="primary"):
            st.session_state.project = Project(
                name=name,
                organization=organization,
                responsible=responsible,
                judgment_mode=judgment_mode,
                description=description,
            ).to_dict()
            go_next("Projeto salvo. Avancamos para Itens SWOT.")


def swot_inputs() -> None:
    st.subheader("Itens SWOT")
    st.caption("Digite um item por linha.")
    col1, col2 = st.columns(2)
    with col1:
        strengths = st.text_area("Forcas", lines_value(st.session_state.strengths), height=170)
        opportunities = st.text_area("Oportunidades", lines_value(st.session_state.opportunities), height=170)
    with col2:
        weaknesses = st.text_area("Fraquezas", lines_value(st.session_state.weaknesses), height=170)
        threats = st.text_area("Ameacas", lines_value(st.session_state.threats), height=170)

    if st.button("Salvar itens SWOT", type="primary"):
        st.session_state.strengths = parse_lines(strengths)
        st.session_state.weaknesses = parse_lines(weaknesses)
        st.session_state.opportunities = parse_lines(opportunities)
        st.session_state.threats = parse_lines(threats)
        go_next("Itens SWOT salvos. Avancamos para Avaliadores.")


def evaluator_inputs() -> None:
    st.subheader("Avaliadores")
    count = st.number_input("Quantidade de avaliadores", min_value=1, max_value=50, value=max(1, len(st.session_state.evaluators) or 3))

    existing = st.session_state.evaluators
    rows = []
    for index in range(int(count)):
        current = existing[index] if index < len(existing) else {}
        with st.expander(f"Avaliador {index + 1}", expanded=index < 3):
            name = st.text_input("Nome", current.get("name", f"Avaliador {index + 1}"), key=f"eval_name_{index}")
            area = st.text_input("Area", current.get("area", ""), key=f"eval_area_{index}")
            role = st.selectbox(
                "Funcao hierarquica",
                list(HIERARCHY_WEIGHTS),
                index=list(HIERARCHY_WEIGHTS).index(current.get("hierarchical_function", "Outros")),
                key=f"eval_role_{index}",
            )
            role_detail = st.text_input("Detalhe", current.get("role_detail", ""), key=f"eval_detail_{index}")
            weight = HIERARCHY_WEIGHTS[role]
            st.info(f"Peso automatico pela funcao hierarquica: {weight:.2f}")
            rows.append(
                Evaluator(
                    name=name,
                    area=area,
                    hierarchical_function=role,
                    role_detail=role_detail,
                    weight=weight,
                ).to_dict()
            )

    if st.button("Salvar avaliadores", type="primary"):
        st.session_state.evaluators = rows
        go_next("Avaliadores salvos. Avancamos para Matrizes.")

    if st.session_state.evaluators:
        st.dataframe(pd.DataFrame(st.session_state.evaluators), use_container_width=True)


def matrix_inputs() -> None:
    st.subheader("Matrizes de julgamento fuzzy")
    if not st.session_state.evaluators:
        st.warning("Cadastre os avaliadores antes de preencher matrizes.")
        return

    defs = matrix_definitions(
        st.session_state.strengths,
        st.session_state.weaknesses,
        st.session_state.opportunities,
        st.session_state.threats,
    )
    if not defs:
        st.warning("Cadastre itens internos e externos antes de preencher matrizes.")
        return

    evaluator_options = [Evaluator(**item).key for item in st.session_state.evaluators]
    evaluator_key = st.selectbox("Avaliador", evaluator_options)
    matrix_name = st.selectbox("Matriz", list(defs))
    rows, columns, description = defs[matrix_name]
    st.caption(description)
    render_fuzzy_scale()
    completed, pending = matrix_completion_status(matrix_name, evaluator_options)
    st.progress(len(completed) / len(evaluator_options), text=f"Matrizes preenchidas: {len(completed)} de {len(evaluator_options)} avaliadores")
    if pending:
        st.info("Ainda faltam: " + ", ".join(pending))
    else:
        st.success("Todos os avaliadores ja preencheram esta matriz.")

    matrix_key = (evaluator_key, matrix_name)
    current = st.session_state.matrices.get(matrix_key, default_matrix(rows, columns))
    current = current.reindex(index=rows, columns=columns).fillna(0.5).astype(float).clip(0.0, 1.0)

    matrix_values = {}
    for row in rows:
        st.markdown(f"#### {row}")
        matrix_values[row] = {}
        for start in range(0, len(columns), 3):
            chunk = columns[start : start + 3]
            slider_columns = st.columns(len(chunk))
            for layout_column, column in zip(slider_columns, chunk):
                with layout_column:
                    value = float(current.loc[row, column])
                    score = st.slider(
                        column,
                        min_value=0.0,
                        max_value=1.0,
                        value=value,
                        step=0.1,
                        key=f"score_{stable_key(evaluator_key, matrix_name, row, column)}",
                    )
                    st.markdown(fuzzy_chip(score), unsafe_allow_html=True)
                    matrix_values[row][column] = score

    edited = pd.DataFrame.from_dict(matrix_values, orient="index", columns=columns).astype(float)

    if st.button("Salvar matriz atual", type="primary"):
        st.session_state.matrices[matrix_key] = edited.astype(float).clip(0.0, 1.0)
        completed, pending = matrix_completion_status(matrix_name, evaluator_options)
        if pending:
            st.session_state.notice = (
                f"Matriz de {evaluator_key} salva. Ainda faltam {len(pending)} avaliador(es): "
                + ", ".join(pending)
            )
            st.rerun()
        go_next("Todas as matrizes dos avaliadores foram salvas. Avancamos para Consolidacao.")

    with st.expander("Previa numerica da matriz"):
        st.dataframe(edited, use_container_width=True)

    if st.session_state.matrices:
        summary = [
            {"avaliador": evaluator, "matriz": matrix, "linhas": df.shape[0], "colunas": df.shape[1]}
            for (evaluator, matrix), df in st.session_state.matrices.items()
        ]
        st.dataframe(pd.DataFrame(summary), use_container_width=True)


def consolidation_inputs() -> None:
    st.subheader("Consolidacao e consenso")
    if not st.session_state.matrices:
        st.warning("Preencha ao menos uma matriz antes de consolidar.")
        return

    matrix_names = sorted({matrix_name for _, matrix_name in st.session_state.matrices})
    matrix_name = st.selectbox("Matriz para consolidar", matrix_names)
    method_label = st.radio("Metodo", ["Media ponderada pela funcao hierarquica", "Media simples"])
    threshold = st.slider("Limite de divergencia", min_value=0.05, max_value=1.0, value=0.25, step=0.05)

    selected = {
        evaluator: df
        for (evaluator, current_matrix_name), df in st.session_state.matrices.items()
        if current_matrix_name == matrix_name
    }

    if st.button("Consolidar", type="primary"):
        result = consolidate_matrices(
            selected,
            evaluator_weights(),
            matrix_name,
            st.session_state.strengths,
            st.session_state.weaknesses,
            st.session_state.opportunities,
            st.session_state.threats,
            method="weighted" if method_label.startswith("Media ponderada") else "simple",
            divergence_threshold=threshold,
        )
        st.session_state.consolidated[matrix_name] = result.consolidated
        st.session_state.consensus[matrix_name] = result.consensus
        st.session_state.rankings[matrix_name] = result.ranking
        if matrix_name == TOWS_MATRIX_NAME:
            st.session_state.tows_strategies = result.tows_strategies
        go_next("Consolidacao realizada. Avancamos para Exportacao.")

    if matrix_name in st.session_state.consolidated:
        st.markdown("#### Pesos usados")
        weights_df = pd.DataFrame(
            [{"avaliador": evaluator, "peso": evaluator_weights().get(evaluator, 1.0)} for evaluator in selected]
        )
        st.dataframe(weights_df, use_container_width=True)
        st.markdown("#### Matriz consolidada")
        st.dataframe(st.session_state.consolidated[matrix_name], use_container_width=True)
        st.markdown("#### Ranking")
        st.dataframe(st.session_state.rankings[matrix_name], use_container_width=True)
        st.markdown("#### Alerta de divergencia")
        st.dataframe(st.session_state.consensus[matrix_name]["alerta"], use_container_width=True)
        if matrix_name == TOWS_MATRIX_NAME and not st.session_state.tows_strategies.empty:
            st.markdown("#### Estrategias TOWS")
            st.dataframe(st.session_state.tows_strategies, use_container_width=True)


def export_inputs() -> None:
    st.subheader("Relatorio PDF")
    public_mode = public_deployment_enabled()
    pdf_kwargs = dict(
        project=st.session_state.project,
        evaluators=st.session_state.evaluators,
        strengths=st.session_state.strengths,
        weaknesses=st.session_state.weaknesses,
        opportunities=st.session_state.opportunities,
        threats=st.session_state.threats,
        rankings=st.session_state.rankings,
        consensus=st.session_state.consensus,
        tows_strategies=st.session_state.tows_strategies,
    )

    if public_mode:
        st.info("Modo publico: o PDF e entregue por download e nao e salvo no servidor.")
    else:
        if st.button("Gerar e salvar PDF nesta maquina", type="primary"):
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            pdf_path = OUTPUT_DIR / PDF_FILE_NAME
            write_pdf_report(str(pdf_path), **pdf_kwargs)
            st.session_state.last_pdf_path = str(pdf_path)
            st.success("PDF gerado e salvo com sucesso.")

        if st.session_state.last_pdf_path:
            st.markdown("Arquivo salvo em:")
            st.code(st.session_state.last_pdf_path)

    st.download_button(
        "Baixar PDF consultivo",
        data=pdf_bytes(**pdf_kwargs),
        file_name=PDF_FILE_NAME,
        mime="application/pdf",
    )


def main() -> None:
    st.set_page_config(page_title="FuzzySWOT Strategy Prioritizer", layout="wide")
    init_state()
    public_mode = public_deployment_enabled()
    st.title("FuzzySWOT Strategy Prioritizer")
    st.caption("MVP web para priorizacao estrategica com logica fuzzy e matriz TOWS.")
    if public_mode:
        st.info(
            "Esta versao publica nao possui login nem banco de dados. Evite inserir dados pessoais, "
            "sigilosos ou informacoes sensiveis; use a ferramenta para fins academicos, demonstrativos "
            "e exploratorios."
        )

    selected_step = st.radio(
        "Etapa",
        STEPS,
        index=st.session_state.current_step,
        horizontal=True,
    )
    selected_index = STEPS.index(selected_step)
    if selected_index != st.session_state.current_step:
        st.session_state.current_step = selected_index

    if st.session_state.notice:
        st.success(st.session_state.notice)
        st.session_state.notice = ""

    if st.session_state.current_step == 0:
        project_inputs()
    elif st.session_state.current_step == 1:
        swot_inputs()
    elif st.session_state.current_step == 2:
        evaluator_inputs()
    elif st.session_state.current_step == 3:
        matrix_inputs()
    elif st.session_state.current_step == 4:
        consolidation_inputs()
    else:
        export_inputs()


if __name__ == "__main__":
    main()

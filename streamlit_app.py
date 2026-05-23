"""Streamlit MVP for the Fuzzy SWOT Strategy Prioritizer."""

from __future__ import annotations

import base64
import hashlib
import math
import mimetypes
import os
from pathlib import Path
from textwrap import dedent

import pandas as pd
import streamlit as st

from fuzzyswot.constants import APP_NAME, APP_OWNER_LABEL, FUZZY_SCALE, HIERARCHY_WEIGHTS, TOWS_MATRIX_NAME
from fuzzyswot.core import (
    consolidate_matrices,
    default_matrix,
    fuzzy_color,
    fuzzy_label,
    matrix_definitions,
    normalize_items,
    strategic_profile_from_tows,
)
from fuzzyswot.exports import pdf_bytes
from fuzzyswot.models import Evaluator, Project

PDF_FILE_NAME = "relatorio_consultivo_fuzzy_swot.pdf"
PUBLIC_MODE_VALUES = {"public", "cloud", "production"}
STEPS = ["Projeto", "Itens SWOT", "Avaliadores", "Matrizes", "Consolidacao", "Exportacao"]


def asset_data_uri(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def render_opening_cover() -> None:
    st.markdown(
        """
        <style>
        .institutional-logos {
            display: flex;
            align-items: center;
            gap: 22px;
            margin: 0.2rem 0 1.0rem;
        }
        .institutional-logos img {
            object-fit: contain;
            width: auto;
            display: block;
        }
        .institutional-logos .logo-upe {
            height: 52px;
        }
        .institutional-logos .logo-poli {
            height: 54px;
        }
        .institutional-logos .logo-ppgec {
            height: 48px;
        }
        .author-links {
            display: flex;
            align-items: center;
            gap: 18px;
            margin: 0.1rem 0 1.2rem;
        }
        .author-links a {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            color: #6b7280;
            text-decoration: none;
            font-size: 0.92rem;
        }
        .author-links a:hover {
            color: #374151;
            text-decoration: none;
        }
        .author-links img {
            width: 18px;
            height: 18px;
            display: inline-block;
        }
        .usage-guide {
            margin: 0.2rem 0 1.1rem;
            color: #4b5563;
            font-size: 0.94rem;
        }
        .usage-guide summary {
            cursor: pointer;
            color: #6b7280;
            text-decoration: none;
            width: fit-content;
            list-style: none;
        }
        .usage-guide summary:hover {
            color: #374151;
        }
        .usage-guide summary::-webkit-details-marker {
            display: none;
        }
        .usage-guide ol {
            margin: 0.75rem 0 0;
            padding-left: 1.25rem;
            line-height: 1.45;
        }
        .usage-guide li {
            margin-bottom: 0.42rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    logo_upe = Path("assets/logo_upe.jfif")
    logo_poli = Path("assets/logo_upe_poli.png")
    logo_ppgec = Path("assets/logo_ppgec.png")
    if logo_upe.exists() and logo_poli.exists() and logo_ppgec.exists():
        st.markdown(
            f"""
            <div class="institutional-logos">
                <img class="logo-upe" src="{asset_data_uri(logo_upe)}" alt="UPE">
                <img class="logo-poli" src="{asset_data_uri(logo_poli)}" alt="POLI">
                <img class="logo-ppgec" src="{asset_data_uri(logo_ppgec)}" alt="PPGEC">
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <details class="usage-guide">
            <summary>Como utilizar a plataforma</summary>
            <ol>
                <li><strong>Preencha os dados do projeto:</strong> informe nome, organizacao, responsavel, modalidade de julgamento e descricao do contexto estrategico.</li>
                <li><strong>Cadastre os itens SWOT:</strong> registre forcas, fraquezas, oportunidades e ameacas, usando um item por linha.</li>
                <li><strong>Cadastre os avaliadores:</strong> informe nome, area e funcao hierarquica. O peso e definido automaticamente pela funcao.</li>
                <li><strong>Preencha as matrizes fuzzy:</strong> selecione avaliador e matriz, atribuindo notas percentuais conforme a escala apresentada.</li>
                <li><strong>Salve as avaliacoes:</strong> registre cada matriz preenchida. Quando todos os avaliadores concluirem, avance para a consolidacao.</li>
                <li><strong>Consolide os julgamentos:</strong> escolha media ponderada pela funcao hierarquica ou media simples e defina o limite de divergencia.</li>
                <li><strong>Analise os resultados:</strong> verifique matriz consolidada, ranking, estrategias TOWS e alertas de divergencia.</li>
                <li><strong>Exporte o relatorio:</strong> baixe o PDF consultivo com os dados do projeto e os resultados consolidados.</li>
            </ol>
        </details>
        """,
        unsafe_allow_html=True,
    )

    st.title(APP_NAME)
    st.caption("Plataforma para priorizacao estrategica com logica fuzzy e matriz TOWS.")
    st.markdown(f"**{APP_OWNER_LABEL}**")

    logo_orcid = Path("assets/logo_orcid.svg")
    logo_linkedin = Path("assets/logo_linkedin.svg")
    if logo_orcid.exists() and logo_linkedin.exists():
        st.markdown(
            f"""
            <div class="author-links">
                <a href="https://orcid.org/0000-0002-6138-7451" target="_blank">
                    <img src="{asset_data_uri(logo_orcid)}" alt="ORCID">
                    <span>Perfil academico</span>
                </a>
                <a href="https://www.linkedin.com/in/daviddeoliveiracosta" target="_blank">
                    <img src="{asset_data_uri(logo_linkedin)}" alt="LinkedIn">
                    <span>Perfil profissional</span>
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )


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
        "strategic_profile": pd.DataFrame(),
        "statistical_confidence": {},
        "divergence_threshold_percent": 25,
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
                grid-template-columns: repeat(11, minmax(72px, 1fr));
                gap: 4px;
                margin: 0.35rem 0 1rem;
            }}
            .fuzzy-scale-item {{
                min-height: 52px;
                border-radius: 6px;
                padding: 6px 6px;
                box-shadow: inset 0 0 0 1px rgba(0,0,0,.08);
            }}
            .fuzzy-scale-item strong {{
                display: block;
                font-size: .86rem;
                line-height: 1.1;
            }}
            .fuzzy-scale-item span {{
                display: block;
                margin-top: 3px;
                font-size: .62rem;
                line-height: 1.08;
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


def render_strategic_radar(profile: pd.DataFrame) -> None:
    if profile.empty:
        return

    values = {str(row["quadrante"]): float(row["participacao_percentual"]) for _, row in profile.iterrows()}
    labels = {
        "SO": "Ofensivo",
        "ST": "Defensivo",
        "WO": "Adaptativo",
        "WT": "Reativo",
    }
    order = ["SO", "ST", "WT", "WO"]
    center = 150
    radius = 105
    angles = [-90, 0, 90, 180]

    def point(percent: float, angle_degrees: float) -> tuple[float, float]:
        angle = math.radians(angle_degrees)
        scaled = radius * max(0.0, min(percent, 100.0)) / 100.0
        return center + scaled * math.cos(angle), center + scaled * math.sin(angle)

    def axis_point(angle_degrees: float, scale: float = 1.0) -> tuple[float, float]:
        angle = math.radians(angle_degrees)
        return center + radius * scale * math.cos(angle), center + radius * scale * math.sin(angle)

    polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y in [point(values.get(q, 0.0), a) for q, a in zip(order, angles)])
    axes = []
    labels_svg = []
    for quadrant, angle in zip(order, angles):
        x, y = axis_point(angle)
        lx, ly = axis_point(angle, 1.26)
        anchor = "middle"
        if angle == 0:
            anchor = "start"
        elif angle == 180:
            anchor = "end"
        axes.append(f'<line x1="{center}" y1="{center}" x2="{x:.1f}" y2="{y:.1f}" stroke="#d1d5db" stroke-width="1"/>')
        labels_svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" dominant-baseline="middle" '
            f'font-size="12" fill="#374151">{quadrant} - {labels[quadrant]} ({values.get(quadrant, 0.0):.1f}%)</text>'
        )

    rings = []
    for pct in [25, 50, 75, 100]:
        r = radius * pct / 100
        rings.append(f'<circle cx="{center}" cy="{center}" r="{r:.1f}" fill="none" stroke="#e5e7eb" stroke-width="1"/>')

    dominant = profile.iloc[0]
    st.markdown(
        f"""
        <div style="display:flex; gap:24px; align-items:center; flex-wrap:wrap; margin:0.4rem 0 1rem;">
            <svg width="360" height="330" viewBox="0 0 360 330" role="img" aria-label="Radar estrategico TOWS">
                {''.join(rings)}
                {''.join(axes)}
                <polygon points="{polygon}" fill="#ef4444" fill-opacity="0.25" stroke="#ef4444" stroke-width="3"/>
                <circle cx="{center}" cy="{center}" r="3" fill="#111827"/>
                {''.join(labels_svg)}
            </svg>
            <div style="max-width:620px;">
                <div style="font-size:0.86rem; color:#6b7280;">Perfil estrategico predominante</div>
                <div style="font-size:1.35rem; font-weight:700; color:#111827; margin:0.15rem 0 0.45rem;">
                    {dominant["perfil_estrategico"]} ({float(dominant["participacao_percentual"]):.1f}%)
                </div>
                <div style="font-size:0.95rem; line-height:1.45; color:#374151;">
                    {dominant["leitura_executiva"]}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
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
    divergence_threshold_percent = st.slider(
        "Limite de divergencia",
        min_value=5,
        max_value=100,
        value=int(st.session_state.divergence_threshold_percent),
        step=5,
        format="%d%%",
        help=(
            "Escala unica em passos de 5%. Exemplo: 15% significa que uma celula sera marcada como divergente "
            "quando a diferenca entre maior e menor julgamento for igual ou superior a 0,15. O mesmo percentual "
            "tambem e usado no PDF para destacar desalinhamento geral."
        ),
    )
    threshold = divergence_threshold_percent / 100

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
        st.session_state.statistical_confidence[matrix_name] = result.statistical_confidence
        st.session_state.divergence_threshold_percent = int(divergence_threshold_percent)
        if matrix_name == TOWS_MATRIX_NAME:
            st.session_state.tows_strategies = result.tows_strategies
            st.session_state.strategic_profile = getattr(
                result,
                "strategic_profile",
                strategic_profile_from_tows(result.tows_strategies),
            )
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
        if matrix_name in st.session_state.statistical_confidence:
            st.markdown("#### Bloco estatistico de confianca")
            st.dataframe(st.session_state.statistical_confidence[matrix_name], use_container_width=True, hide_index=True)
        if matrix_name == TOWS_MATRIX_NAME and not st.session_state.strategic_profile.empty:
            st.markdown("#### Diagnostico estrategico TOWS")
            render_strategic_radar(st.session_state.strategic_profile)
            st.dataframe(st.session_state.strategic_profile, use_container_width=True, hide_index=True)
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
        statistical_confidence=st.session_state.statistical_confidence,
        divergence_rate_threshold=float(st.session_state.divergence_threshold_percent),
        tows_strategies=st.session_state.tows_strategies,
        strategic_profile=st.session_state.strategic_profile,
    )

    if public_mode:
        st.info("Modo publico: o PDF e entregue por download e nao e salvo no servidor.")

    st.download_button(
        "Baixar PDF consultivo",
        data=pdf_bytes(**pdf_kwargs),
        file_name=PDF_FILE_NAME,
        mime="application/pdf",
        type="primary",
    )


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide")
    init_state()
    public_mode = public_deployment_enabled()
    render_opening_cover()
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

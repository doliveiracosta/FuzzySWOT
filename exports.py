"""Export helpers for online and offline Fuzzy SWOT reports."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import BinaryIO
from xml.sax.saxutils import escape

import pandas as pd

from .constants import APP_NAME, APP_OWNER_LABEL


def write_pdf_report(
    output: str | BinaryIO,
    *,
    project: dict,
    evaluators: list[dict],
    strengths: list[str],
    weaknesses: list[str],
    opportunities: list[str],
    threats: list[str],
    rankings: dict[str, pd.DataFrame],
    consensus: dict[str, dict[str, pd.DataFrame]] | None = None,
    divergence_rate_threshold: float = 25.0,
    tows_strategies: pd.DataFrame,
    strategic_profile: pd.DataFrame | None = None,
) -> None:
    """Write a concise consultative PDF report."""

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm)
    story = []

    def paragraph(text: str, style: str = "Normal") -> Paragraph:
        return Paragraph(escape(str(text)), styles[style])

    def table(rows: list[list[object]], widths: list[float]) -> Table:
        wrapped_rows = [[paragraph(value, "Normal") for value in row] for row in rows]
        t = Table(wrapped_rows, colWidths=widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#424242")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return t

    def swot_table(title: str, items: list[str], width: float) -> Table:
        rows = [["#", title]]
        if items:
            rows.extend([[index, item] for index, item in enumerate(items, start=1)])
        else:
            rows.append(["-", "Nenhum item informado."])
        return table(rows, [1.2 * cm, width])

    def interpretation_table(rows: list[list[object]], widths: list[float], alert: bool = False) -> Table:
        wrapped_rows = [[paragraph(value, "Normal") for value in row] for row in rows]
        t = Table(wrapped_rows, colWidths=widths, repeatRows=1)
        body_background = colors.HexColor("#ffebee") if alert else colors.white
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b71c1c" if alert else "#2e7d32")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, 1), (-1, -1), body_background),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return t

    story.append(paragraph(APP_NAME, "Title"))
    story.append(paragraph("Relatorio consultivo de priorizacao estrategica por logica fuzzy", "Heading2"))
    story.append(paragraph(APP_OWNER_LABEL))
    story.append(Spacer(1, 10))
    story.append(paragraph(f"Projeto: {project.get('name', '')}"))
    story.append(paragraph(f"Organizacao: {project.get('organization', '')}"))
    story.append(paragraph(f"Responsavel: {project.get('responsible', '')}"))
    story.append(paragraph(f"Data de geracao: {datetime.now().strftime('%d/%m/%Y %H:%M')}"))
    story.append(Spacer(1, 12))

    story.append(paragraph("1. Inputs SWOT informados", "Heading1"))
    story.append(
        paragraph(
            "Os fatores abaixo foram informados como base da analise. Forcas e fraquezas representam o ambiente "
            "interno; oportunidades e ameacas representam o ambiente externo."
        )
    )
    story.append(Spacer(1, 6))
    story.append(swot_table("Forcas", strengths, 14.5 * cm))
    story.append(Spacer(1, 6))
    story.append(swot_table("Fraquezas", weaknesses, 14.5 * cm))
    story.append(Spacer(1, 6))
    story.append(swot_table("Oportunidades", opportunities, 14.5 * cm))
    story.append(Spacer(1, 6))
    story.append(swot_table("Ameacas", threats, 14.5 * cm))
    story.append(Spacer(1, 6))
    story.append(
        table(
            [
                ["Avaliadores", "Quantidade"],
                [", ".join(e.get("name", "") for e in evaluators) or "Nenhum avaliador informado.", len(evaluators)],
            ],
            [12.5 * cm, 3.2 * cm],
        )
    )
    story.append(Spacer(1, 12))

    story.append(paragraph("2. Rankings", "Heading1"))
    if rankings:
        for matrix_name, ranking in rankings.items():
            story.append(paragraph(matrix_name, "Heading2"))
            rows = [["Posicao", "Elemento", "Prioridade"]]
            for _, row in ranking.head(15).iterrows():
                rows.append([row["posicao"], row["elemento"], f"{float(row['prioridade_fuzzy']):.3f}"])
            story.append(table(rows, [2.0 * cm, 10.0 * cm, 3.0 * cm]))
            story.append(Spacer(1, 8))
    else:
        story.append(paragraph("Nenhum ranking gerado."))

    story.append(paragraph("3. Alinhamento estrategico entre avaliadores", "Heading1"))
    story.append(
        paragraph(
            "Esta secao compara os julgamentos dos avaliadores. Quanto menor a amplitude, maior o alinhamento "
            "entre pessoas ou areas. A amplitude representa a diferenca entre a maior e a menor nota atribuida "
            "ao mesmo relacionamento fuzzy. O limite definido pelo usuario foi aplicado como percentual."
        )
    )
    story.append(Spacer(1, 6))

    if consensus:
        for matrix_name, indicators in consensus.items():
            amplitude_df = indicators.get("amplitude")
            alert_df = indicators.get("alerta")
            if amplitude_df is None or alert_df is None or amplitude_df.empty:
                continue

            total_cells = int(amplitude_df.size)
            divergent_mask = alert_df.astype(str) == "Alta divergencia"
            divergent_cells = int(divergent_mask.values.sum())
            convergent_cells = total_cells - divergent_cells
            convergence_rate = (convergent_cells / total_cells * 100) if total_cells else 0.0
            divergence_rate = (divergent_cells / total_cells * 100) if total_cells else 0.0
            mean_amplitude = float(amplitude_df.astype(float).values.mean()) if total_cells else 0.0
            max_amplitude = float(amplitude_df.astype(float).values.max()) if total_cells else 0.0
            exceeds_threshold = divergence_rate > divergence_rate_threshold

            story.append(paragraph(matrix_name, "Heading2"))
            story.append(
                interpretation_table(
                    [
                        ["Leitura executiva", "Resultado"],
                        [
                            "Status do alinhamento",
                            (
                                f"ATENCAO: {divergence_rate:.1f}% dos cruzamentos ficaram divergentes, "
                                f"acima do limite definido de {divergence_rate_threshold:.1f}%."
                                if exceeds_threshold
                                else f"Alinhamento dentro do limite definido: {divergence_rate:.1f}% de divergencia "
                                f"para limite de {divergence_rate_threshold:.1f}%."
                            ),
                        ],
                    ],
                    [4.2 * cm, 11.5 * cm],
                    alert=exceeds_threshold,
                )
            )
            story.append(Spacer(1, 6))
            story.append(
                table(
                    [
                        ["Indicador", "Valor", "Interpretacao"],
                        [
                            "Convergencia geral",
                            f"{convergence_rate:.1f}%",
                            "Percentual de relacionamentos sem alta divergencia.",
                        ],
                        [
                            "Divergencia geral",
                            f"{divergence_rate:.1f}%",
                            f"Percentual comparado ao limite definido de {divergence_rate_threshold:.1f}%.",
                        ],
                        [
                            "Amplitude media",
                            f"{mean_amplitude:.3f}",
                            "Diferenca media entre maior e menor julgamento.",
                        ],
                        [
                            "Maior amplitude",
                            f"{max_amplitude:.3f}",
                            "Ponto de maior desalinhamento entre avaliadores.",
                        ],
                        [
                            "Pontos divergentes",
                            str(divergent_cells),
                            "Quantidade de cruzamentos marcados como alta divergencia.",
                        ],
                    ],
                    [4.2 * cm, 3.0 * cm, 8.5 * cm],
                )
            )
            story.append(Spacer(1, 6))

            divergent_rows = []
            for row_label in amplitude_df.index:
                for column_label in amplitude_df.columns:
                    if str(alert_df.loc[row_label, column_label]) == "Alta divergencia":
                        divergent_rows.append(
                            [
                                str(row_label),
                                str(column_label),
                                f"{float(amplitude_df.loc[row_label, column_label]):.3f}",
                                "Alta divergencia",
                            ]
                        )

            if divergent_rows:
                divergent_rows = sorted(divergent_rows, key=lambda item: float(item[2]), reverse=True)
                story.append(paragraph("Principais pontos para alinhamento", "Heading3"))
                story.append(
                    table(
                        [["Fator interno", "Fator externo", "Amplitude", "Status"]] + divergent_rows[:12],
                        [4.6 * cm, 4.6 * cm, 2.4 * cm, 3.2 * cm],
                    )
                )
                story.append(Spacer(1, 6))
            else:
                story.append(paragraph("Nao foram identificados pontos de alta divergencia nesta matriz."))
                story.append(Spacer(1, 6))
    else:
        story.append(paragraph("Nenhum indicador de consenso foi gerado. Consolide a matriz antes de exportar o PDF."))

    story.append(paragraph("4. Diagnostico estrategico TOWS", "Heading1"))
    if strategic_profile is not None and not strategic_profile.empty:
        dominant = strategic_profile.iloc[0]
        story.append(
            interpretation_table(
                [
                    ["Perfil predominante", "Leitura executiva"],
                    [
                        f"{dominant.get('perfil_estrategico', '')} "
                        f"({float(dominant.get('participacao_percentual', 0.0)):.1f}%)",
                        dominant.get("leitura_executiva", ""),
                    ],
                ],
                [4.5 * cm, 11.2 * cm],
                alert=str(dominant.get("quadrante", "")) == "WT",
            )
        )
        story.append(Spacer(1, 6))
        rows = [["Quadrante", "Perfil", "Participacao", "Prioridade media", "Status"]]
        for _, row in strategic_profile.iterrows():
            rows.append(
                [
                    row.get("quadrante", ""),
                    row.get("perfil_estrategico", ""),
                    f"{float(row.get('participacao_percentual', 0.0)):.1f}%",
                    f"{float(row.get('prioridade_media', 0.0)):.3f}",
                    row.get("status", ""),
                ]
            )
        story.append(table(rows, [1.8 * cm, 4.6 * cm, 2.5 * cm, 2.7 * cm, 2.7 * cm]))
        story.append(Spacer(1, 10))
    else:
        story.append(paragraph("Nenhum diagnostico estrategico TOWS foi gerado."))
        story.append(Spacer(1, 8))

    story.append(paragraph("5. Estrategias TOWS", "Heading1"))
    if not tows_strategies.empty:
        rows = [["Posicao", "Quadrante", "Fator interno", "Fator externo", "Prioridade"]]
        for _, row in tows_strategies.head(20).iterrows():
            rows.append(
                [
                    row["posicao"],
                    row["quadrante"],
                    row["fator_interno"],
                    row["fator_externo"],
                    f"{float(row['prioridade_fuzzy']):.3f}",
                ]
            )
        story.append(table(rows, [1.5 * cm, 1.8 * cm, 4.8 * cm, 4.8 * cm, 2.2 * cm]))
    else:
        story.append(paragraph("Nenhuma estrategia TOWS gerada."))

    doc.build(story)


def pdf_bytes(**kwargs) -> bytes:
    buffer = BytesIO()
    write_pdf_report(buffer, **kwargs)
    return buffer.getvalue()

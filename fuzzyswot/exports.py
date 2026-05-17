"""Export helpers for online and offline Fuzzy SWOT reports."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import BinaryIO
from xml.sax.saxutils import escape

import pandas as pd


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
    tows_strategies: pd.DataFrame,
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

    story.append(paragraph("FuzzySWOT Strategy Prioritizer", "Title"))
    story.append(paragraph("Relatorio consultivo de priorizacao estrategica por logica fuzzy", "Heading2"))
    story.append(Spacer(1, 10))
    story.append(paragraph(f"Projeto: {project.get('name', '')}"))
    story.append(paragraph(f"Organizacao: {project.get('organization', '')}"))
    story.append(paragraph(f"Responsavel: {project.get('responsible', '')}"))
    story.append(paragraph(f"Data de geracao: {datetime.now().strftime('%d/%m/%Y %H:%M')}"))
    story.append(Spacer(1, 12))

    story.append(paragraph("1. Estrutura SWOT", "Heading1"))
    story.append(
        table(
            [
                ["Grupo", "Quantidade", "Itens"],
                ["Forcas", len(strengths), ", ".join(strengths)],
                ["Fraquezas", len(weaknesses), ", ".join(weaknesses)],
                ["Oportunidades", len(opportunities), ", ".join(opportunities)],
                ["Ameacas", len(threats), ", ".join(threats)],
                ["Avaliadores", len(evaluators), ", ".join(e.get("name", "") for e in evaluators)],
            ],
            [3.2 * cm, 2.2 * cm, 10.5 * cm],
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

    story.append(paragraph("3. Estrategias TOWS", "Heading1"))
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

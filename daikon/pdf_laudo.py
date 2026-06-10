"""Geração do PDF do laudo com as imagens do exame."""
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, Image, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

from . import config


def _idade(nascimento: str) -> str:
    try:
        nasc = datetime.strptime(nascimento, "%Y-%m-%d")
        hoje = datetime.now()
        anos = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        return f"{anos} anos"
    except (ValueError, TypeError):
        return ""


def _data_br(iso: str) -> str:
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or ""


def gerar_pdf(estudo: dict, laudo: dict, paciente: dict, medico: dict,
              imagens_png: list, cfg: dict) -> str:
    """Monta o PDF e devolve o caminho do arquivo gerado."""
    os.makedirs(config.PDF_DIR, exist_ok=True)
    caminho = os.path.join(config.PDF_DIR, f"laudo_{estudo['id']}.pdf")

    doc = SimpleDocTemplate(
        caminho, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
        title=laudo.get("titulo") or "Laudo de Ultrassonografia",
    )

    estilos = getSampleStyleSheet()
    st_clinica = ParagraphStyle("clinica", parent=estilos["Title"],
                                fontSize=16, spaceAfter=0)
    st_sub = ParagraphStyle("sub", parent=estilos["Normal"], fontSize=9,
                            textColor=colors.grey, alignment=1)
    st_titulo = ParagraphStyle("titulo", parent=estilos["Heading1"],
                               fontSize=13, alignment=1, spaceBefore=10)
    st_corpo = ParagraphStyle("corpo", parent=estilos["Normal"], fontSize=10.5,
                              leading=15, spaceAfter=6)
    st_rodape = ParagraphStyle("rodape", parent=estilos["Normal"], fontSize=9,
                               alignment=1, textColor=colors.grey)

    historia = []
    historia.append(Paragraph(cfg.get("nome_clinica", ""), st_clinica))
    sub = " — ".join(x for x in (cfg.get("subtitulo_clinica"),
                                 cfg.get("endereco_clinica"),
                                 cfg.get("telefone_clinica")) if x)
    if sub:
        historia.append(Paragraph(sub, st_sub))
    historia.append(Spacer(1, 6))
    historia.append(HRFlowable(width="100%", color=colors.HexColor("#0e7490")))

    dados = [
        ["Paciente:", paciente.get("nome", ""),
         "Nascimento:", _data_br(paciente.get("nascimento", ""))],
        ["Idade:", _idade(paciente.get("nascimento", "")),
         "Sexo:", {"M": "Masculino", "F": "Feminino"}.get(paciente.get("sexo"), "")],
        ["Data do exame:", _data_br(estudo.get("data_exame") or estudo.get("recebido_em", "")),
         "Médico:", (medico or {}).get("nome", "")],
    ]
    tabela = Table(dados, colWidths=[2.8 * cm, 6.2 * cm, 2.8 * cm, 5.2 * cm])
    tabela.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
    ]))
    historia.append(Spacer(1, 8))
    historia.append(tabela)
    historia.append(HRFlowable(width="100%", color=colors.lightgrey))

    titulo = laudo.get("titulo") or estudo.get("descricao") or "Laudo de Ultrassonografia"
    historia.append(Paragraph(titulo.upper(), st_titulo))
    historia.append(Spacer(1, 4))

    for linha in (laudo.get("texto") or "").split("\n"):
        linha = linha.strip()
        if not linha:
            historia.append(Spacer(1, 6))
        else:
            seguro = linha.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            historia.append(Paragraph(seguro, st_corpo))

    if medico:
        historia.append(Spacer(1, 36))
        ass = f"{medico.get('nome', '')}"
        if medico.get("crm"):
            ass += f" — CRM {medico['crm']}"
        historia.append(Paragraph("_" * 45, ParagraphStyle(
            "linha", parent=estilos["Normal"], alignment=1)))
        historia.append(Paragraph(ass, ParagraphStyle(
            "ass", parent=estilos["Normal"], alignment=1, fontSize=10)))

    existentes = [p for p in imagens_png if p and os.path.exists(p)]
    if existentes:
        historia.append(Spacer(1, 14))
        historia.append(Paragraph("IMAGENS DO EXAME", st_titulo))
        historia.append(Spacer(1, 6))
        largura = 8.0 * cm
        linhas, atual = [], []
        for p in existentes:
            img = Image(p)
            proporcao = img.imageHeight / float(img.imageWidth)
            img.drawWidth = largura
            img.drawHeight = largura * proporcao
            atual.append(img)
            if len(atual) == 2:
                linhas.append(atual)
                atual = []
        if atual:
            atual.append("")
            linhas.append(atual)
        grade = Table(linhas, colWidths=[8.4 * cm, 8.4 * cm])
        grade.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        historia.append(grade)

    historia.append(Spacer(1, 14))
    historia.append(Paragraph(
        f"Laudo gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} — Daikon",
        st_rodape))

    doc.build(historia)
    return caminho

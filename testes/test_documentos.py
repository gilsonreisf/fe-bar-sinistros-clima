from datetime import date

import numpy as np
from pypdf import PdfReader

from dados_sinteticos.documentos import gerar_laudo_pdf, gerar_orcamento_pdf, moeda, texto_laudo

ITENS = [
    {"seq": 1, "codigo_item": "TEL-CER-MEDIO", "descricao": "Telha cerâmica colonial (padrão médio)", "unidade": "m²",
     "quantidade": 35, "valor_unitario": 55.0, "valor_total": 1925.0, "preco_referencia": 55.0, "preexistente": False},
    {"seq": 2, "codigo_item": "CAL-MEDIO", "descricao": "Calha de chapa galvanizada (padrão médio)", "unidade": "m",
     "quantidade": 10, "valor_unitario": 70.0, "valor_total": 700.0, "preco_referencia": 70.0, "preexistente": True},
]
AVISO = {"id_aviso": "AV-2026-000001", "municipio": "Seara", "data_aviso": "2026-09-29"}


def _texto(caminho):
    return "\n".join(p.extract_text() for p in PdfReader(caminho).pages)


def test_moeda_formato_brasileiro():
    assert moeda(1925) == "R$ 1.925,00"
    assert moeda(0.5) == "R$ 0,50"


def test_pdf_orcamento_texto_extraivel(tmp_path):
    """Foco de revisão 4: acentos e valores em formato brasileiro sobrevivem à extração."""
    for semente in (1, 2):  # os dois layouts
        caminho = tmp_path / f"orc_{semente}.pdf"
        gerar_orcamento_pdf(caminho, np.random.default_rng(semente), AVISO, ITENS,
                            {"razao_social": "Telhados São João Ltda.", "cnpj": "12.345.678/0001-90"}, "Maria da Conceição")
        texto = _texto(caminho)
        assert "Orçamento" in texto and "Telha cerâmica colonial" in texto
        assert "R$ 2.625,00" in texto  # total
        assert "Conceição" in texto


def test_laudo_preexistente_menciona_dano_anterior(tmp_path):
    texto = texto_laudo(np.random.default_rng(3), "granizo", date(2026, 10, 2), ITENS, "dano_preexistente")
    assert "anterior ao evento" in texto and "Calha" in texto
    caminho = tmp_path / "laudo.pdf"
    gerar_laudo_pdf(caminho, AVISO, texto)
    assert "anterior ao evento" in _texto(caminho)


def test_laudo_regular_nao_menciona_dano_anterior():
    texto = texto_laudo(np.random.default_rng(3), "vendaval", date(2026, 10, 2), ITENS, "legitimo_complexo")
    assert "Não foram observados indícios de danos anteriores" in texto

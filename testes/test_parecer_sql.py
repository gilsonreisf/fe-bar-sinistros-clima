"""Checagens estáticas da entrada do parecer: sem gabarito, mesmas chaves que o prompt v2 cita, mesma chave de preço."""
import re
from pathlib import Path

from parecer.prompts import PROMPT_V2

SQL = (Path(__file__).resolve().parents[1] / "src/pipeline/silver_parecer.sql").read_text(encoding="utf-8")


def test_entrada_do_parecer_nao_le_o_gabarito_nem_o_rotulo():
    for proibida in ("gabarito", "restrito", "padrao", "decisao_esperada", "valor_devido"):
        assert proibida not in SQL, proibida


def test_chaves_citadas_no_prompt_existem_na_entrada():
    """As regras do prompt v2 citam caminhos do JSON (ex.: evidencia_climatica.forca); todos precisam existir no SQL."""
    citados = set(re.findall(r"\b(apolice|evidencia_climatica|documentos)\.([a-z_]+)", PROMPT_V2))
    assert citados, "o prompt v2 deveria citar campos da entrada"
    for grupo, campo in citados:
        assert f"'{grupo}'" in SQL and f"'{campo}'" in SQL, f"{grupo}.{campo}"


def test_mesma_chave_de_preco_das_outras_mvs():
    assert "lower(regexp_replace(trim(descricao), '\\\\s+', ' '))" in SQL
    assert "tipo_documento = 'laudo'" in SQL and "d.legivel" in SQL

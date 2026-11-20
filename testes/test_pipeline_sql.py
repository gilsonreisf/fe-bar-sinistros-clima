"""Checagens estáticas do pipeline: sem nome fixo e só com placeholders que o bundle fornece (foco de revisão 4)."""
import re
from pathlib import Path

from dados_sinteticos import config
from regras.clima import RAIO_ESTACAO_KM

RAIZ = Path(__file__).resolve().parents[1]
PIPELINE = RAIZ / "src/pipeline"
RECURSO = RAIZ / "recursos/pipeline_sinistros.yml"
CHAVES = {"catalogo", "schema_bronze", "schema_silver", "volume_arquivos"}


def _arquivos():
    return sorted(PIPELINE.glob("*.sql")) + sorted(PIPELINE.glob("*.py"))


def test_pipeline_tem_bronze_e_silver():
    nomes = {p.name for p in _arquivos()}
    assert {"bronze.py", "silver_avisos.sql", "silver_documentos.sql", "silver_cadastros.sql", "silver_clima.py",
            "silver_sinistros.sql"} <= nomes


def test_configuracao_do_pipeline_tem_todas_as_chaves():
    yml = RECURSO.read_text(encoding="utf-8")
    for chave in CHAVES:
        assert re.search(rf"^\s+{chave}: ", yml, re.M), chave
    assert "--editable ${workspace.file_path}" in yml


def test_sql_usa_so_chaves_da_configuracao():
    for arq in PIPELINE.glob("*.sql"):
        usados = set(re.findall(r"\$\{([a-z_]+)\}", arq.read_text(encoding="utf-8")))
        assert usados and usados <= CHAVES, (arq.name, usados - CHAVES)


def test_python_le_so_chaves_da_configuracao():
    for arq in PIPELINE.glob("*.py"):
        usados = set(re.findall(r'spark\.conf\.get\("([a-z_]+)"\)', arq.read_text(encoding="utf-8")))
        assert usados and usados <= CHAVES, (arq.name, usados - CHAVES)


def test_sem_nome_de_catalogo_fixo():
    for arq in _arquivos() + [RECURSO]:
        texto = arq.read_text(encoding="utf-8")
        assert "fe_bar_sinistros_catalog" not in texto and "sinistros_clima." not in texto, arq.name


def test_regras_do_sql_batem_com_as_regras_python():
    texto = (PIPELINE / "silver_sinistros.sql").read_text(encoding="utf-8")
    for causa, cobertura in config.CAUSA_COBERTURA.items():
        if causa != cobertura:
            assert f"WHEN '{causa}' THEN '{cobertura}'" in texto, causa
    assert f"distancia_estacao_km <= {RAIO_ESTACAO_KM:g}" in texto

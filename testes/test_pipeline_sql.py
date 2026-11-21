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
    # As regras chegam como wheel do Volume (o serverless do pipeline não lê arquivos do workspace fora das fontes; D-019)
    assert "- --no-deps ${var.pacote_python}" in yml
    assert re.search(r"^\s+root_path: \.\./src/pipeline$", yml, re.M) and "development: true" in yml
    assert "--editable" not in yml and "/teste/" not in yml


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


def _sql(nome: str) -> str:
    return (PIPELINE / nome).read_text(encoding="utf-8")


def test_falhas_de_documento_viram_flag():
    """Revisão #1 (spec 10.3): extração falha, preço sem conferência e PDF ausente não podem passar como 'limpos'."""
    texto = _sql("silver_sinistros.sql")
    for flag in ("extracao_falhou", "preco_nao_conferido", "documento_ausente"):
        assert f"'{flag}'" in texto, flag


def test_causa_desconhecida_vira_alerta_e_expectation():
    """Revisão #2: o domínio de causas do SQL é o mesmo das regras Python."""
    from regras.clima import VARIAVEIS_POR_CAUSA

    avisos, sinistros = _sql("silver_avisos.sql"), _sql("silver_sinistros.sql")
    assert "CONSTRAINT causa_conhecida" in avisos and "'causa_desconhecida'" in sinistros
    for causa in VARIAVEIS_POR_CAUSA:
        assert f"'{causa}'" in avisos, causa


def test_avisos_guardam_o_que_nao_coube_no_esquema_e_alertas_tratam_nulo():
    """Revisão #6: campo com tipo errado vai para _rescued_data (e é medido), e NULL não escapa dos alertas."""
    assert "rescuedDataColumn" in _sql("bronze.py")
    assert "_rescued_data IS NULL" in _sql("silver_avisos.sql")
    sinistros = _sql("silver_sinistros.sql")
    assert "coalesce(valor_reclamado > 0, false)" in sinistros and "coalesce(data_ocorrencia <= data_aviso, false)" in sinistros


def test_tabelas_com_ia_protegidas_contra_full_refresh():
    """Um full refresh acidental não pode refazer o OCR e a extração de todos os PDFs (custo)."""
    assert _sql("silver_documentos.sql").count("'pipelines.reset.allowed' = 'false'") == 2

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
            "silver_sinistros.sql", "silver_historico.sql"} <= nomes


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


def _colunas_do_select_final(sql: str) -> str:
    return sql[sql.rindex("SELECT"):]


def test_historico_e_evento_tem_as_mesmas_colunas_de_entrada():
    from regras.features import COLUNAS_CLIMA_BRUTO, COLUNAS_ENTRADA
    for nome in ("silver_historico.sql", "silver_sinistros.sql"):
        final = _colunas_do_select_final(_sql(nome))
        for coluna in COLUNAS_ENTRADA + COLUNAS_CLIMA_BRUTO:
            assert re.search(rf"\b{coluna}\b", final), (nome, coluna)


def test_historico_nao_le_colunas_que_vazam_o_rotulo():
    texto = _sql("silver_historico.sql")
    for proibida in ("decisao_final", "valor_pago", "motivo_decisao", "padrao", "gabarito"):
        assert proibida not in texto, proibida
    assert not re.search(r"\bpreexistente\b", texto)  # só menciona_preexistente (o laudo), nunca o item marcado


def test_participacao_do_prestador_e_point_in_time_e_suavizada_nos_dois_lados():
    """Janela estritamente anterior ao dia do aviso e proporção suavizada (empírica bayesiana), igual nos dois lados:
    no início do evento a janela é pequena e 1 aviso anterior parecia concentração (lote 1)."""
    from regras.features import JANELA_PRESTADOR_DIAS, PSEUDO_AVISOS_JANELA, PSEUDO_AVISOS_PRESTADOR
    formula = (f"(coalesce(avisos_prestador, 0) + {PSEUDO_AVISOS_PRESTADOR}) / "
               f"(coalesce(avisos_janela, 0) + {PSEUDO_AVISOS_JANELA})")
    for nome in ("silver_historico.sql", "silver_sinistros.sql"):
        texto = _sql(nome)
        assert f"date_sub(k.data_aviso, {JANELA_PRESTADOR_DIAS})" in texto and "< k.data_aviso" in texto, nome
        assert formula in texto, nome


def test_desvio_de_preco_usa_a_mesma_chave_nos_dois_lados():
    chave = "lower(regexp_replace(trim(descricao), '\\\\s+', ' '))"
    assert chave in _sql("silver_documentos.sql") and chave in _sql("silver_historico.sql")

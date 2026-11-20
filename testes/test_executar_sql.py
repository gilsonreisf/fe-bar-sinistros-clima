from executar_sql import dividir_comandos


def test_divide_por_ponto_e_virgula_no_fim_da_linha_e_ignora_comentarios():
    sql = """-- comentário
CREATE SCHEMA IF NOT EXISTS a.b
  COMMENT 'x; y';
CREATE VOLUME IF NOT EXISTS a.b.c;

SELECT 1
"""
    assert dividir_comandos(sql) == [
        "CREATE SCHEMA IF NOT EXISTS a.b\n  COMMENT 'x; y'",
        "CREATE VOLUME IF NOT EXISTS a.b.c",
        "SELECT 1",
    ]


def test_aplica_variaveis_nos_placeholders():
    from executar_sql import aplicar_variaveis

    sql = "CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_bronze};"
    assert aplicar_variaveis(sql, {"catalogo": "c", "schema_bronze": "b"}) == "CREATE SCHEMA IF NOT EXISTS c.b;"


def test_placeholder_desconhecido_falha():
    import pytest
    from executar_sql import aplicar_variaveis

    with pytest.raises(ValueError, match="schema_prata"):
        aplicar_variaveis("SELECT * FROM ${catalogo}.${schema_prata}.t", {"catalogo": "c"})


def test_sql_do_projeto_usa_apenas_placeholders_conhecidos():
    """Nenhum nome de catálogo fixo nos .sql: todo placeholder precisa ter valor no ambiente."""
    from pathlib import Path

    from ambiente import carregar_ambiente
    from executar_sql import aplicar_variaveis

    arquivos = sorted((Path(__file__).resolve().parents[1] / "src/governanca").glob("*.sql"))
    assert arquivos
    for arquivo in arquivos:
        sql = aplicar_variaveis(arquivo.read_text(encoding="utf-8"), carregar_ambiente({}).variaveis_sql())
        assert "${" not in sql and "sinistros_catalog" not in sql, arquivo.name

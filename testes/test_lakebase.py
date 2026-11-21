"""Schema `operacao` do Lakebase: concorrência, idempotência e requisitos do Lakehouse Sync (checagens estáticas; o
comportamento real é testado ponta a ponta por scripts/testar_lakebase.py)."""
from lakebase.operacao import DDL, consultas
from parecer.esquema import RECOMENDACOES


def test_ddl_tem_replica_identity_e_restricoes():
    texto = "\n".join(DDL)
    for tabela in ("atribuicoes", "decisoes_regulador", "reanalises"):
        assert f"ALTER TABLE operacao.{tabela} REPLICA IDENTITY FULL" in texto, tabela
    assert "id_decisao UUID PRIMARY KEY" in texto and "id_aviso TEXT PRIMARY KEY" in texto
    for r in RECOMENDACOES:
        assert f"'{r}'" in texto
    assert "valor_aprovado >= 0" in texto


def test_assumir_proximo_e_atomico_e_decisao_idempotente():
    q = consultas("gold.sinistros_analisados_lb")
    assert "ON CONFLICT (id_aviso) DO NOTHING" in q["assumir_proximo"] and "pg_try_advisory_xact_lock" in q["assumir_proximo"]
    assert "NOT f.fast_track" in q["assumir_proximo"] and "ORDER BY f.prioridade DESC" in q["assumir_proximo"]
    assert "ON CONFLICT DO NOTHING" in q["registrar_decisao"]  # id_decisao repetido ou 2ª decisão do mesmo aviso
    assert "%(decisao)s::text = f.recomendacao_ia" in q["registrar_decisao"]  # concordância calculada no banco


def test_lock_so_depois_dos_candidatos_ordenados():
    # revisão das fases 4 a 8 (#3): o lock fica fora da consulta ordenada, senão trava todos os candidatos
    q = consultas("gold.sinistros_analisados_lb")["assumir_proximo"]
    assert "AS MATERIALIZED" in q
    ordenado, depois = q.split("), escolhido AS (")
    assert "ORDER BY f.prioridade DESC" in ordenado and "pg_try_advisory_xact_lock" not in ordenado
    assert "pg_try_advisory_xact_lock" in depois and "ORDER BY" not in depois.split("INSERT")[0]


def test_decisao_so_de_quem_esta_com_o_caso_e_na_mesma_instrucao():
    from lakebase.operacao import DDL

    q = consultas("gold.sinistros_analisados_lb")["registrar_decisao"]
    assert "a.regulador = %(regulador)s AND a.status = 'em_analise'" in q
    assert "UPDATE operacao.atribuicoes" in q  # concluir a atribuição na mesma instrução (atômico)
    assert "<> 'recusar' OR" in q and "<= f.valor_reclamado" in q
    assert any("UNIQUE INDEX" in d and "(id_aviso)" in d for d in DDL)

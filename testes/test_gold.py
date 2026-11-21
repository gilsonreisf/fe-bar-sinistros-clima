"""Gold: DDL sem nomes fixos, seleção incremental (sem pagar parecer duas vezes) e geração tolerante a falhas."""
import pandas as pd
import pytest

from gold.processar import gerar_pareceres, linhas_gold, selecionar_para_analise
from gold.visoes import COLUNAS_GOLD, ddl_gold


def test_ddl_parametrizado_com_cdf_e_visoes():
    ddl = ddl_gold("cat", "sil", "gol")
    texto = "\n".join(ddl)
    assert "cat.gol.sinistros_analisados" in texto and "delta.enableChangeDataFeed" in texto
    for visao in ("fila_regulacao", "kpis_evento", "sinistro_detalhe"):
        assert f"CREATE OR REPLACE VIEW cat.gol.{visao}" in texto
    assert "sinistros_clima" not in texto and "fe_bar" not in texto and "gabarito" not in texto
    for coluna in ("id_aviso", "score_suspeita", "recomendacao_ia", "fast_track", "bloqueios_fast_track", "prioridade"):
        assert coluna in COLUNAS_GOLD


def test_selecao_incremental_nao_repete_parecer_ok_e_respeita_tentativas():
    silver = pd.DataFrame({"id_aviso": ["A", "B", "C", "D", "E"]})
    gold = pd.DataFrame({"id_aviso": ["B", "C", "D", "E"], "status_parecer": ["ok", "pendente", "invalido", "pendente"],
                         "tentativas_parecer": [1, 1, 2, 3]})
    assert selecionar_para_analise(silver, gold, max_tentativas=3) == ["A", "C", "D"]
    assert selecionar_para_analise(silver, gold.iloc[0:0], max_tentativas=3) == ["A", "B", "C", "D", "E"]


def test_gerar_pareceres_nao_derruba_o_lote_quando_um_falha():
    def gerar(entrada):
        if entrada["id"] == 3:
            raise RuntimeError("cota excedida")
        return {"status_parecer": "ok", "recomendacao": "pagar_integral", "id": entrada["id"]}

    saida = gerar_pareceres([(f"A{i}", {"id": i}) for i in range(5)], gerar, paralelo=3)
    assert [saida[f"A{i}"]["status_parecer"] for i in range(5)] == ["ok", "ok", "ok", "pendente", "ok"]
    assert "cota excedida" in saida["A3"]["erros"][0] and saida["A3"]["recomendacao"] == "investigar"


def test_linhas_gold_juntam_score_parecer_fast_track_e_prioridade():
    base = pd.DataFrame({"id_aviso": ["A", "B"], "lote": [2, 2], "data_aviso": pd.to_datetime(["2026-09-01", "2026-09-01"]),
                         "municipio": ["X", "Y"], "causa_declarada": ["granizo", "vendaval"], "valor_reclamado": [3000.0, 30000.0],
                         "cobertura_valida": [True, True], "forca_evidencia_climatica": ["forte", "forte"],
                         "alertas_qualidade": [[], []], "flags_documento": [[], []]})
    scores = pd.DataFrame({"score_suspeita": [0.01, 0.9], "fatores_suspeita": ["", "Preço acima da tabela de referência"]},
                          index=base.index)
    pareceres = {"A": {"recomendacao": "pagar_integral", "valor_sugerido": 2500.0, "motivos": ["ok"], "clausulas": ["CG-3.1"],
                       "itens_excluidos": [], "confianca": 0.9, "status_parecer": "ok", "versao_prompt": "2", "trace_id": "t1",
                       "erros": []},
                 "B": {"recomendacao": "pagar_parcial", "valor_sugerido": 20000.0, "motivos": ["acima"], "clausulas": ["CG-7.1"],
                       "itens_excluidos": [], "confianca": 0.8, "status_parecer": "ok", "versao_prompt": "2", "trace_id": "t2",
                       "erros": []}}
    g = linhas_gold(base, scores, pareceres, llm="llm", versao_modelo="3", agora=pd.Timestamp("2026-09-02"),
                    tentativas_anteriores={"B": 1}, hoje=pd.Timestamp("2026-09-02"))
    assert list(g.columns) == COLUNAS_GOLD
    a, b = g.set_index("id_aviso").loc["A"], g.set_index("id_aviso").loc["B"]
    assert a.fast_track and not b.fast_track and "score_suspeita" in b.bloqueios_fast_track
    assert b.prioridade > a.prioridade and a.tentativas_parecer == 1 and b.tentativas_parecer == 2
    assert a.recomendacao_ia == "pagar_integral" and a.llm == "llm" and a.versao_modelo == "3"


def test_pesos_invalidos_falham_cedo():
    with pytest.raises(ValueError):
        linhas_gold(pd.DataFrame(columns=["id_aviso"]), pd.DataFrame(), {}, "llm", "3", pd.Timestamp("2026-09-01"), {},
                    pesos={"suspeita": 1.0, "valor": 1.0, "espera": 1.0})


def test_cpf_mascarado_no_detalhe_e_marcado_como_dado_pessoal():
    ddl = ddl_gold("cat", "sil", "gol", grupo_cpf="grupo_x")
    texto = "\n".join(ddl)
    assert "CREATE OR REPLACE FUNCTION cat.gol.mascarar_cpf" in texto and "is_account_group_member('grupo_x')" in texto
    assert "s.* EXCEPT (cpf_segurado), cat.gol.mascarar_cpf(s.cpf_segurado) AS cpf_segurado" in texto
    assert ddl[-1] == "SET TAG ON COLUMN cat.gol.sinistro_detalhe.cpf_segurado classificacao_lgpd = dado_pessoal"
    # a função vem antes das visões que a usam
    assert ddl.index(next(c for c in ddl if "FUNCTION" in c)) < ddl.index(next(c for c in ddl if "sinistro_detalhe" in c))


def test_reaplicar_regras_atualiza_fast_track_e_prioridade_sem_llm():
    from gold.processar import reaplicar_regras

    gold = pd.DataFrame({"id_aviso": ["A", "B"], "score_suspeita": [0.05, 0.05], "recomendacao_ia": ["pagar_integral"] * 2,
                         "status_parecer": ["ok", "ok"]})
    silver = pd.DataFrame({"id_aviso": ["A", "B"], "data_aviso": ["2026-08-01", "2026-08-10"],
                           "valor_reclamado": [3000.0, 3000.0], "cobertura_valida": [True, True],
                           "forca_evidencia_climatica": ["forte", "forte"], "alertas_qualidade": [[], []],
                           "flags_documento": [[], ["valor_divergente"]], "menciona_dano_anterior": [False, False]})
    r = reaplicar_regras(gold, silver, hoje=pd.Timestamp("2026-08-10")).set_index("id_aviso")
    assert bool(r.loc["A", "fast_track"]) and not bool(r.loc["B", "fast_track"])
    assert r.loc["B", "bloqueios_fast_track"] == ["valor_divergente"]
    assert r.loc["A", "prioridade"] > r.loc["B", "prioridade"]  # esperou mais

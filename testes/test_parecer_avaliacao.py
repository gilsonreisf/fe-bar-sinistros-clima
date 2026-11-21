"""Avaliação do parecer (spec 6.4): expectativas por padrão, amostra estratificada, métricas de código e registro
idempotente dos prompts."""
import pandas as pd
import pytest

from parecer.avaliacao import (FATOS_POR_PADRAO, amostra_estratificada, cita_clausula, expectativas, json_valido,
                               padrao_identificado, recomendacao_correta, registrar_prompt_se_mudou,
                               valor_dentro_tolerancia)

PADROES = ["legitimo_simples", "legitimo_complexo", "sem_evento_climatico", "orcamento_inflado", "sem_cobertura",
           "apolice_recente", "dano_preexistente", "prestador_concentrado"]


@pytest.mark.parametrize("padrao", PADROES)
def test_expectativas_de_todos_os_padroes(padrao):
    e = expectativas(padrao, "investigar", 100.0, "vendaval_granizo")
    assert e["recomendacao_esperada"] == "investigar" and e["padrao"] == padrao and e["valor_devido"] == 100.0
    assert "A recomendação é investigar" in e["expected_facts"] and set(FATOS_POR_PADRAO[padrao]) <= set(e["expected_facts"])
    assert e["clausula_esperada"].startswith("CG-")


def test_clausula_esperada_do_legitimo_e_a_da_cobertura():
    assert expectativas("legitimo_simples", "pagar_integral", 1.0, "alagamento")["clausula_esperada"] == "CG-3.2"
    assert expectativas("sem_cobertura", "recusar", 0.0, "vendaval_granizo")["clausula_esperada"] == "CG-2.1"


def test_amostra_estratificada_limita_por_grupo_e_e_estavel():
    df = pd.DataFrame({"id": range(100), "padrao": ["a"] * 90 + ["b"] * 10})
    a1, a2 = amostra_estratificada(df, "padrao", 25, seed=7), amostra_estratificada(df, "padrao", 25, seed=7)
    assert a1["padrao"].value_counts().to_dict() == {"a": 25, "b": 10} and a1["id"].tolist() == a2["id"].tolist()


def test_metricas_de_codigo():
    saida = {"recomendacao": "pagar_parcial", "status_parecer": "ok", "clausulas": ["CG-7.1", "CG-4.1"],
             "motivos": ["Orçamento acima da tabela de referência"]}
    esperado = expectativas("orcamento_inflado", "pagar_parcial", 1000.0, "vendaval_granizo")
    assert recomendacao_correta(saida, esperado) and json_valido(saida) and cita_clausula(saida, esperado)
    assert padrao_identificado(saida, esperado)
    assert not padrao_identificado({**saida, "motivos": ["Tudo certo"]}, esperado)
    assert not json_valido({**saida, "status_parecer": "invalido"})
    legitimo = expectativas("legitimo_simples", "pagar_integral", 1.0, "vendaval_granizo")
    assert padrao_identificado({"recomendacao": "pagar_integral", "motivos": []}, legitimo)


def test_valor_dentro_da_tolerancia():
    assert valor_dentro_tolerancia(1050.0, 1000.0) and not valor_dentro_tolerancia(1200.0, 1000.0)
    assert valor_dentro_tolerancia(0.0, 0.0) and valor_dentro_tolerancia(0.05, 0.0) and not valor_dentro_tolerancia(50.0, 0.0)


def test_registrar_prompt_so_quando_o_texto_muda():
    existentes = {1: "texto v1", 2: "texto v2"}
    registrados = []

    def carregar(versao):
        return existentes.get(versao)

    def registrar():
        registrados.append(1)
        existentes[len(existentes) + 1] = "texto novo"
        return len(existentes)

    assert registrar_prompt_se_mudou(carregar, registrar, "texto v2") == (2, False) and registrados == []
    assert registrar_prompt_se_mudou(carregar, registrar, "texto novo") == (3, True) and registrados == [1]

"""Núcleo do parecer prévio: esquema, valor calculado em código e geração com LLM simulado (spec 6.2 e 10.3)."""
import json

import mlflow
import pytest

from parecer.clausulas import CLAUSULAS
from parecer.esquema import BASES_VALOR, RECOMENDACOES, validar_parecer
from parecer.gerar import gerar_parecer, renderizar_prompt
from parecer.prompts import PROMPTS
from parecer.valor import calcular_valor, valores_de_referencia


@pytest.fixture(autouse=True)
def _mlflow_local(tmp_path, monkeypatch):
    """Traces dos testes vão para um sqlite temporário (nunca para a raiz do repo nem para o workspace)."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/mlflow.db")


def _entrada(**kw):
    e = {
        "aviso": {"id_aviso": "AV-1", "causa_declarada": "granizo", "valor_reclamado": 10000.0, "data_ocorrencia": "2026-08-29"},
        "apolice": {"cobertura_valida": True, "cobertura_necessaria": "vendaval_granizo", "lmi": 50000.0, "franquia": 1000.0,
                    "dias_desde_contratacao": 200},
        "evidencia_climatica": {"forca": "forte", "fonte": "defesa_civil"},
        "documentos": {"valor_orcamento": 10000.0, "desvio_preco_pct": 0.5, "menciona_dano_anterior": True,
                       "laudo": "Observa-se desgaste nos seguintes itens: Telha cerâmica.",
                       "itens": [{"descricao": "telha ceramica (padrão popular)", "quantidade": 10, "valor_unitario": 600.0,
                                  "valor_total": 6000.0, "preco_referencia": 400.0},
                                 {"descricao": "Calha de PVC", "quantidade": 4, "valor_unitario": 1000.0,
                                  "valor_total": 4000.0, "preco_referencia": None}]},
    }
    for chave, valor in kw.items():
        e[chave] = valor
    return e


def _resposta(**kw):
    r = {"recomendacao": "pagar_integral", "base_valor": "reclamado", "itens_excluidos": [],
         "motivos": ["Cobertura contratada e evento confirmado pela Defesa Civil"], "clausulas": ["CG-3.1", "CG-4.1"],
         "confianca": 0.9}
    return json.dumps(r | kw, ensure_ascii=False)


# --- esquema ---------------------------------------------------------------------------------------------------------

def test_dominios():
    assert RECOMENDACOES == ("pagar_integral", "pagar_parcial", "recusar", "investigar")
    assert BASES_VALOR == ("reclamado", "tabela_referencia", "itens_validos", "zero")


def test_json_valido_com_cerca_e_texto_antes():
    parecer, avisos = validar_parecer("Segue o parecer:\n```json\n" + _resposta() + "\n```")
    assert parecer["recomendacao"] == "pagar_integral" and parecer["confianca"] == 0.9 and avisos == []


@pytest.mark.parametrize("ruim, trecho", [
    (_resposta(recomendacao="pagar"), "recomendacao"),
    (_resposta(base_valor="metade"), "base_valor"),
    (_resposta(confianca=1.5), "confianca"),
    (_resposta(motivos=[]), "motivos"),
    (_resposta(base_valor="itens_validos", itens_excluidos=[]), "itens_excluidos"),
    ("não é json", "JSON"),
    (json.dumps({"recomendacao": "investigar"}), "base_valor"),
])
def test_json_invalido_explica_o_erro(ruim, trecho):
    parecer, erros = validar_parecer(ruim)
    assert parecer is None and any(trecho in e for e in erros), erros


def test_clausula_desconhecida_e_removida_com_aviso():
    parecer, avisos = validar_parecer(_resposta(clausulas=["CG-3.1", "XYZ-9"]))
    assert parecer["clausulas"] == ["CG-3.1"] and any("XYZ-9" in a for a in avisos)


def test_clausulas_tem_os_codigos_usados_nas_regras():
    for codigo in ("CG-2.1", "CG-2.4", "CG-3.1", "CG-3.2", "CG-3.3", "CG-4.1", "CG-4.2", "CG-5.1", "CG-6.1", "CG-7.1", "CG-8.1"):
        assert codigo in CLAUSULAS


# --- valor (calculado em código, nunca pelo LLM) --------------------------------------------------------------------

def test_valores_de_referencia():
    v = valores_de_referencia(_entrada())
    assert v["valor_liquido_reclamado"] == 9000.0
    assert v["valor_liquido_tabela"] == 10 * 400 + 4000 - 1000  # item sem par na tabela entra pelo valor do orçamento
    assert v["excede_lmi"] is False


def test_lmi_e_franquia_limitam_o_valor():
    e = _entrada(apolice={"lmi": 5000.0, "franquia": 1000.0, "cobertura_valida": True})
    assert calcular_valor(e, "reclamado", []) == 5000.0 and valores_de_referencia(e)["excede_lmi"] is True
    pequeno = _entrada(aviso={"valor_reclamado": 800.0}, apolice={"lmi": 5000.0, "franquia": 1000.0})
    assert calcular_valor(pequeno, "reclamado", []) == 0.0


def test_itens_validos_exclui_por_nome_base_sem_acento_e_sem_caixa():
    assert calcular_valor(_entrada(), "itens_validos", ["Telha cerâmica"]) == 4000 - 1000


def test_zero_e_dados_ausentes():
    assert calcular_valor(_entrada(), "zero", []) == 0.0
    minima = {"aviso": {"valor_reclamado": 3000.0}}
    assert calcular_valor(minima, "reclamado", []) == 3000.0 and calcular_valor(minima, "itens_validos", ["x"]) == 3000.0
    assert valores_de_referencia(minima)["valor_liquido_tabela"] == 3000.0


# --- prompts e geração ------------------------------------------------------------------------------------------------

def test_prompt_renderizado_tem_entrada_valores_e_clausulas():
    for template in PROMPTS.values():
        texto = renderizar_prompt(template, _entrada())
        assert "{{" not in texto and "valor_liquido_tabela" in texto and "CG-5.1" in texto and "AV-1" in texto


def test_gerar_parecer_valido_na_primeira():
    chamadas = []
    p = gerar_parecer(_entrada(), PROMPTS["v2"], lambda prompt: chamadas.append(prompt) or _resposta(), "3")
    assert p["status_parecer"] == "ok" and p["valor_sugerido"] == 9000.0 and len(chamadas) == 1
    assert p["versao_prompt"] == "3" and p["recomendacao"] == "pagar_integral" and p["trace_id"]


def test_gerar_parecer_tenta_de_novo_e_depois_desiste():
    respostas = iter(["lixo", _resposta(recomendacao="pagar_parcial", base_valor="tabela_referencia")])
    p = gerar_parecer(_entrada(), PROMPTS["v2"], lambda _: next(respostas), "1")
    assert p["status_parecer"] == "ok" and p["valor_sugerido"] == 7000.0
    ruim = gerar_parecer(_entrada(), PROMPTS["v2"], lambda _: "lixo", "1")
    assert ruim["status_parecer"] == "invalido" and ruim["recomendacao"] == "investigar" and ruim["valor_sugerido"] == 0.0
    assert ruim["erros"]


def test_llm_indisponivel_vira_pendente_sem_propagar():
    def falha(_):
        raise TimeoutError("endpoint frio")
    p = gerar_parecer(_entrada(), PROMPTS["v1"], falha, "1")
    assert p["status_parecer"] == "pendente" and p["recomendacao"] == "investigar" and "endpoint frio" in p["erros"][0]


def test_recusa_nunca_paga_e_entrada_minima_funciona():
    p = gerar_parecer({"aviso": {"valor_reclamado": 2000.0}}, PROMPTS["v1"],
                      lambda _: _resposta(recomendacao="recusar", base_valor="reclamado"), "1")
    assert p["recomendacao"] == "recusar" and p["valor_sugerido"] == 0.0

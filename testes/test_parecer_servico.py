"""Modelo servido do parecer (models from code) e publicação do endpoint (AI Gateway, tracing, scale-to-zero)."""
import json
from pathlib import Path

import mlflow
import pandas as pd
import pytest
from databricks.sdk.errors import NotFound

import parecer
from parecer.endpoint import config_endpoint, publicar_endpoint
from parecer.gerar import juntar_score
from parecer.modelo_pyfunc import assinatura_parecer
from parecer.prompts import PROMPTS


@pytest.fixture(autouse=True)
def _mlflow_local(tmp_path, monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/mlflow.db")


def test_config_do_endpoint_tem_gateway_tracing_e_scale_to_zero():
    c = config_endpoint("cat.ml.parecer_sinistro", 4, "123", "cat", "ml")
    entidade = c["config"]["served_entities"][0]
    assert entidade["entity_name"] == "cat.ml.parecer_sinistro" and entidade["entity_version"] == "4"
    assert entidade["workload_size"] == "Small" and entidade["scale_to_zero_enabled"] is True
    assert entidade["environment_vars"] == {"ENABLE_MLFLOW_TRACING": "true", "MLFLOW_EXPERIMENT_ID": "123"}
    gateway = c["ai_gateway"]
    assert gateway["inference_table_config"] == {"enabled": True, "catalog_name": "cat", "schema_name": "ml",
                                                 "table_name_prefix": "parecer"}
    assert gateway["usage_tracking_config"] == {"enabled": True}


def test_publicar_cria_quando_nao_existe_e_atualiza_quando_existe():
    chamadas = []

    def api_nova(metodo, caminho, corpo=None):
        chamadas.append((metodo, caminho))
        if metodo == "GET":
            raise NotFound("não existe")
        return {}

    corpo = config_endpoint("m", 1, "1", "c", "s")
    assert publicar_endpoint(api_nova, "ep", corpo) == "criado"
    assert chamadas == [("GET", "/api/2.0/serving-endpoints/ep"), ("POST", "/api/2.0/serving-endpoints")]
    chamadas.clear()
    assert publicar_endpoint(lambda m, c, b=None: chamadas.append((m, c)) or {}, "ep", corpo) == "atualizado"
    assert ("PUT", "/api/2.0/serving-endpoints/ep/config") in chamadas
    assert ("PUT", "/api/2.0/serving-endpoints/ep/ai-gateway") in chamadas


def test_juntar_score_so_quando_ha_score():
    assert "modelo_suspeita" not in juntar_score({"aviso": {}}, None, None)
    assert "modelo_suspeita" not in juntar_score({"aviso": {}}, float("nan"), "")
    e = juntar_score({"aviso": {}}, 0.7, "Preço acima da tabela de referência")
    assert e["modelo_suspeita"] == {"score_suspeita": 0.7, "fatores_suspeita": "Preço acima da tabela de referência"}


def test_modelo_servido_gera_parecer_por_linha(tmp_path, monkeypatch):
    import parecer.gerar as gerar

    resposta = json.dumps({"recomendacao": "pagar_integral", "base_valor": "reclamado", "itens_excluidos": [],
                           "motivos": ["Cobertura contratada"], "clausulas": ["CG-3.1"], "confianca": 0.9})
    monkeypatch.setattr(gerar, "chamar_llm_databricks", lambda *a, **k: (lambda prompt: resposta))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"endpoint_llm": "llm", "versao_prompt": "2", "template": PROMPTS["v2"],
                                  "nome_prompt": "cat.ml.prompt_parecer"}), encoding="utf-8")
    destino = tmp_path / "modelo"
    mlflow.pyfunc.save_model(path=str(destino), python_model=str(Path(parecer.__file__).with_name("modelo_pyfunc.py")),
                             artifacts={"config": str(config)}, code_paths=[str(Path(parecer.__file__).parent)],
                             signature=assinatura_parecer())
    modelo = mlflow.pyfunc.load_model(str(destino))
    entrada = pd.DataFrame({"entrada_json": [json.dumps({"aviso": {"valor_reclamado": 3000.0},
                                                         "apolice": {"franquia": 500.0}})] * 2,
                            "score_suspeita": [0.05, None], "fatores_suspeita": ["", None]})
    saida = modelo.predict(entrada)
    assert len(saida) == 2 and (saida["status_parecer"] == "ok").all() and (saida["valor_sugerido"] == 2500.0).all()
    assert json.loads(saida["motivos"].iloc[0]) == ["Cobertura contratada"] and saida["versao_prompt"].iloc[0] == "2"
    assert set(saida.columns) == {"recomendacao", "valor_sugerido", "motivos", "clausulas", "itens_excluidos",
                                  "confianca", "status_parecer", "versao_prompt", "trace_id", "erros"}

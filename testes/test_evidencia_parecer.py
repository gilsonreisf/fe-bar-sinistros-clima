import json

import pandas as pd

from evidencia_parecer import renderizar_evidencia_parecer
from testar_endpoint_parecer import renderizar_teste_endpoint


def test_evidencia_da_avaliacao_compara_v1_e_v2():
    resultado = {"dataset": "cat.ml.ds", "casos": 10, "prompt": "cat.ml.prompt_parecer", "versoes_prompt": {"v1": 1, "v2": 2},
                 "prompt_producao": 2, "promovido": True, "modelo": "cat.ml.parecer_sinistro", "versao_modelo": "1",
                 "endpoint": "ep", "acao_endpoint": "criado", "runs": {"v1": "r1", "v2": "r2"}, "run_registro": "r3",
                 "metricas": {"v1": {"recomendacao_correta/mean": 0.6, "correctness/mean": 0.7},
                              "v2": {"recomendacao_correta/mean": 0.9, "correctness/mean": 0.8}}}
    md = renderizar_evidencia_parecer("2026-11-21 02:00", resultado, {"v2": pd.DataFrame({"padrao": ["x"], "acuracia": [1.0]})},
                                      pd.DataFrame({"id_aviso": ["AV-1"], "esperado": ["pagar_integral"], "obtido": ["investigar"]}),
                                      {"aliases": ["producao"]})
    assert "| `recomendacao_correta/mean` | recomendação igual à do gabarito | 0.600 | 0.900 |" in md
    assert "Alias `producao` → **v2**" in md and "AV-1" in md and "CG-2.4" in md


def test_evidencia_do_endpoint_mostra_parecer_trace_e_gateway():
    caso = {"id_aviso": "AV-1", "padrao": "legitimo_simples", "esperado": "pagar_integral", "recomendacao": "pagar_integral",
            "valor_sugerido": 1784.84, "confianca": 0.9, "status_parecer": "ok", "versao_prompt": "2",
            "clausulas": json.dumps(["CG-3.1"]), "motivos": json.dumps(["Cobertura contratada"]), "latencia_s": 6.2,
            "trace_id": "tr-1"}
    md = renderizar_teste_endpoint("agora", "ep", {"ready": "READY", "config_update": "NOT_UPDATING", "entidade": "m",
                                                   "versao": "1", "scale_to_zero": True},
                                   {"inference_table_config": {"enabled": True}, "usage_tracking_config": {"enabled": True}},
                                   [caso], {"tr-1": True}, ["parecer_payload"])
    assert "**pagar_integral**" in md and "R$ 1.784,84" in md and "encontrado no experimento: True" in md
    assert "`parecer_payload`" in md and "Cobertura contratada" in md

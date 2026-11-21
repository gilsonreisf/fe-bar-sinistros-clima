import pandas as pd

from evidencia_modelo import renderizar_evidencia_modelo, tabela_markdown


def test_tabela_markdown_formata_numeros_e_nulos():
    md = tabela_markdown(pd.DataFrame({"padrao": ["a", None], "score": [0.123456, 1.0]}))
    assert md.splitlines()[0] == "| padrao | score |" and "| a | 0.1235 |" in md and "|  | 1.0 |" in md


def test_evidencia_tem_as_secoes_e_compara_registrado_com_ablacao():
    md = renderizar_evidencia_modelo(
        quando="2026-11-21 01:00",
        resultado={"modelo": "cat.ml.modelo_suspeita", "versao": "1", "alias": "champion", "run_id": "abc"},
        metricas={"teste_auc": 0.99, "evento_auc": 0.97, "treino_auc": 1.0},
        metricas_ablacao={"teste_auc": 0.98, "evento_auc": 0.80},
        parametros={"num_leaves": "15", "features": "a,b"},
        entradas=[("features_treino", "treino", "cat.ml.features_treino", "0")],
        artefatos=["curva_roc.png", "modelo/MLmodel"],
        tabelas={"Teste por padrão": pd.DataFrame({"padrao": ["x"], "n": [3]})},
        versao={"aliases": ["champion"], "tags": {"teste_auc": "0.9900"}, "status": "READY"},
        experimento="/Shared/sinistros_clima/dev/modelo_suspeita",
    )
    for trecho in ("# Modelo de suspeita", "## Resultado do job", "## Métricas", "| teste_auc | 0.99 | 0.98 |",
                   "| evento_auc | 0.97 | 0.8 |", "## Dados de entrada (log_input)", "cat.ml.features_treino",
                   "## Artefatos", "curva_roc.png", "### Teste por padrão", "champion", "## Parâmetros"):
        assert trecho in md, trecho
    assert "@" not in md and "/Users/" not in md

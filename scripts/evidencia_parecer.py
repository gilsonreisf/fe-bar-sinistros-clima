"""Gera evidencias/05-avaliacao-genai.md a partir de uma execução do job de avaliação do parecer: v1 × v2 (métricas
de código e juízes), acurácia por padrão, divergências do v2, portão do prompt, modelo registrado e endpoint.

Uso: uv run python scripts/evidencia_parecer.py <task_run_id> [evidencias/05-avaliacao-genai.md]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from evidencia_modelo import tabela_markdown

RAIZ = Path(__file__).resolve().parents[1]
DESCRICAO = {
    "recomendacao_correta/mean": "recomendação igual à do gabarito",
    "json_valido/mean": "JSON válido na primeira ou na segunda tentativa",
    "padrao_identificado/mean": "motivos citam o fato que caracteriza o padrão",
    "cita_clausula/mean": "cita a cláusula esperada",
    "correctness/mean": "juiz LLM: fatos esperados presentes",
    "diretrizes_parecer/mean": "juiz LLM: diretrizes (português formal, sem recusa sem evidência, tom)",
    "valor_dentro_tolerancia_pagamentos": "valor sugerido a ±10% do devido (casos com pagamento esperado)",
    "casos_pagamento_esperado": "casos com pagamento esperado",
}


def renderizar_evidencia_parecer(quando: str, resultado: dict, por_padrao: dict[str, pd.DataFrame],
                                 erros_v2: pd.DataFrame, modelo: dict) -> str:
    m = resultado["metricas"]
    chaves = sorted({k for v in m.values() for k in v}, key=lambda k: (k not in DESCRICAO, k))
    p = ["# Parecer prévio por IA: avaliação com MLflow (v1 × v2), portão e registro", "",
         f"Gerado em {quando} com `uv run python scripts/evidencia_parecer.py <task_run_id>`, a partir do job "
         "`job_avaliacao_parecer` (notebook `notebooks/avaliacao_parecer.py`; saídas em "
         "`notebooks/saidas/avaliacao_parecer.ipynb`).", "",
         "## Configuração", "",
         f"- Dataset de avaliação (MLflow Evaluation Dataset no UC): `{resultado['dataset']}`, {resultado['casos']} casos "
         "estratificados por padrão dos lotes de validação do evento.",
         f"- Prompt versionado no UC (tabela Delta; o Prompt Registry não está habilitado no workspace, D-022): `{resultado['prompt']}`. Versões avaliadas: "
         + ", ".join(f"{c} = v{v}" for c, v in resultado["versoes_prompt"].items())
         + f". Alias `producao` → **v{resultado['prompt_producao']}** (promovido nesta execução: {resultado['promovido']}).",
         f"- Modelo registrado: `{resultado['modelo']}` versão **{resultado['versao_modelo']}** (aliases: "
         f"{', '.join(modelo.get('aliases', [])) or 'nenhum'}), com o prompt de produção congelado.",
         f"- Endpoint: `{resultado['endpoint']}` ({resultado['acao_endpoint']}), com AI Gateway (inference table e usage "
         "tracking) e tracing; teste em `evidencias/05-endpoint-parecer.md`.",
         "- Runs do MLflow: " + ", ".join(f"{c} `{r}`" for c, r in resultado["runs"].items())
         + f", registro `{resultado['run_registro']}`.", "",
         "## Métricas (v1 × v2)", "",
         "| métrica | o que mede | " + " | ".join(m) + " |", "|---|---|" + "---|" * len(m)]
    for k in chaves:
        p.append(f"| `{k}` | {DESCRICAO.get(k, '')} | " + " | ".join(
            "" if m[c].get(k) is None else f"{m[c][k]:.3f}" for c in m) + " |")
    for c, tabela in por_padrao.items():
        p += ["", f"## Acurácia da recomendação por padrão ({c})", "", tabela_markdown(tabela)]
    p += ["", "## Divergências do prompt v2 em relação ao gabarito", "",
          "Apólices com menos de 30 dias vão para `investigar` pela cláusula CG-2.4 (análise de contratação recente), "
          "mesmo quando o gabarito diz que o sinistro é legítimo: é uma divergência de política, não de leitura.", "",
          tabela_markdown(erros_v2) if len(erros_v2) else "Nenhuma divergência."]
    return "\n".join(p) + "\n"


def renderizar_comparacao_llm(quando: str, metricas: dict[str, dict]) -> str:
    """Mesmo dataset e mesmo prompt (v2), LLMs diferentes: base da escolha do LLM do lote (D-023)."""
    llms = list(metricas)
    chaves = sorted({k for m in metricas.values() for k in m}, key=lambda k: (k not in DESCRICAO, k))
    p = ["# Comparação de LLMs no parecer prévio (mesmo dataset, prompt v2)", "",
         f"Gerado em {quando} com `uv run python scripts/evidencia_parecer.py comparacao <task_run_id>=<llm> ...`, a "
         "partir do job de avaliação no modo `publicar=nao` (avalia sem mexer no prompt, no modelo nem no endpoint).", "",
         "| métrica | o que mede | " + " | ".join(f"`{l}`" for l in llms) + " |", "|---|---|" + "---|" * len(llms)]
    for k in chaves:
        p.append(f"| `{k}` | {DESCRICAO.get(k, '')} | "
                 + " | ".join("" if metricas[l].get(k) is None else f"{metricas[l][k]:.3f}" for l in llms) + " |")
    return "\n".join(p) + "\n"


def main(task_run_id: str, saida: str = "evidencias/05-avaliacao-genai.md") -> None:
    import mlflow
    from databricks.sdk import WorkspaceClient
    from mlflow import MlflowClient

    perfil = os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")
    w = WorkspaceClient(profile=perfil)
    resultado = json.loads(w.jobs.get_run_output(int(task_run_id)).notebook_output.result)
    mlflow.set_tracking_uri(f"databricks://{perfil}")
    cliente = MlflowClient(tracking_uri=f"databricks://{perfil}", registry_uri=f"databricks-uc://{perfil}")
    por_padrao, erros_v2 = {}, pd.DataFrame()
    with tempfile.TemporaryDirectory() as tmp:
        for chave, run_id in resultado["runs"].items():
            conteudo = json.loads(Path(cliente.download_artifacts(run_id, "acuracia_por_padrao.json", tmp)).read_text())
            por_padrao[chave] = pd.DataFrame(conteudo["data"], columns=conteudo["columns"])
        conteudo = json.loads(Path(cliente.download_artifacts(resultado["runs"]["v2"], "erros.json", tmp)).read_text())
        erros_v2 = pd.DataFrame(conteudo["data"], columns=conteudo["columns"])
    colunas = [c for c in ("id_aviso", "padrao", "esperado", "obtido", "dias_desde_contratacao", "motivos") if c in erros_v2]
    mv = cliente.get_model_version(resultado["modelo"], resultado["versao_modelo"])
    md = renderizar_evidencia_parecer(datetime.now().strftime("%Y-%m-%d %H:%M"), resultado, por_padrao,
                                      erros_v2[colunas], {"aliases": list(mv.aliases or [])})
    (RAIZ / saida).write_text(md, encoding="utf-8")
    print(f"{saida} gerado ({len(md)} caracteres)")


def comparacao(*pares: str, saida: str = "evidencias/05-comparacao-llm.md") -> None:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    metricas = {}
    for par in pares:
        run, llm = par.split("=", 1)
        metricas[llm] = json.loads(w.jobs.get_run_output(int(run)).notebook_output.result)["metricas"]["v2"]
    md = renderizar_comparacao_llm(datetime.now().strftime("%Y-%m-%d %H:%M"), metricas)
    (RAIZ / saida).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    if sys.argv[1:2] == ["comparacao"]:
        comparacao(*sys.argv[2:])
    else:
        main(*sys.argv[1:])

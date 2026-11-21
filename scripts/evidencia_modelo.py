"""Gera evidencias/04-ml.md a partir de uma execução do job de treino: resultado do notebook, run do MLflow
(métricas, parâmetros, log_input, artefatos, tabelas por padrão), ablação e versão do modelo no Unity Catalog.

Uso: uv run python scripts/evidencia_modelo.py <task_run_id> [evidencias/04-ml.md]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
TABELAS = {"por_padrao_teste.json": "Teste (out–dez/2025) por padrão",
           "por_padrao_evento_lote1.json": "Evento 2026 (lote 1) por padrão"}
_IGNORAR_METRICA = ("_n", "_n_suspeitos")


def _valor(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return f"{round(v, 4)}"
    return str(v)


def tabela_markdown(df: pd.DataFrame) -> str:
    linhas = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * len(df.columns)]
    linhas += ["| " + " | ".join(_valor(v) for v in linha) + " |" for linha in df.itertuples(index=False)]
    return "\n".join(linhas)


def renderizar_evidencia_modelo(quando: str, resultado: dict, metricas: dict, metricas_ablacao: dict, parametros: dict,
                                entradas: list[tuple[str, str, str, str]], artefatos: list[str],
                                tabelas: dict[str, pd.DataFrame], versao: dict, experimento: str) -> str:
    p = [f"# Modelo de suspeita: treino, validação e registro",
         "",
         f"Gerado em {quando} com `uv run python scripts/evidencia_modelo.py <task_run_id>`, a partir da execução do job "
         f"`job_treino_modelo` (notebook `notebooks/treino_modelo_suspeita.py`; saídas em "
         f"`notebooks/saidas/treino_modelo_suspeita.ipynb`). Experimento MLflow: `{experimento}`.",
         "",
         "## Resultado do job",
         "",
         f"- Modelo no Unity Catalog: `{resultado.get('modelo')}`, versão **{resultado.get('versao')}**, alias "
         f"**`{resultado.get('alias')}`** (aliases atuais da versão: {', '.join(versao.get('aliases', [])) or 'nenhum'}; "
         f"status {versao.get('status', '?')}).",
         f"- Run do MLflow: `{resultado.get('run_id')}`.",
         "",
         "## Métricas",
         "",
         "Prefixos: `treino_` (jan–set/2025), `teste_` (out–dez/2025, split temporal) e `evento_` (avisos do evento de "
         "2026 já publicados, pontuados pelo modelo carregado do UC). O limiar 0,2 é o corte do fast track (spec 6.3).",
         "",
         "| métrica | modelo registrado | ablação com clima bruto |",
         "|---|---|---|"]
    for nome in sorted(metricas):
        if nome.endswith(_IGNORAR_METRICA):
            continue
        p.append(f"| {nome} | {_valor(metricas[nome])} | {_valor(metricas_ablacao.get(nome))} |")
    contagens = {k: int(v) for k, v in metricas.items() if k.endswith(_IGNORAR_METRICA)}
    p += ["", "Tamanhos: " + ", ".join(f"{k} = {v}" for k, v in sorted(contagens.items())) + ".", ""]
    for titulo, tabela in tabelas.items():
        p += [f"### {titulo}", "", tabela_markdown(tabela), ""]
    p += ["## Dados de entrada (log_input)", "", "| nome | contexto | tabela | versão Delta |", "|---|---|---|---|"]
    p += [f"| {n} | {c} | `{t}` | {v} |" for n, c, t, v in entradas]
    p += ["", "## Artefatos do run", ""] + [f"- `{a}`" for a in sorted(artefatos)]
    p += ["", "## Tags da versão do modelo", "", "| tag | valor |", "|---|---|"]
    p += [f"| {k} | {v} |" for k, v in sorted(versao.get("tags", {}).items())]
    p += ["", "## Parâmetros", "", "| parâmetro | valor |", "|---|---|"]
    p += [f"| {k} | {v} |" for k, v in sorted(parametros.items())]
    return "\n".join(p) + "\n"


def _artefatos(cliente, run_id: str, caminho: str | None = None) -> list[str]:
    nomes = []
    for a in cliente.list_artifacts(run_id, caminho):
        nomes += _artefatos(cliente, run_id, a.path) if a.is_dir else [a.path]
    return nomes


def main(task_run_id: str, saida: str = "evidencias/04-ml.md") -> None:
    import mlflow
    from databricks.sdk import WorkspaceClient
    from mlflow import MlflowClient

    perfil = os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")
    w = WorkspaceClient(profile=perfil)
    resultado = json.loads(w.jobs.get_run_output(int(task_run_id)).notebook_output.result)
    mlflow.set_tracking_uri(f"databricks://{perfil}")
    cliente = MlflowClient(tracking_uri=f"databricks://{perfil}", registry_uri=f"databricks-uc://{perfil}")
    run = cliente.get_run(resultado["run_id"])
    filhos = cliente.search_runs([run.info.experiment_id], f"tags.mlflow.parentRunId = '{run.info.run_id}'")
    ablacao = filhos[0].data.metrics if filhos else {}
    entradas = []
    for d in run.inputs.dataset_inputs:
        fonte = json.loads(d.dataset.source or "{}")
        contexto = next((t.value for t in d.tags if t.key == "mlflow.data.context"), "")
        entradas.append((d.dataset.name, contexto, fonte.get("delta_table_name", fonte.get("path", "")),
                         str(fonte.get("delta_table_version", ""))))
    tabelas = {}
    with tempfile.TemporaryDirectory() as tmp:
        for arquivo, titulo in TABELAS.items():
            caminho = Path(cliente.download_artifacts(run.info.run_id, arquivo, tmp))
            conteudo = json.loads(caminho.read_text(encoding="utf-8"))
            tabelas[titulo] = pd.DataFrame(conteudo["data"], columns=conteudo["columns"])
    mv = cliente.get_model_version(resultado["modelo"], resultado["versao"])
    aliases = [a for a in (mv.aliases or [])]
    experimento = cliente.get_experiment(run.info.experiment_id).name
    md = renderizar_evidencia_modelo(
        quando=datetime.now().strftime("%Y-%m-%d %H:%M"), resultado=resultado, metricas=run.data.metrics,
        metricas_ablacao=ablacao, parametros=run.data.params, entradas=entradas, artefatos=_artefatos(cliente, run.info.run_id),
        tabelas=tabelas, versao={"aliases": aliases, "tags": mv.tags, "status": mv.status}, experimento=experimento)
    (RAIZ / saida).write_text(md, encoding="utf-8")
    print(f"{saida} gerado ({len(md)} caracteres)")


if __name__ == "__main__":
    main(*sys.argv[1:])

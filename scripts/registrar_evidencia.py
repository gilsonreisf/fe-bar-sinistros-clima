"""Executa um .sql no SQL Warehouse e grava as saídas em Markdown, como evidência em texto (o avaliador só lê texto).

Uso: uv run python scripts/registrar_evidencia.py <arquivo.sql> <saida.md> "<título>"
Placeholders: os do módulo `ambiente` (catálogo e schemas) mais ${workspace_id}.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from databricks.sdk import WorkspaceClient

from ambiente import carregar_ambiente
from executar_sql import aplicar_variaveis, dividir_comandos, executar

RAIZ = Path(__file__).resolve().parents[1]


def renderizar_evidencia(titulo: str, origem: str, quando: str, resultados: list[tuple[str, list[str], list[list]]]) -> str:
    partes = [f"# {titulo}", "", f"Executado em {quando} com `uv run python scripts/registrar_evidencia.py {origem}` "
              "(catálogo e schemas lidos do `.env`; D-016).", ""]
    for i, (comando, colunas, linhas) in enumerate(resultados, start=1):
        partes += [f"## Consulta {i}", "", "```sql", comando, "```", ""]
        if not colunas:
            partes += ["(comando sem resultado tabular)", ""]
            continue
        partes += ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
        partes += ["| " + " | ".join("" if v is None else str(v) for v in linha) + " |" for linha in linhas]
        partes.append("")
    return "\n".join(partes)


def main(arquivo_sql: str, saida_md: str, titulo: str) -> None:
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    variaveis = carregar_ambiente().variaveis_sql() | {"workspace_id": str(w.get_workspace_id())}
    sql = aplicar_variaveis((RAIZ / arquivo_sql).read_text(encoding="utf-8"), variaveis)
    resultados = []
    for comando in dividir_comandos(sql):
        colunas, linhas = executar(w, os.environ["FE_BAR_WAREHOUSE_ID"], comando)
        resultados.append((comando, colunas, linhas))
    md = renderizar_evidencia(titulo, arquivo_sql, datetime.now().strftime("%Y-%m-%d %H:%M"), resultados)
    destino = RAIZ / saida_md
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main(*sys.argv[1:4])

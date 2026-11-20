"""Executa um arquivo .sql no SQL Warehouse, um comando por vez, e imprime os resultados.

Uso: uv run python scripts/executar_sql.py <arquivo.sql>
Requer as variáveis DATABRICKS_CONFIG_PROFILE e FE_BAR_WAREHOUSE_ID (veja .env.exemplo).
Os placeholders ${catalogo} e ${schema_<camada>} são preenchidos pelo módulo `ambiente`
(FE_BAR_CATALOGO e FE_BAR_PREFIXO_SCHEMA).
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

from ambiente import carregar_ambiente

_PLACEHOLDER = re.compile(r"\$\{([a-z_]+)\}")


def aplicar_variaveis(sql: str, variaveis: dict[str, str]) -> str:
    """Troca ${nome} pelo valor correspondente. Levanta ValueError se algum placeholder não tiver valor."""
    faltando = sorted({n for n in _PLACEHOLDER.findall(sql) if n not in variaveis})
    if faltando:
        raise ValueError(f"placeholders sem valor: {', '.join(faltando)}")
    return _PLACEHOLDER.sub(lambda m: variaveis[m.group(1)], sql)


def dividir_comandos(sql: str) -> list[str]:
    """Divide o SQL em comandos terminados por ';' no fim da linha, ignorando linhas de comentário."""
    comandos, atual = [], []
    for linha in sql.splitlines():
        if linha.strip().startswith("--"):
            continue
        atual.append(linha)
        if linha.rstrip().endswith(";"):
            comando = "\n".join(atual).strip().rstrip(";").strip()
            if comando:
                comandos.append(comando)
            atual = []
    resto = "\n".join(atual).strip()
    if resto:
        comandos.append(resto)
    return comandos


def executar(w: WorkspaceClient, warehouse_id: str, comando: str) -> tuple[list[str], list[list[str]]]:
    """Executa um comando e devolve (colunas, linhas). Levanta RuntimeError se falhar."""
    r = w.statement_execution.execute_statement(statement=comando, warehouse_id=warehouse_id, wait_timeout="50s")
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        erro = r.status.error.message if r.status.error else ""
        raise RuntimeError(f"{r.status.state.value}: {erro}\n--- comando ---\n{comando[:500]}")
    colunas = [c.name for c in r.manifest.schema.columns] if r.manifest and r.manifest.schema and r.manifest.schema.columns else []
    linhas = r.result.data_array if r.result and r.result.data_array else []
    return colunas, linhas


def main(caminho: str) -> None:
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    warehouse_id = os.environ["FE_BAR_WAREHOUSE_ID"]
    sql = aplicar_variaveis(Path(caminho).read_text(encoding="utf-8"), carregar_ambiente().variaveis_sql())
    for i, comando in enumerate(dividir_comandos(sql), start=1):
        print(f"[{i}] {comando.splitlines()[0][:100]}")
        colunas, linhas = executar(w, warehouse_id, comando)
        if colunas:
            print("    " + " | ".join(colunas))
            for linha in linhas[:50]:
                print("    " + " | ".join("" if v is None else str(v) for v in linha))


if __name__ == "__main__":
    main(sys.argv[1])

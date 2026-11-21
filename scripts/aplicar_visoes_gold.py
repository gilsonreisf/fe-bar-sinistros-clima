"""Recria a função de máscara do CPF e as visões gold (as mesmas do job do evento, `gold.visoes.ddl_gold`) no SQL
Warehouse, sem esperar a próxima execução do job. Idempotente; a tabela `sinistros_analisados` não é tocada.

Uso: uv run python scripts/aplicar_visoes_gold.py
"""
from __future__ import annotations

import os

from databricks.sdk import WorkspaceClient

from ambiente import carregar_ambiente
from executar_sql import executar
from gold.visoes import ddl_gold


def main() -> None:
    w, amb = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")), carregar_ambiente()
    for comando in ddl_gold(amb.catalogo, amb.schema("silver"), amb.schema("gold"))[1:]:
        executar(w, os.environ["FE_BAR_WAREHOUSE_ID"], comando)
        print("ok:", comando.splitlines()[0][:100])


if __name__ == "__main__":
    main()

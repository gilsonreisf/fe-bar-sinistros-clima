"""Provisiona o Lakebase do projeto, de forma idempotente (spec 7.1 e 11; o DAB ainda não cobre synced tables nem o
Lakehouse Sync). Pode rodar quantas vezes quiser: só cria o que falta.

1. Projeto Lakebase (Postgres 17, branch `production`, compute `primary` com scale-to-zero).
2. Schema `operacao` (atribuições, decisões do regulador, reanálises) com REPLICA IDENTITY FULL.
3. Synced table do gold → Postgres (`gold.sinistros_analisados` → `<schema gold>.sinistros_analisados_lb`, TRIGGERED).
   No FEVM não há CREATE CATALOG (D-016), então o destino é o catálogo do projeto, e não um catálogo do Lakebase.
4. Lakehouse Sync (Beta): schema `operacao` do Postgres → `<catálogo>.operacional` (tabelas `lb_*_history`, SCD2).

Uso: uv run python scripts/provisionar_lakebase.py
Variáveis: as do .env, mais FE_BAR_LAKEBASE_PROJETO (padrão: sinistros-clima).
"""
from __future__ import annotations

import os
import time

from ambiente import carregar_ambiente

PROJETO_PADRAO = "sinistros-clima"


def nomes(amb, projeto: str) -> dict[str, str]:
    branch = f"projects/{projeto}/branches/production"
    return {"projeto": f"projects/{projeto}", "branch": branch, "endpoint": f"{branch}/endpoints/primary",
            "database": f"{branch}/databases/databricks-postgres",
            "origem_fila": f"{amb.catalogo}.{amb.schema('gold')}.sinistros_analisados",
            "synced_fila": f"{amb.catalogo}.{amb.schema('gold')}.sinistros_analisados_lb",
            "cdf_id": "operacao_para_uc"}


def _existe(chamada) -> bool:
    from databricks.sdk.errors import NotFound

    try:
        chamada()
        return True
    except NotFound:
        return False


def main() -> None:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.postgres import (CdfConfig, NewPipelineSpec, Project, ProjectSpec, SyncedTable,
                                                 SyncedTableSyncedTableSpec,
                                                 SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy as Politica)

    from lakebase.operacao import DDL, conectar

    w, amb = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")), carregar_ambiente()
    projeto = os.environ.get("FE_BAR_LAKEBASE_PROJETO", PROJETO_PADRAO)
    n = nomes(amb, projeto)
    if not _existe(lambda: w.postgres.get_project(name=n["projeto"])):
        w.postgres.create_project(project=Project(spec=ProjectSpec(display_name="Sinistros clima - operacao da regulacao")),
                                  project_id=projeto).wait()
        print(f"projeto criado: {n['projeto']}")
    else:
        print(f"projeto já existe: {n['projeto']}")
    with conectar(w, projeto) as conexao:
        for comando in DDL:
            conexao.execute(comando)
        conexao.commit()
    print("schema operacao conferido (DDL idempotente)")
    if not _existe(lambda: w.postgres.get_synced_table(name=f"synced_tables/{n['synced_fila']}")):
        w.postgres.create_synced_table(synced_table=SyncedTable(spec=SyncedTableSyncedTableSpec(
            source_table_full_name=n["origem_fila"], primary_key_columns=["id_aviso"], scheduling_policy=Politica.TRIGGERED,
            branch=n["branch"], postgres_database="databricks_postgres", create_database_objects_if_missing=True,
            new_pipeline_spec=NewPipelineSpec(storage_catalog=amb.catalogo, storage_schema=amb.schema("ml")))),
            synced_table_id=n["synced_fila"])
        print(f"synced table criada: {n['synced_fila']}")
    else:
        print(f"synced table já existe: {n['synced_fila']}")
    if not _existe(lambda: w.postgres.get_cdf_config(name=f"{n['database']}/cdf-configs/{n['cdf_id']}")):
        w.postgres.create_cdf_config(parent=n["database"], cdf_config_id=n["cdf_id"], cdf_config=CdfConfig(
            catalog=amb.catalogo, schema=amb.schema("operacional"), postgres_schema="operacao"))
        print(f"Lakehouse Sync criado: operacao → {amb.catalogo}.{amb.schema('operacional')}")
    else:
        print("Lakehouse Sync já existe")
    for _ in range(30):
        st = w.postgres.get_synced_table(name=f"synced_tables/{n['synced_fila']}").status
        if str(getattr(st, "detailed_state", "")).endswith("ONLINE") or "ONLINE" in str(st):
            break
        time.sleep(10)
    print(f"estado da synced table: {getattr(st, 'detailed_state', st)}")


if __name__ == "__main__":
    main()

"""Permissões mínimas do service principal do app (D-025/D-026), idempotente. Rode uma vez depois do primeiro deploy.

- Unity Catalog: leitura do schema gold (camada de consumo: visões e metric views, com o CPF mascarado), da entrada do
  parecer na silver (sem dado pessoal) e EXECUTE na função de máscara do CPF. Nada de bronze, de outras tabelas da
  silver, de gabarito nem de escrita.
- Lakebase (Postgres): leitura da synced table do gold e leitura/escrita só nas tabelas do schema `operacao`.
  O papel do service principal é criado pela plataforma no deploy (recurso `postgres` do app).

Uso: uv run python scripts/permissoes_app.py <nome do app>   (ex.: sinistros-clima-dev)
"""
from __future__ import annotations

import os
import sys

from ambiente import carregar_ambiente

def comandos_uc(amb, sp: str) -> list[str]:
    c, g, s, o = amb.catalogo, amb.schema("gold"), amb.schema("silver"), amb.schema("operacional")
    p = f"`{sp}`"
    return ([f"GRANT USE CATALOG ON CATALOG {c} TO {p}"]
            + [f"GRANT USE SCHEMA ON SCHEMA {c}.{x} TO {p}" for x in (g, s, o)]
            # SELECT no schema gold (camada de consumo), e não visão a visão: o job e os scripts recriam as visões e as
            # metric views com CREATE OR REPLACE, o que apaga grants por objeto (medido no deploy do app)
            + [f"GRANT SELECT ON SCHEMA {c}.{g} TO {p}"]
            + [f"GRANT SELECT ON TABLE {c}.{s}.entrada_parecer TO {p}",
               f"GRANT SELECT ON TABLE {c}.{o}.lb_decisoes_regulador_history TO {p}",
               f"GRANT EXECUTE ON FUNCTION {c}.{g}.mascarar_cpf TO {p}"])


def comandos_pg(amb, sp: str) -> list[str]:
    papel, gold = f'"{sp}"', amb.schema("gold")
    return [f"GRANT USAGE ON SCHEMA operacao TO {papel}",
            f"GRANT SELECT, INSERT, UPDATE ON operacao.atribuicoes TO {papel}",
            f"GRANT SELECT, INSERT ON operacao.decisoes_regulador, operacao.reanalises TO {papel}",
            f"GRANT USAGE ON SCHEMA {gold} TO {papel}",
            f"GRANT SELECT ON {gold}.sinistros_analisados_lb TO {papel}"]


def main(nome_app: str) -> None:
    from databricks.sdk import WorkspaceClient

    from executar_sql import executar
    from lakebase.operacao import conectar

    w, amb = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")), carregar_ambiente()
    sp = w.apps.get(name=nome_app).service_principal_client_id
    for cmd in comandos_uc(amb, sp):
        executar(w, os.environ["FE_BAR_WAREHOUSE_ID"], cmd)
        print("UC:", cmd.replace(sp, "<sp>"))
    with conectar(w, os.environ.get("FE_BAR_LAKEBASE_PROJETO", "sinistros-clima")) as con:
        for cmd in comandos_pg(amb, sp):
            con.execute(cmd)
            print("Postgres:", cmd.replace(sp, "<sp>"))
        con.commit()


if __name__ == "__main__":
    main(*sys.argv[1:])

"""Teste ponta a ponta da operação no Lakebase (spec 10.2) e evidência evidencias/03-lakebase.md.

1. Dois reguladores pedem "Assumir próximo" ao mesmo tempo, várias vezes: ninguém pode receber o mesmo sinistro.
2. Cada um registra a decisão; o clique duplo (mesmo id_decisao) não pode duplicar a linha.
3. As decisões voltam ao Unity Catalog pelo Lakehouse Sync (`<catálogo>.operacional.lb_decisoes_regulador_history`).

Os reguladores de teste são identidades fictícias (`regulador_teste_a` e `regulador_teste_b`); as decisões deles ficam
na base como parte do laço de retorno.
Uso: uv run python scripts/testar_lakebase.py [rodadas=5]
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from ambiente import carregar_ambiente

RAIZ = Path(__file__).resolve().parents[1]


def renderizar(quando: str, r: dict) -> str:
    p = ["# Lakebase: fila, decisões e volta ao lakehouse (teste ponta a ponta)", "",
         f"Gerado em {quando} com `uv run python scripts/testar_lakebase.py`.", "",
         "## Estrutura", "",
         f"- Projeto Lakebase `{r['projeto']}` (Postgres {r['pg_version']}), branch `production`, compute `primary` com "
         "scale-to-zero.",
         f"- Synced table (UC → Postgres, TRIGGERED): `{r['synced']}`, estado `{r['estado_synced']}`, "
         f"{r['linhas_fila']} linhas no Postgres.",
         "- Schema `operacao` (escrito pelo app): `atribuicoes`, `decisoes_regulador` (só inserção, `id_decisao` UUID do "
         "cliente) e `reanalises`, com REPLICA IDENTITY FULL.",
         f"- Lakehouse Sync (Beta): `operacao` → `{r['destino_uc']}`, estado {r['estado_cdf']}.", "",
         "## 1. Dois reguladores assumindo ao mesmo tempo", "",
         f"- {r['pedidos']} pedidos simultâneos de \"Assumir próximo\" ({r['rodadas']} rodadas × 2 reguladores).",
         f"- Sinistros entregues: {r['entregues']}; distintos: {r['distintos']}; repetidos: **{r['entregues'] - r['distintos']}**.",
         f"- Pedidos sem caso: {r['pedidos'] - r['entregues']}. Na corrida pelo mesmo sinistro, a PK barra o segundo "
         "regulador, que volta sem caso em vez de duplicar; o app tenta o próximo até 3 vezes.",
         "", "## 2. Decisão com clique duplo", "",
         f"- {r['decisoes_enviadas']} envios (cada decisão enviada duas vezes com o mesmo `id_decisao`); linhas gravadas: "
         f"**{r['decisoes_gravadas']}**.",
         f"- Concordância com a IA nas decisões de teste: {r['concordancia']}.", "",
         "## 3. Volta ao Unity Catalog (Lakehouse Sync)", "",
         f"- `{r['tabela_historico']}`: {r['linhas_historico']} linhas com as decisões de teste "
         f"(espera de {r['espera_s']:.0f} s); tipos de mudança: {r['tipos_mudanca']}.", ""]
    return "\n".join(p)


def _sql_uc(w, sql: str):
    res = w.statement_execution.execute_statement(statement=sql, warehouse_id=os.environ["FE_BAR_WAREHOUSE_ID"],
                                                  wait_timeout="50s")
    if res.status.state.value != "SUCCEEDED":
        return None
    return res.result.data_array or []


def main(rodadas: str = "5", saida: str = "evidencias/03-lakebase.md") -> None:
    from databricks.sdk import WorkspaceClient

    from lakebase.operacao import consultas, conectar

    w, amb = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")), carregar_ambiente()
    projeto = os.environ.get("FE_BAR_LAKEBASE_PROJETO", "sinistros-clima")
    fila_pg = f"{amb.schema('gold')}.sinistros_analisados_lb"
    q = consultas(fila_pg)

    def assumir(regulador: str):
        with conectar(w, projeto) as c:
            linha = c.execute(q["assumir_proximo"], {"regulador": regulador}).fetchone()
            c.commit()
            return regulador, (linha[0] if linha else None)

    n = int(rodadas)
    pedidos = ["regulador_teste_a", "regulador_teste_b"] * n
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultado = list(pool.map(assumir, pedidos))
    entregues = [(reg, i) for reg, i in resultado if i]
    decisoes, inicio = [], time.time()
    with conectar(w, projeto) as c:
        for reg, id_aviso in entregues:
            rec = c.execute(f"SELECT recomendacao_ia, valor_sugerido FROM {fila_pg} WHERE id_aviso = %s", (id_aviso,)).fetchone()
            # o regulador de teste concorda com a IA em 4 de cada 5 casos (laço de retorno com divergência real)
            decisao = rec[0] if len(decisoes) % 5 else ("investigar" if rec[0] != "investigar" else "pagar_parcial")
            params = {"id_decisao": str(uuid.uuid4()), "id_aviso": id_aviso, "regulador": reg, "decisao": decisao,
                      "valor_aprovado": float(rec[1] or 0), "motivo": "decisão de teste (testar_lakebase.py)"}
            for _ in range(2):  # clique duplo
                c.execute(q["registrar_decisao"], params)
                decisoes.append(params["id_decisao"])
            c.execute(q["concluir_atribuicao"], {"id_aviso": id_aviso, "regulador": reg})
        c.commit()
        ids = list(set(decisoes))
        gravadas = c.execute("SELECT count(*), sum(CASE WHEN concordou_com_ia THEN 1 ELSE 0 END) FROM operacao.decisoes_regulador "
                             "WHERE id_decisao = ANY(%s::uuid[])", (ids,)).fetchone()
        linhas_fila = c.execute(f"SELECT count(*) FROM {fila_pg}").fetchone()[0]
    historico = f"{amb.catalogo}.{amb.schema('operacional')}.lb_decisoes_regulador_history"
    # o Lakehouse Sync leva o UUID do Postgres como BINARY (16 bytes): compara pelo hexadecimal, sem hífens
    lista = ", ".join(f"'{i.replace('-', '')}'" for i in ids)
    linhas_hist, tipos = [], {}
    while time.time() - inicio < 600:
        linhas_hist = _sql_uc(w, f"SELECT _pg_change_type, count(*) FROM {historico} WHERE lower(hex(id_decisao)) IN ({lista}) GROUP BY 1")
        if linhas_hist and sum(int(x[1]) for x in linhas_hist) >= len(ids):
            break
        time.sleep(20)
    tipos = {x[0]: int(x[1]) for x in (linhas_hist or [])}
    synced = w.postgres.get_synced_table(name=f"synced_tables/{amb.catalogo}.{amb.schema('gold')}.sinistros_analisados_lb")
    try:  # a API de status do Lakehouse Sync (Beta) ainda não responde em todos os workspaces: vale a config
        cfg = w.postgres.get_cdf_config(
            name=f"projects/{projeto}/branches/production/databases/databricks-postgres/cdf-configs/operacao_para_uc")
        estado_cdf = f"configurado ({cfg.postgres_schema} → {cfg.catalog}.{cfg.schema})"
    except Exception as e:  # noqa: BLE001
        estado_cdf = f"indisponível: {type(e).__name__}"
    r = {"projeto": projeto, "pg_version": w.postgres.get_project(name=f"projects/{projeto}").status.pg_version,
         "synced": synced.name, "estado_synced": synced.status.detailed_state, "linhas_fila": linhas_fila,
         "destino_uc": f"{amb.catalogo}.{amb.schema('operacional')}",
         "estado_cdf": estado_cdf,
         "rodadas": n, "pedidos": len(pedidos), "entregues": len(entregues), "distintos": len({i for _, i in entregues}),
         "decisoes_enviadas": len(decisoes), "decisoes_gravadas": int(gravadas[0]),
         "concordancia": f"{int(gravadas[1] or 0)} de {int(gravadas[0])}", "tabela_historico": historico,
         "linhas_historico": sum(tipos.values()), "tipos_mudanca": tipos or "ainda sem linhas", "espera_s": time.time() - inicio}
    md = renderizar(datetime.now().strftime("%Y-%m-%d %H:%M"), r)
    (RAIZ / saida).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main(*sys.argv[1:])

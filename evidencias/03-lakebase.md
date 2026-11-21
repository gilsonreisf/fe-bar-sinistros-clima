# Lakebase: fila, decisões e volta ao lakehouse (teste ponta a ponta)

Gerado em 2026-11-21 10:59 com `uv run python scripts/testar_lakebase.py`.

## Estrutura

- Projeto Lakebase `sinistros-clima` (Postgres 17), branch `production`, compute `primary` com scale-to-zero.
- Synced table (UC → Postgres, TRIGGERED): `synced_tables/fe_bar_sinistros_catalog.gold.sinistros_analisados_lb`, estado `SyncedTableState.SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE`, 3417 linhas no Postgres.
- Schema `operacao` (escrito pelo app): `atribuicoes`, `decisoes_regulador` (só inserção, `id_decisao` UUID do cliente) e `reanalises`, com REPLICA IDENTITY FULL.
- Lakehouse Sync (Beta): `operacao` → `fe_bar_sinistros_catalog.operacional`, estado configurado (operacao → fe_bar_sinistros_catalog.operacional).

## 1. Dois reguladores assumindo ao mesmo tempo

- 6 pedidos simultâneos de "Assumir próximo" (3 rodadas × 2 reguladores).
- Sinistros entregues: 6; distintos: 6; repetidos: **0**.
- Pedidos sem caso: 0. Na corrida pelo mesmo sinistro, a PK barra o segundo regulador, que volta sem caso em vez de duplicar; o app tenta o próximo até 3 vezes.

## 2. Decisão com clique duplo

- 12 envios (cada decisão enviada duas vezes com o mesmo `id_decisao`); linhas gravadas: **6**.
- Concordância com a IA nas decisões de teste: 4 de 6.
- Decisão de um regulador que não está com o caso: **recusada**.

## 3. Volta ao Unity Catalog (Lakehouse Sync)

- `fe_bar_sinistros_catalog.operacional.lb_decisoes_regulador_history`: 6 linhas com as decisões de teste (espera de 32 s); tipos de mudança: {'insert': 6}.

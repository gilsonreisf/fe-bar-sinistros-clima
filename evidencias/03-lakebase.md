# Lakebase: fila, decisões e volta ao lakehouse (teste ponta a ponta)

Gerado em 2026-11-21 09:44 com `uv run python scripts/testar_lakebase.py`.

## Estrutura

- Projeto Lakebase `sinistros-clima` (Postgres 17), branch `production`, compute `primary` com scale-to-zero.
- Synced table (UC → Postgres, TRIGGERED): `synced_tables/fe_bar_sinistros_catalog.gold.sinistros_analisados_lb`, estado `SyncedTableState.SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE`, 20 linhas no Postgres.
- Schema `operacao` (escrito pelo app): `atribuicoes`, `decisoes_regulador` (só inserção, `id_decisao` UUID do cliente) e `reanalises`, com REPLICA IDENTITY FULL.
- Lakehouse Sync (Beta): `operacao` → `fe_bar_sinistros_catalog.operacional`, estado configurado (operacao → fe_bar_sinistros_catalog.operacional).

## 1. Dois reguladores assumindo ao mesmo tempo

- 6 pedidos simultâneos de "Assumir próximo" (3 rodadas × 2 reguladores).
- Sinistros entregues: 1; distintos: 1; repetidos: **0**.

## 2. Decisão com clique duplo

- 2 envios (cada decisão enviada duas vezes com o mesmo `id_decisao`); linhas gravadas: **1**.
- Concordância com a IA nas decisões de teste: 0 de 1.

## 3. Volta ao Unity Catalog (Lakehouse Sync)

- `fe_bar_sinistros_catalog.operacional.lb_decisoes_regulador_history`: 0 linhas com as decisões de teste (espera de 609 s); tipos de mudança: ainda sem linhas.

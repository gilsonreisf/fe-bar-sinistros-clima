# App da regulação de sinistros climáticos (AppKit)

App Databricks (AppKit: Node + React) usado pelo regulador e pela coordenação durante o evento (spec 9; D-026).

| Tela | Para quem | Dados |
|---|---|---|
| **Painel do evento** (`/`) | diretoria e coordenação | metric view `gold.sinistros_metrics` no SQL Warehouse |
| **Fila do regulador** (`/fila`) | regulador | Lakebase: synced table do gold + `operacao.atribuicoes` ("Assumir próximo" atômico) |
| **Detalhe do sinistro** (`/sinistro/:id`) | regulador | `gold.sinistro_detalhe` (CPF mascarado) + decisão e reanálise no Lakebase; "Reanalisar com IA" chama o endpoint do parecer |
| **IA sob supervisão** (`/supervisao`) | coordenação e dono do modelo | metric view `gold.regulacao_metrics` (decisões que voltaram ao UC pelo Lakehouse Sync) |

O Genie "Sinistros Clima — Diretoria" é um espaço próprio; o app mostra o link no cabeçalho.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `consultas/*.sql` | Consultas do warehouse com `${catalogo}` e `${schema_<camada>}`; nada fixo no código (D-016) |
| `scripts/gerar-consultas.mjs` | Gera `config/queries/*.sql` a partir de `consultas/` com `FE_BAR_CATALOGO` e `FE_BAR_PREFIXO_SCHEMA` (`npm run consultas`) |
| `server/server.ts` | Rotas da fila, da decisão e da reanálise (Lakebase e endpoint do parecer) |
| `client/src/pages/` | As quatro telas |
| `databricks.yml` | Bundle do app: recursos (warehouse, Lakebase, endpoint) e variáveis |

## Rodar e publicar

1. `cp .env.example .env` e preencha o profile, o warehouse, o Lakebase (`PGHOST`, `LAKEBASE_ENDPOINT`), o endpoint, `FE_BAR_CATALOGO` e, se quiser, `FE_BAR_GENIE_SPACE_ID`.
2. Local: `npm install` e `npm run dev`.
3. Publicar (a partir de `app/`):
   ```bash
   npm run consultas
   databricks bundle deploy -t dev --var warehouse_id=<id> --var genie_space_id=<id do Genie>
   databricks bundle run -t dev app
   ```
4. Uma vez, depois do primeiro deploy, dê ao service principal do app as permissões no UC e no Postgres:
   `uv run python scripts/permissoes_app.py <nome do app>` (na raiz do projeto).

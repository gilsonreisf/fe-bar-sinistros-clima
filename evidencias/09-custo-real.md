# Custo real medido e custo por unidade

Gerado em 2026-11-21 13:16 com `uv run python scripts/custo_por_unidade.py`, a partir de `system.billing.usage` com o preço de lista (`system.billing.list_prices`).

> Valores de **referência, a calibrar na PoC**: preço de lista, workspace de desenvolvimento e faturamento com algumas horas de atraso (coluna `faturado_ate`). O volume por unidade depende do cliente (PDFs por aviso, tamanho dos documentos e LLM escolhido).

## Custo por unidade (o que escala com o evento)

| unidade | volume medido | custo medido | custo médio por unidade |
|---|---|---|---|
| PDF lido e extraído (`ai_parse_document` + `ai_extract`) | 9.705 PDFs | US$ 33,45 | US$ 0,0034 |
| Aviso processado no pipeline (PDFs + computação serverless) | 8.000 avisos | US$ 37,21 | US$ 0,0047 |
| Parecer prévio em lote (Claude Haiku 5.5 + computação do job do evento) | 3.615 pareceres já faturados | US$ 6,73 | US$ 0,0019 |

- **Por sinistro completo** (pipeline + parecer): cerca de **US$ 0,007**. Em um evento de 8 mil avisos, isso dá cerca de US$ 52,10.
- O parecer do app ("Reanalisar com IA", Claude Sonnet 5.5 no endpoint) é sob demanda: cerca de US$ 0,02 por chamada pela medição de tokens da fase 4 (D-022).
- Custo fixo de operação (não por unidade): o endpoint do parecer e o Lakebase com scale-to-zero, e o SQL Warehouse do painel e do Genie enquanto estiver ligado.

## Tudo o que foi faturado no workspace desde 2026-11-20 (total US$ 78,62, inclui desenvolvimento)

| produto | sku | recurso | quantidade | unidade | custo_lista_usd | faturado_ate |
|---|---|---|---|---|---|---|
| SQL | ENTERPRISE_SERVERLESS_SQL_COMPUTE_US_WEST_OREGON | 4648e87d2d68b63f | 36.81 | DBU | 25.77 | 2026-11-21T05:00:00.000Z |
| AI_FUNCTIONS | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_WEST_OREGON | databricks-ai-parse-document | 327.13 | DBU | 22.90 | 2026-11-21T04:20:00.000Z |
| AI_FUNCTIONS | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_WEST_OREGON | databricks-ai-extract | 150.77 | DBU | 10.55 | 2026-11-21T04:30:00.000Z |
| MODEL_SERVING | ENTERPRISE_ANTHROPIC_MODEL_SERVING | databricks-claude-sonnet-5-5 | 79.07 | DBU | 5.53 | 2026-11-21T04:00:00.000Z |
| DLT | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_WEST_OREGON | 427ee3a3-e204-49d3-af1e-bdce884845ac | 8.36 | DBU | 3.76 | 2026-11-21T05:00:00.000Z |
| MODEL_SERVING | ENTERPRISE_ANTHROPIC_MODEL_SERVING | databricks-claude-haiku-5-5 | 48.84 | DBU | 3.42 | 2026-11-21T13:00:00.000Z |
| JOBS | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_WEST_OREGON | 712482161186376 | 7.18 | DBU | 3.23 | 2026-11-21T08:00:00.000Z |
| LAKEBASE | ENTERPRISE_DATABASE_SERVERLESS_COMPUTE_US_WEST_OREGON |  | 1.84 | DBU | 0.96 | 2026-11-21T12:40:00.000Z |
| JOBS | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_WEST_OREGON | 1046824189825132 | 1.57 | DBU | 0.71 | 2026-11-21T04:00:00.000Z |
| INTERACTIVE | ENTERPRISE_ALL_PURPOSE_SERVERLESS_COMPUTE_US_WEST_OREGON |  | 0.63 | DBU | 0.60 | 2026-11-21T03:50:00.000Z |
| JOBS | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_WEST_OREGON | 729707774020558 | 0.86 | DBU | 0.39 | 2026-11-21T04:00:00.000Z |
| AGENT_EVALUATION | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_WEST_OREGON |  | 4.74 | DBU | 0.33 | 2026-11-21T04:00:00.000Z |
| MODEL_SERVING | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_WEST_OREGON | sinistros-clima-parecer-dev | 3.50 | DBU | 0.24 | 2026-11-21T13:35:00.000Z |
| AI_GATEWAY | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_WEST_OREGON | databricks-claude-haiku-5-5 | 1.10 | DBU | 0.08 | 2026-11-21T12:40:00.000Z |
| PREDICTIVE_OPTIMIZATION | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_WEST_OREGON |  | 0.16 | DBU | 0.07 | 2026-11-21T00:00:00.000Z |
| DEFAULT_STORAGE | PREMIUM_DATABRICKS_STORAGE_US_WEST_OREGON |  | 1.23 | DSU | 0.03 | 2026-11-21T06:00:00.000Z |
| LAKEBASE | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_WEST_OREGON | 3a252edf-d594-4586-8dd6-c499bd2bd992 | 0.07 | DBU | 0.03 | 2026-11-21T04:10:00.000Z |
| NETWORKING | PUBLIC_CONNECTIVITY_DATA_PROCESSED_US_WEST_OREGON |  | 0.39 | GB | 0.02 | 2026-11-21T08:00:00.000Z |
| NETWORKING | INTER_REGION_EGRESS_FROM_US_WEST_OREGON |  | 0.00 | GB | 0.00 | 2026-11-21T08:00:00.000Z |
| NETWORKING | INTERNET_EGRESS_FROM_US_WEST_OREGON |  | 0.00 | GB | 0.00 | 2026-11-21T08:00:00.000Z |
| AI_GATEWAY | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_WEST_OREGON | databricks-claude-sonnet-5-5 | 0.01 | DBU | 0.00 | 2026-11-21T03:50:00.000Z |
| LAKEBASE | ENTERPRISE_DATABRICKS_STORAGE_US_WEST_OREGON |  | 0.01 | DSU | 0.00 | 2026-11-21T12:00:00.000Z |
| AI_GATEWAY | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_WEST_OREGON | sinistros-clima-parecer-dev | 0.00 | DBU | 0.00 | 2026-11-21T03:50:00.000Z |

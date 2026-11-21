# Governança no Unity Catalog: LGPD, máscara do CPF, comentários e lineage

Executado em 2026-11-21 11:16 com `uv run python scripts/registrar_evidencia.py src/governanca/95_governanca.sql` (catálogo e schemas lidos do `.env`; D-016).

## Consulta 1

```sql
ALTER TABLE fe_bar_sinistros_catalog.bronze.segurados ALTER COLUMN cpf SET TAGS ('classificacao_lgpd' = 'dado_pessoal')
```

(comando sem resultado tabular)

## Consulta 2

```sql
ALTER TABLE fe_bar_sinistros_catalog.bronze.segurados ALTER COLUMN nome SET TAGS ('classificacao_lgpd' = 'dado_pessoal')
```

(comando sem resultado tabular)

## Consulta 3

```sql
ALTER TABLE fe_bar_sinistros_catalog.bronze.segurados ALTER COLUMN telefone SET TAGS ('classificacao_lgpd' = 'dado_pessoal')
```

(comando sem resultado tabular)

## Consulta 4

```sql
ALTER TABLE fe_bar_sinistros_catalog.bronze.segurados ALTER COLUMN email SET TAGS ('classificacao_lgpd' = 'dado_pessoal')
```

(comando sem resultado tabular)

## Consulta 5

```sql
ALTER TABLE fe_bar_sinistros_catalog.bronze.avisos ALTER COLUMN cpf_segurado SET TAGS ('classificacao_lgpd' = 'dado_pessoal')
```

(comando sem resultado tabular)

## Consulta 6

```sql
ALTER TABLE fe_bar_sinistros_catalog.silver.avisos ALTER COLUMN cpf_segurado SET TAGS ('classificacao_lgpd' = 'dado_pessoal')
```

(comando sem resultado tabular)

## Consulta 7

```sql
ALTER TABLE fe_bar_sinistros_catalog.silver.sinistros_enriquecidos ALTER COLUMN cpf_segurado SET TAGS ('classificacao_lgpd' = 'dado_pessoal')
```

(comando sem resultado tabular)

## Consulta 8

```sql
COMMENT ON TABLE fe_bar_sinistros_catalog.ml.parecer_payload IS 'Inference table do AI Gateway do endpoint do parecer: cada requisição e resposta, para auditoria e monitoramento.'
```

(comando sem resultado tabular)

## Consulta 9

```sql
COMMENT ON TABLE fe_bar_sinistros_catalog.operacional.lb_atribuicoes_history IS 'Histórico SCD2 (Lakehouse Sync) de operacao.atribuicoes do Lakebase: quem assumiu cada sinistro e quando.'
```

(comando sem resultado tabular)

## Consulta 10

```sql
COMMENT ON TABLE fe_bar_sinistros_catalog.operacional.lb_decisoes_regulador_history IS 'Histórico SCD2 (Lakehouse Sync) de operacao.decisoes_regulador: decisão do regulador ao lado da recomendação da IA (laço de retorno).'
```

(comando sem resultado tabular)

## Consulta 11

```sql
COMMENT ON TABLE fe_bar_sinistros_catalog.operacional.lb_reanalises_history IS 'Histórico SCD2 (Lakehouse Sync) de operacao.reanalises: cada "Reanalisar com IA" pedido no app, com o trace.'
```

(comando sem resultado tabular)

## Consulta 12

```sql
SELECT schema_name, table_name, column_name, tag_value
FROM fe_bar_sinistros_catalog.information_schema.column_tags
WHERE tag_name = 'classificacao_lgpd' ORDER BY schema_name, table_name, column_name
```

| schema_name | table_name | column_name | tag_value |
|---|---|---|---|
| bronze | avisos | cpf_segurado | dado_pessoal |
| bronze | segurados | cpf | dado_pessoal |
| bronze | segurados | email | dado_pessoal |
| bronze | segurados | nome | dado_pessoal |
| bronze | segurados | telefone | dado_pessoal |
| gold | sinistro_detalhe | cpf_segurado | dado_pessoal |
| silver | avisos | cpf_segurado | dado_pessoal |
| silver | sinistros_enriquecidos | cpf_segurado | dado_pessoal |

## Consulta 13

```sql
SELECT id_aviso, cpf_segurado FROM fe_bar_sinistros_catalog.gold.sinistro_detalhe ORDER BY id_aviso LIMIT 3
```

| id_aviso | cpf_segurado |
|---|---|
| AV-2026-000001 | ***.382.***-** |
| AV-2026-000002 | ***.638.***-** |
| AV-2026-000003 | ***.035.***-** |

## Consulta 14

```sql
SELECT routine_name, comment FROM fe_bar_sinistros_catalog.information_schema.routines
WHERE routine_schema = 'gold' AND routine_name = 'mascarar_cpf'
```

| routine_name | comment |
|---|---|
| mascarar_cpf | LGPD: CPF completo só para o grupo regulacao_sinistros; os demais veem só os 3 dígitos do meio. |

## Consulta 15

```sql
SELECT table_schema, table_name, table_type, comment IS NOT NULL AND comment <> '' AS tem_comentario
FROM fe_bar_sinistros_catalog.information_schema.tables
WHERE table_schema IN ('silver', 'gold', 'ml', 'operacional')
  AND table_name NOT LIKE '\_\_%' AND table_name NOT LIKE 'event_log%'
ORDER BY table_schema, table_name
```

| table_schema | table_name | table_type | tem_comentario |
|---|---|---|---|
| gold | fila_regulacao | VIEW | true |
| gold | kpis_evento | VIEW | true |
| gold | regulacao_metrics | METRIC_VIEW | true |
| gold | sinistro_detalhe | VIEW | true |
| gold | sinistros_analisados | MANAGED | true |
| gold | sinistros_analisados_lb | FOREIGN | true |
| gold | sinistros_metrics | METRIC_VIEW | true |
| ml | avaliacao_parecer_dataset | MANAGED | true |
| ml | features_treino | MANAGED | true |
| ml | parecer_payload | MANAGED | true |
| ml | prompt_parecer | MANAGED | true |
| operacional | lb_atribuicoes_history | MANAGED | true |
| operacional | lb_decisoes_regulador_history | MANAGED | true |
| operacional | lb_reanalises_history | MANAGED | true |
| silver | apolices_coberturas | MATERIALIZED_VIEW | true |
| silver | avisos | STREAMING_TABLE | true |
| silver | clima_estacao_dia | MATERIALIZED_VIEW | true |
| silver | documentos_extraidos | STREAMING_TABLE | true |
| silver | documentos_resumo | MATERIALIZED_VIEW | true |
| silver | documentos_texto | STREAMING_TABLE | true |
| silver | entrada_parecer | MATERIALIZED_VIEW | true |
| silver | evidencia_climatica | MATERIALIZED_VIEW | true |
| silver | evidencia_climatica_historico | MATERIALIZED_VIEW | true |
| silver | historico_enriquecido | MATERIALIZED_VIEW | true |
| silver | ocorrencias_defesa_civil | MATERIALIZED_VIEW | true |
| silver | sinistros_enriquecidos | MATERIALIZED_VIEW | true |

## Consulta 16

```sql
SELECT DISTINCT source_table_full_name AS origem, target_table_full_name AS destino, entity_type AS por
FROM system.access.table_lineage
WHERE workspace_id = '7474657549414280' AND event_date >= DATE'2026-11-20'
  AND (target_table_full_name LIKE 'fe_bar_sinistros_catalog.gold.%' OR source_table_full_name LIKE 'fe_bar_sinistros_catalog.gold.%')
  AND source_table_full_name IS NOT NULL AND target_table_full_name IS NOT NULL
ORDER BY destino, origem
```

| origem | destino | por |
|---|---|---|
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.fila_regulacao | JOB |
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.fila_regulacao |  |
| fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | fe_bar_sinistros_catalog.gold.fila_regulacao | JOB |
| fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | fe_bar_sinistros_catalog.gold.fila_regulacao |  |
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.kpis_evento | JOB |
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.kpis_evento |  |
| fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | fe_bar_sinistros_catalog.gold.kpis_evento |  |
| fe_bar_sinistros_catalog.operacional.lb_decisoes_regulador_history | fe_bar_sinistros_catalog.gold.regulacao_metrics |  |
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.sinistro_detalhe | JOB |
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.sinistro_detalhe |  |
| fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | fe_bar_sinistros_catalog.gold.sinistro_detalhe | JOB |
| fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | fe_bar_sinistros_catalog.gold.sinistro_detalhe |  |
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.sinistros_analisados_lb | PIPELINE |
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.sinistros_metrics |  |
| fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | fe_bar_sinistros_catalog.gold.sinistros_metrics |  |

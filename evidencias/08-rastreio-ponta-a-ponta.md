# Rastreio ponta a ponta do sinistro AV-2026-000047

Gerado em 2026-11-21 10:31 com `uv run python scripts/rastrear_sinistro.py`. O mesmo aviso em cada camada: Lakeflow (bronze e silver) → Unity Catalog → ML e GenAI → gold → Lakebase → app → de volta ao UC.

## 1. Chegada (Volume → bronze, Auto Loader)

O aviso entrou pelo arquivo do lote, com metadados de ingestão.

| id_aviso | arquivo | _ingerido_em | causa_declarada | valor_reclamado | documentos |
|---|---|---|---|---|---|
| AV-2026-000047 | avisos_lote_01.jsonl | 2026-11-20T23:18:52.130Z | danos_eletricos | 139562.34 | 2 |

## 2. Documentos (bronze → silver: `ai_parse_document` + `ai_extract`)

Cada PDF lido e os campos extraídos por IA, ainda dentro do pipeline.

| tipo_documento | arquivo | legivel | valor_total | menciona_dano_anterior | itens | erro_extracao |
|---|---|---|---|---|---|---|
| laudo | AV-2026-000047_laudo.pdf | true |  | false | 0 |  |
| orcamento | AV-2026-000047_orcamento.pdf | true | 139562.34 | false | 4 |  |

## 3. Cruzamentos (silver: apólice, clima INMET/Defesa Civil, preço, prestador)

Fatos que o regulador conferiria à mão, já calculados.

| cobertura_valida | dentro_vigencia | dias_desde_contratacao | forca_evidencia_climatica | fonte_evidencia | desvio_preco | participacao_prestador_30d | alertas |
|---|---|---|---|---|---|---|---|
| true | true | 9 | forte | inmet | -0.0255 | 4.92E-4 | [] |

## 4. Score de suspeita (modelo `ml.modelo_suspeita@champion`) e parecer prévio (LLM com prompt versionado)

Saída do job do evento no gold, com versões e trace do MLflow.

| score | fatores_suspeita | versao_modelo | recomendacao_ia | valor_sugerido | confianca | status_parecer | versao_prompt | llm | trace_id |
|---|---|---|---|---|---|---|---|---|---|
| 0.9977 | Apólice contratada há menos de 30 dias; Valor reclamado alto; Valor próximo do limite da cobertura (LMI) | 3 | investigar | 14000.0 | 0.9 | ok | 2 | databricks-claude-haiku-5-5 | tr-ae2140c0feaf2a0c1ca6dbc6dd40f414 |

## 5. Fast track, prioridade e posição na fila (gold)

Por que o caso não saiu automático e onde ele entrou na fila.

| fast_track | bloqueios | prioridade | posicao_fila |
|---|---|---|---|
| false | ["valor_acima_do_teto","score_suspeita","recomendacao_nao_integral"] | 0.999 | 10 |

## 6. Consumo governado (visão de detalhe com CPF mascarado)

O que o app mostra ao regulador.

| id_aviso | cpf_segurado | municipio | recomendacao_ia |
|---|---|---|---|
| AV-2026-000047 | ***.328.***-** | Rio Negrinho | investigar |

## 6b. Operação no Lakebase (synced table do gold e atribuição)

A fila lida em baixa latência pelo app e quem assumiu o caso.

| id_aviso | fast_track | prioridade | recomendacao_ia |
|---|---|---|---|
| AV-2026-000047 | False | 0.9990 | investigar |

| regulador | status | atribuido_em |
|---|---|---|
| regulador_teste_a | decidido | 2026-11-21 13:29:15.250158+00:00 |

## 7. Decisão do regulador de volta ao UC (Lakebase → Lakehouse Sync)

A decisão gravada no Postgres pelo app, já como histórico SCD2 no Unity Catalog.

| _pg_change_type | regulador | decisao | recomendacao_ia | concordou_com_ia | valor_aprovado | criado_em |
|---|---|---|---|---|---|---|
| insert | regulador_teste_a | pagar_parcial | investigar | false | 14000.00 | 2026-11-21T13:29:23.484Z |

## 8. Lineage registrado pelo Unity Catalog para as tabelas do caminho

Origem → destino, por tipo de entidade.

| origem | destino | por |
|---|---|---|
| fe_bar_sinistros_catalog.gold.sinistros_analisados | fe_bar_sinistros_catalog.gold.sinistros_analisados_lb | PIPELINE |
| fe_bar_sinistros_catalog.bronze.precos_referencia | fe_bar_sinistros_catalog.silver.entrada_parecer | PIPELINE |
| fe_bar_sinistros_catalog.silver.apolices_coberturas | fe_bar_sinistros_catalog.silver.entrada_parecer | PIPELINE |
| fe_bar_sinistros_catalog.silver.documentos_extraidos | fe_bar_sinistros_catalog.silver.entrada_parecer | PIPELINE |
| fe_bar_sinistros_catalog.silver.documentos_texto | fe_bar_sinistros_catalog.silver.entrada_parecer | PIPELINE |
| fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | fe_bar_sinistros_catalog.silver.entrada_parecer | PIPELINE |
| fe_bar_sinistros_catalog.silver.apolices_coberturas | fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | PIPELINE |
| fe_bar_sinistros_catalog.silver.avisos | fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | PIPELINE |
| fe_bar_sinistros_catalog.silver.documentos_resumo | fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | PIPELINE |
| fe_bar_sinistros_catalog.silver.evidencia_climatica | fe_bar_sinistros_catalog.silver.sinistros_enriquecidos | PIPELINE |

## 9. Uso do modelo servido (inference table do AI Gateway)

Cada chamada ao endpoint (teste do endpoint e "Reanalisar com IA" no app) fica auditada; a tabela chega com atraso de até uma hora. O parecer em lote chama o LLM direto (D-023) e fica no trace do MLflow.

| requisicoes | primeira | ultima |
|---|---|---|
| 3 | 2026-11-21T03:49:35.792Z | 2026-11-21T03:49:47.524Z |


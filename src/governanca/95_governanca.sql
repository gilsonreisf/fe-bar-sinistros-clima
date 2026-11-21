-- Governança enxuta da fase 7 (D-025): dado pessoal marcado com tag LGPD, CPF mascarado na camada de consumo (gold) e
-- conferência de comentários, lineage e permissões. Idempotente. A função `mascarar_cpf` e a visão `sinistro_detalhe`
-- vêm de `gold.visoes.ddl_gold` (job do evento ou `scripts/aplicar_visoes_gold.py`).

-- 1. Tags LGPD nas colunas pessoais das camadas de engenharia (bronze e silver). Quem consome (app, Genie, analistas)
--    lê só o gold, onde o CPF chega mascarado.
ALTER TABLE ${catalogo}.${schema_bronze}.segurados ALTER COLUMN cpf SET TAGS ('classificacao_lgpd' = 'dado_pessoal');
ALTER TABLE ${catalogo}.${schema_bronze}.segurados ALTER COLUMN nome SET TAGS ('classificacao_lgpd' = 'dado_pessoal');
ALTER TABLE ${catalogo}.${schema_bronze}.segurados ALTER COLUMN telefone SET TAGS ('classificacao_lgpd' = 'dado_pessoal');
ALTER TABLE ${catalogo}.${schema_bronze}.segurados ALTER COLUMN email SET TAGS ('classificacao_lgpd' = 'dado_pessoal');
ALTER TABLE ${catalogo}.${schema_bronze}.avisos ALTER COLUMN cpf_segurado SET TAGS ('classificacao_lgpd' = 'dado_pessoal');
ALTER TABLE ${catalogo}.${schema_silver}.avisos ALTER COLUMN cpf_segurado SET TAGS ('classificacao_lgpd' = 'dado_pessoal');
ALTER TABLE ${catalogo}.${schema_silver}.sinistros_enriquecidos ALTER COLUMN cpf_segurado SET TAGS ('classificacao_lgpd' = 'dado_pessoal');

-- Comentários das tabelas criadas pela plataforma (inference table do AI Gateway e histórico do Lakehouse Sync).
COMMENT ON TABLE ${catalogo}.${schema_ml}.parecer_payload IS 'Inference table do AI Gateway do endpoint do parecer: cada requisição e resposta, para auditoria e monitoramento.';
COMMENT ON TABLE ${catalogo}.${schema_operacional}.lb_atribuicoes_history IS 'Histórico SCD2 (Lakehouse Sync) de operacao.atribuicoes do Lakebase: quem assumiu cada sinistro e quando.';
COMMENT ON TABLE ${catalogo}.${schema_operacional}.lb_decisoes_regulador_history IS 'Histórico SCD2 (Lakehouse Sync) de operacao.decisoes_regulador: decisão do regulador ao lado da recomendação da IA (laço de retorno).';
COMMENT ON TABLE ${catalogo}.${schema_operacional}.lb_reanalises_history IS 'Histórico SCD2 (Lakehouse Sync) de operacao.reanalises: cada "Reanalisar com IA" pedido no app, com o trace.';

-- 2. Onde há dado pessoal (inventário pela tag).
SELECT schema_name, table_name, column_name, tag_value
FROM ${catalogo}.information_schema.column_tags
WHERE tag_name = 'classificacao_lgpd' ORDER BY schema_name, table_name, column_name;

-- 3. CPF na camada de consumo: mascarado para quem não é do grupo da regulação (é o caso desta identidade).
SELECT id_aviso, cpf_segurado FROM ${catalogo}.${schema_gold}.sinistro_detalhe ORDER BY id_aviso LIMIT 3;

SELECT routine_name, comment FROM ${catalogo}.information_schema.routines
WHERE routine_schema = '${schema_gold}' AND routine_name = 'mascarar_cpf';

-- 4. Comentários: toda tabela e visão do gold e do silver documentada no catálogo.
SELECT table_schema, table_name, table_type, comment IS NOT NULL AND comment <> '' AS tem_comentario
FROM ${catalogo}.information_schema.tables
WHERE table_schema IN ('${schema_silver}', '${schema_gold}', '${schema_ml}', '${schema_operacional}')
  AND table_name NOT LIKE '\_\_%' AND table_name NOT LIKE 'event_log%'
ORDER BY table_schema, table_name;

-- 5. Lineage capturado pelo Unity Catalog: de onde vem cada objeto do gold e quem lê dele.
SELECT DISTINCT source_table_full_name AS origem, target_table_full_name AS destino, entity_type AS por
FROM system.access.table_lineage
WHERE workspace_id = '${workspace_id}' AND event_date >= DATE'2026-11-20'
  AND (target_table_full_name LIKE '${catalogo}.${schema_gold}.%' OR source_table_full_name LIKE '${catalogo}.${schema_gold}.%')
  AND source_table_full_name IS NOT NULL AND target_table_full_name IS NOT NULL
ORDER BY destino, origem;

-- IA sob supervisão: decisões dos reguladores (Lakebase → UC pelo Lakehouse Sync) contra a recomendação da IA.
SELECT MEASURE(`Decisões`) AS decisoes, MEASURE(`Concordância com a IA`) AS concordancia,
  MEASURE(`Divergências da IA`) AS divergencias, MEASURE(`Valor aprovado`) AS valor_aprovado,
  MEASURE(`Valor sugerido pela IA`) AS valor_sugerido_ia
FROM ${catalogo}.${schema_gold}.regulacao_metrics

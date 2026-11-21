-- Onde o regulador concorda e onde diverge da IA (insumo do retreino, próximo passo).
SELECT `Recomendação da IA` AS recomendacao_ia, `Decisão do regulador` AS decisao_regulador,
  MEASURE(`Decisões`) AS decisoes
FROM ${catalogo}.${schema_gold}.regulacao_metrics
GROUP BY ALL ORDER BY decisoes DESC

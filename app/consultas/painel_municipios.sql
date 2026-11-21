-- Os 10 municípios com maior exposição, com o peso dos suspeitos.
SELECT `Município` AS municipio, MEASURE(`Avisos`) AS avisos, MEASURE(`Valor reclamado`) AS valor_reclamado,
  MEASURE(`Sinistros suspeitos`) AS suspeitos, MEASURE(`Percentual de fast track`) AS pct_fast_track
FROM ${catalogo}.${schema_gold}.sinistros_metrics
GROUP BY ALL ORDER BY valor_reclamado DESC LIMIT 10

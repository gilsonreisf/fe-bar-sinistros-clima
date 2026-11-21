-- Chegada dos avisos por lote: quantos foram liberados no fast track e quantos foram encaminhados ao regulador.
SELECT concat('Lote ', lpad(CAST(`Lote` AS STRING), 2, '0')) AS lote,
  MEASURE(`Sinistros no fast track`) AS fast_track, MEASURE(`Encaminhados ao regulador`) AS regulador
FROM ${catalogo}.${schema_gold}.sinistros_metrics
GROUP BY ALL ORDER BY lote

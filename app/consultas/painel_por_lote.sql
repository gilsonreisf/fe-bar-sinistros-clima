-- Chegada dos avisos por lote: quantos foram liberados no fast track e quantos foram para a fila.
SELECT concat('Lote ', lpad(CAST(`Lote` AS STRING), 2, '0')) AS lote,
  MEASURE(`Sinistros no fast track`) AS fast_track, MEASURE(`Na fila do regulador`) AS fila
FROM ${catalogo}.${schema_gold}.sinistros_metrics
GROUP BY ALL ORDER BY lote

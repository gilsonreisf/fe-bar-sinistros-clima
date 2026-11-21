-- Painel do evento: números do topo (metric view do gold; as definições ficam no UC, D-025).
SELECT MEASURE(`Avisos`) AS avisos, MEASURE(`Valor reclamado`) AS valor_reclamado,
  MEASURE(`Sinistros no fast track`) AS fast_track, MEASURE(`Percentual de fast track`) AS pct_fast_track,
  MEASURE(`Valor liberado no fast track`) AS valor_liberado_fast_track, MEASURE(`Na fila do regulador`) AS na_fila,
  MEASURE(`Sinistros suspeitos`) AS suspeitos, MEASURE(`Valor reclamado suspeito`) AS valor_suspeito,
  MEASURE(`Ajuste sugerido pela IA`) AS ajuste_ia, MEASURE(`Pareceres pendentes`) AS pareceres_pendentes
FROM ${catalogo}.${schema_gold}.sinistros_metrics

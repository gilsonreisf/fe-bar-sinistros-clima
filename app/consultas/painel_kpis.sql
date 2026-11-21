-- Painel do evento: números do topo (metric view do gold; as definições ficam no UC, D-025).
SELECT MEASURE(`Avisos`) AS avisos, MEASURE(`Valor reclamado`) AS valor_reclamado,
  MEASURE(`Sinistros no fast track`) AS fast_track, MEASURE(`Percentual de fast track`) AS pct_fast_track,
  MEASURE(`Valor liberado no fast track`) AS valor_liberado_fast_track, MEASURE(`Encaminhados ao regulador`) AS encaminhados,
  MEASURE(`Sinistros suspeitos`) AS suspeitos, MEASURE(`Valor reclamado suspeito`) AS valor_suspeito,
  MEASURE(`Ajuste por evidência sugerido pela IA`) AS ajuste_ia, MEASURE(`Recusas por falta de cobertura`) AS recusas_cobertura, MEASURE(`Pareceres pendentes`) AS pareceres_pendentes
FROM ${catalogo}.${schema_gold}.sinistros_metrics

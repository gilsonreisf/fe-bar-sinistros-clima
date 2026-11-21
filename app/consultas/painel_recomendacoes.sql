-- O que o parecer prévio recomendou (a decisão é do regulador).
SELECT CASE `Recomendação da IA` WHEN 'pagar_integral' THEN 'Pagar integral' WHEN 'pagar_parcial' THEN 'Pagar parcial'
    WHEN 'recusar' THEN 'Recusar' WHEN 'investigar' THEN 'Investigar' ELSE 'Sem parecer' END AS recomendacao,
  MEASURE(`Avisos`) AS avisos
FROM ${catalogo}.${schema_gold}.sinistros_metrics
GROUP BY ALL ORDER BY avisos DESC

-- Custo real medido em system.billing.usage (spec 10.1, item 09). Pode haver atraso de algumas horas no faturamento.
SELECT u.usage_date, u.billing_origin_product, u.sku_name,
  round(sum(u.usage_quantity), 3) AS quantidade, any_value(u.usage_unit) AS unidade,
  round(sum(u.usage_quantity * lp.pricing.default), 2) AS custo_lista_usd
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices lp
  ON lp.sku_name = u.sku_name AND lp.cloud = u.cloud
  AND u.usage_start_time >= lp.price_start_time
  AND (lp.price_end_time IS NULL OR u.usage_start_time < lp.price_end_time)
WHERE u.workspace_id = '${workspace_id}' AND u.usage_date >= DATE'2026-11-20'
GROUP BY ALL ORDER BY u.usage_date, custo_lista_usd DESC;

# Custo real medido (lote 1 do evento)

Executado em 2026-11-20 20:34 com `uv run python scripts/registrar_evidencia.py src/governanca/92_custo.sql` (catálogo e schemas lidos do `.env`; D-016).

## Consulta 1

```sql
SELECT u.usage_date, u.billing_origin_product, u.sku_name,
  round(sum(u.usage_quantity), 3) AS quantidade, any_value(u.usage_unit) AS unidade,
  round(sum(u.usage_quantity * lp.pricing.default), 2) AS custo_lista_usd
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices lp
  ON lp.sku_name = u.sku_name AND lp.cloud = u.cloud
  AND u.usage_start_time >= lp.price_start_time
  AND (lp.price_end_time IS NULL OR u.usage_start_time < lp.price_end_time)
WHERE u.workspace_id = '7474657549414280' AND u.usage_date >= DATE'2026-11-20'
GROUP BY ALL ORDER BY u.usage_date, custo_lista_usd DESC
```

| usage_date | billing_origin_product | sku_name | quantidade | unidade | custo_lista_usd |
|---|---|---|---|---|---|
**Situação em 2026-11-20 20:34:** o faturamento do processamento do lote 1 (800 avisos e 951 PDFs com `ai_parse_document` e `ai_extract`, pipeline serverless) ainda não chegou ao `system.billing.usage`, que costuma atrasar algumas horas. A consulta é refeita no início da fase 5, **antes** de publicar os lotes 2 a 10 (D-017), e este arquivo é regenerado com os valores medidos.

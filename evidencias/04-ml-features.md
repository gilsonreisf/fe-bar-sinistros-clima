# Features do modelo de suspeita: histórico 2025 e lote 1 do evento

Executado em 2026-11-20 23:34 com `uv run python scripts/registrar_evidencia.py src/governanca/93_conferir_features.sql` (catálogo e schemas lidos do `.env`; D-016).

## Consulta 1

```sql
SELECT 'silver' AS camada, 'historico_enriquecido' AS tabela, count(*) AS linhas FROM fe_bar_sinistros_catalog.silver.historico_enriquecido
UNION ALL SELECT 'silver', 'evidencia_climatica_historico', count(*) FROM fe_bar_sinistros_catalog.silver.evidencia_climatica_historico
UNION ALL SELECT 'silver', 'sinistros_enriquecidos', count(*) FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos
```

| camada | tabela | linhas |
|---|---|---|
| silver | historico_enriquecido | 20000 |
| silver | evidencia_climatica_historico | 20000 |
| silver | sinistros_enriquecidos | 800 |

## Consulta 2

```sql
SELECT g.padrao, count(*) AS sinistros,
  round(100 * avg(CASE WHEN h.forca_evidencia_climatica = 'forte' THEN 1.0 ELSE 0.0 END), 1) AS pct_forte,
  round(100 * avg(CASE WHEN h.forca_evidencia_climatica = 'fraca' THEN 1.0 ELSE 0.0 END), 1) AS pct_fraca,
  round(100 * avg(CASE WHEN h.forca_evidencia_climatica = 'contraria' THEN 1.0 ELSE 0.0 END), 1) AS pct_contraria,
  round(percentile(h.desvio_preco_pct, 0.5), 3) AS desvio_mediano,
  percentile(h.dias_desde_contratacao, 0.5) AS dias_mediano,
  round(100 * avg(CASE WHEN h.cobertura_valida THEN 0.0 ELSE 1.0 END), 1) AS pct_sem_cobertura,
  round(100 * avg(CASE WHEN h.menciona_dano_anterior THEN 1.0 ELSE 0.0 END), 1) AS pct_dano_anterior,
  round(1000 * percentile(h.participacao_prestador_30d, 0.5), 3) AS participacao_mediana_por_mil,
  round(100 * avg(CASE WHEN h.participacao_prestador_30d IS NULL THEN 1.0 ELSE 0.0 END), 1) AS pct_participacao_nula
FROM fe_bar_sinistros_catalog.silver.historico_enriquecido h
JOIN read_files('/Volumes/fe_bar_sinistros_catalog/ml/restrito/gabarito/gabarito_historico_2025.csv', format => 'csv', header => true) g
  ON g.id_sinistro = h.id_sinistro
GROUP BY g.padrao ORDER BY g.padrao
```

| padrao | sinistros | pct_forte | pct_fraca | pct_contraria | desvio_mediano | dias_mediano | pct_sem_cobertura | pct_dano_anterior | participacao_mediana_por_mil | pct_participacao_nula |
|---|---|---|---|---|---|---|---|---|---|---|
| apolice_recente | 400 | 73.3 | 26.3 | 0.5 | 0.02 | 6.0 | 0.0 | 0.0 | 0.477 | 0.0 |
| dano_preexistente | 400 | 80.5 | 19.5 | 0.0 | 0.024 | 175.0 | 0.0 | 100.0 | 0.468 | 0.0 |
| legitimo_complexo | 5000 | 77.1 | 22.7 | 0.2 | 0.021 | 183.0 | 0.0 | 0.0 | 0.459 | 0.0 |
| legitimo_simples | 12000 | 77.9 | 21.9 | 0.2 | 0.023 | 180.0 | 0.0 | 0.0 | 0.457 | 0.0 |
| orcamento_inflado | 800 | 76.1 | 23.8 | 0.1 | 0.784 | 178.0 | 0.0 | 0.0 | 0.436 | 0.0 |
| prestador_concentrado | 200 | 78.0 | 21.5 | 0.5 | 0.019 | 169.5 | 0.0 | 0.0 | 1.737 | 0.0 |
| sem_cobertura | 600 | 77.3 | 22.7 | 0.0 | 0.022 | 181.5 | 100.0 | 0.0 | 0.453 | 0.0 |
| sem_evento_climatico | 600 | 0.0 | 4.2 | 95.8 | 0.025 | 183.5 | 0.0 | 0.0 | 0.447 | 0.0 |

## Consulta 3

```sql
SELECT g.padrao, count(*) AS avisos,
  round(100 * avg(CASE WHEN s.forca_evidencia_climatica = 'forte' THEN 1.0 ELSE 0.0 END), 1) AS pct_forte,
  round(100 * avg(CASE WHEN s.forca_evidencia_climatica = 'fraca' THEN 1.0 ELSE 0.0 END), 1) AS pct_fraca,
  round(100 * avg(CASE WHEN s.forca_evidencia_climatica = 'contraria' THEN 1.0 ELSE 0.0 END), 1) AS pct_contraria,
  round(percentile(s.desvio_preco_pct, 0.5), 3) AS desvio_mediano,
  percentile(s.dias_desde_contratacao, 0.5) AS dias_mediano,
  round(100 * avg(CASE WHEN s.cobertura_valida THEN 0.0 ELSE 1.0 END), 1) AS pct_sem_cobertura,
  round(100 * avg(CASE WHEN s.menciona_dano_anterior THEN 1.0 ELSE 0.0 END), 1) AS pct_dano_anterior,
  round(1000 * percentile(s.participacao_prestador_30d, 0.5), 3) AS participacao_mediana_por_mil,
  round(100 * avg(CASE WHEN s.participacao_prestador_30d IS NULL THEN 1.0 ELSE 0.0 END), 1) AS pct_participacao_nula
FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos s
JOIN read_files('/Volumes/fe_bar_sinistros_catalog/ml/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) g
  ON g.id_aviso = s.id_aviso
GROUP BY g.padrao ORDER BY g.padrao
```

| padrao | avisos | pct_forte | pct_fraca | pct_contraria | desvio_mediano | dias_mediano | pct_sem_cobertura | pct_dano_anterior | participacao_mediana_por_mil | pct_participacao_nula |
|---|---|---|---|---|---|---|---|---|---|---|
| apolice_recente | 13 | 100.0 | 0.0 | 0.0 | -0.003 | 6.0 | 0.0 | 0.0 | 0.448 | 0.0 |
| dano_preexistente | 9 | 100.0 | 0.0 | 0.0 | -0.005 | 112.0 | 0.0 | 100.0 | 0.448 | 0.0 |
| legitimo_complexo | 178 | 100.0 | 0.0 | 0.0 | 0.025 | 174.0 | 0.0 | 0.0 | 0.448 | 0.0 |
| legitimo_simples | 436 | 99.8 | 0.2 | 0.0 | 0.02 | 178.5 | 0.0 | 0.0 | 0.448 | 0.0 |
| orcamento_inflado | 25 | 100.0 | 0.0 | 0.0 | 0.865 | 169.0 | 0.0 | 0.0 | 0.448 | 0.0 |
| prestador_concentrado | 5 | 100.0 | 0.0 | 0.0 | -0.026 | 132.0 | 0.0 | 0.0 | 0.381 | 0.0 |
| sem_cobertura | 16 | 100.0 | 0.0 | 0.0 | -0.004 | 244.5 | 100.0 | 0.0 | 0.448 | 0.0 |
| sem_evento_climatico | 118 | 0.0 | 2.5 | 97.5 | 0.012 | 147.0 | 0.0 | 0.0 | 0.466 | 0.0 |

## Consulta 4

```sql
SELECT 'historico' AS base,
  sum(CASE WHEN e.id_sinistro IS NULL THEN 1 ELSE 0 END) AS sem_linha_de_evidencia,
  sum(CASE WHEN h.desvio_preco_pct IS NULL THEN 1 ELSE 0 END) AS sem_desvio,
  sum(CASE WHEN h.cobertura_valida AND h.lmi IS NULL THEN 1 ELSE 0 END) AS cobertura_sem_lmi,
  sum(CASE WHEN NOT h.cobertura_valida AND h.lmi IS NOT NULL THEN 1 ELSE 0 END) AS lmi_sem_cobertura
FROM fe_bar_sinistros_catalog.silver.historico_enriquecido h
LEFT JOIN fe_bar_sinistros_catalog.silver.evidencia_climatica_historico e ON e.id_sinistro = h.id_sinistro
UNION ALL
SELECT 'evento',
  sum(CASE WHEN e.id_aviso IS NULL THEN 1 ELSE 0 END),
  sum(CASE WHEN s.desvio_preco_pct IS NULL THEN 1 ELSE 0 END),
  sum(CASE WHEN s.cobertura_valida AND s.lmi IS NULL THEN 1 ELSE 0 END),
  sum(CASE WHEN NOT s.cobertura_valida AND s.lmi IS NOT NULL THEN 1 ELSE 0 END)
FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos s
LEFT JOIN fe_bar_sinistros_catalog.silver.evidencia_climatica e ON e.id_aviso = s.id_aviso
```

| base | sem_linha_de_evidencia | sem_desvio | cobertura_sem_lmi | lmi_sem_cobertura |
|---|---|---|---|---|
| historico | 0 | 0 | 0 | 0 |
| evento | 0 | 6 | 0 | 0 |

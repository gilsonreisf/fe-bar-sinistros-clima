# Ingestão e enriquecimento: lote 1 do evento

Executado em 2026-11-20 20:33 com `uv run python scripts/registrar_evidencia.py src/governanca/91_conferir_pipeline.sql` (catálogo e schemas lidos do `.env`; D-016).

## Consulta 1

```sql
SELECT 'bronze' AS camada, 'avisos' AS tabela, count(*) AS linhas FROM fe_bar_sinistros_catalog.bronze.avisos
UNION ALL SELECT 'bronze', 'documentos', count(*) FROM fe_bar_sinistros_catalog.bronze.documentos
UNION ALL SELECT 'bronze', 'apolices', count(*) FROM fe_bar_sinistros_catalog.bronze.apolices
UNION ALL SELECT 'bronze', 'apolices_coberturas', count(*) FROM fe_bar_sinistros_catalog.bronze.apolices_coberturas
UNION ALL SELECT 'bronze', 'segurados', count(*) FROM fe_bar_sinistros_catalog.bronze.segurados
UNION ALL SELECT 'bronze', 'clima_inmet', count(*) FROM fe_bar_sinistros_catalog.bronze.clima_inmet
UNION ALL SELECT 'bronze', 'historico_sinistros', count(*) FROM fe_bar_sinistros_catalog.bronze.historico_sinistros
UNION ALL SELECT 'silver', 'avisos', count(*) FROM fe_bar_sinistros_catalog.silver.avisos
UNION ALL SELECT 'silver', 'documentos_extraidos', count(*) FROM fe_bar_sinistros_catalog.silver.documentos_extraidos
UNION ALL SELECT 'silver', 'clima_estacao_dia', count(*) FROM fe_bar_sinistros_catalog.silver.clima_estacao_dia
UNION ALL SELECT 'silver', 'evidencia_climatica', count(*) FROM fe_bar_sinistros_catalog.silver.evidencia_climatica
UNION ALL SELECT 'silver', 'sinistros_enriquecidos', count(*) FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos
```

| camada | tabela | linhas |
|---|---|---|
| bronze | avisos | 800 |
| bronze | documentos | 951 |
| bronze | apolices | 60251 |
| bronze | apolices_coberturas | 169066 |
| bronze | segurados | 50251 |
| bronze | clima_inmet | 378048 |
| bronze | historico_sinistros | 20000 |
| silver | avisos | 800 |
| silver | documentos_extraidos | 951 |
| silver | clima_estacao_dia | 15752 |
| silver | evidencia_climatica | 800 |
| silver | sinistros_enriquecidos | 800 |

## Consulta 2

```sql
SELECT tipo_documento, count(*) AS documentos, sum(CAST(legivel AS INT)) AS legiveis,
  sum(CAST(erro_extracao IS NOT NULL AS INT)) AS erros_extracao
FROM fe_bar_sinistros_catalog.silver.documentos_extraidos GROUP BY tipo_documento ORDER BY tipo_documento
```

| tipo_documento | documentos | legiveis | erros_extracao |
|---|---|---|---|
| laudo | 151 | 151 | 0 |
| orcamento | 800 | 800 | 0 |

## Consulta 3

```sql
SELECT g.forca_evidencia_esperada, s.forca_evidencia_climatica, g.fonte_evidencia_esperada, s.fonte_evidencia, count(*) AS avisos
FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos s
JOIN read_files('/Volumes/fe_bar_sinistros_catalog/ml/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) g
  ON g.id_aviso = s.id_aviso
GROUP BY ALL ORDER BY avisos DESC
```

| forca_evidencia_esperada | forca_evidencia_climatica | fonte_evidencia_esperada | fonte_evidencia | avisos |
|---|---|---|---|---|
| forte | forte | defesa_civil | defesa_civil | 590 |
| contraria | contraria | inmet | inmet | 115 |
| forte | forte | inmet | inmet | 91 |
| fraca | fraca | nenhuma | nenhuma | 4 |

## Consulta 4

```sql
WITH gab AS (
  SELECT id_aviso, round(sum(CAST(valor_total AS DOUBLE)), 2) AS total_gabarito, count(*) AS itens_gabarito
  FROM read_files('/Volumes/fe_bar_sinistros_catalog/ml/restrito/gabarito/gabarito_itens_evento_2026.csv', format => 'csv', header => true)
  GROUP BY id_aviso
)
SELECT count(*) AS avisos,
  round(100 * avg(CASE WHEN abs(r.valor_orcamento - gab.total_gabarito) <= 0.01 THEN 1.0 ELSE 0.0 END), 1) AS pct_total_exato,
  round(100 * avg(CASE WHEN r.itens_extraidos = gab.itens_gabarito THEN 1.0 ELSE 0.0 END), 1) AS pct_qtd_itens_exata,
  round(100 * sum(r.itens_casados) / sum(r.itens_extraidos), 1) AS pct_itens_casados_com_preco
FROM fe_bar_sinistros_catalog.silver.documentos_resumo r JOIN gab ON gab.id_aviso = r.id_aviso
```

| avisos | pct_total_exato | pct_qtd_itens_exata | pct_itens_casados_com_preco |
|---|---|---|---|
| 800 | 100.0 | 100.0 | 99.1 |

## Consulta 5

```sql
SELECT g.padrao, count(*) AS avisos,
  round(avg(CAST(s.cobertura_valida AS INT)), 2) AS pct_cobertura_valida,
  round(avg(s.desvio_preco_pct), 3) AS desvio_preco_medio,
  round(avg(CAST(array_contains(s.flags_documento, 'menciona_dano_anterior') AS INT)), 2) AS pct_dano_anterior,
  round(avg(CAST(array_contains(s.flags_documento, 'preco_acima_referencia') AS INT)), 2) AS pct_preco_acima,
  percentile(s.dias_desde_contratacao, 0.5) AS mediana_dias_contratacao,
  max(s.qtd_orcamentos_prestador) AS max_orcamentos_prestador
FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos s
JOIN read_files('/Volumes/fe_bar_sinistros_catalog/ml/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) g
  ON g.id_aviso = s.id_aviso
GROUP BY g.padrao ORDER BY avisos DESC
```

| padrao | avisos | pct_cobertura_valida | desvio_preco_medio | pct_dano_anterior | pct_preco_acima | mediana_dias_contratacao | max_orcamentos_prestador |
|---|---|---|---|---|---|---|---|
| legitimo_simples | 436 | 1.0 | 0.02 | 0.0 | 0.0 | 178.5 | 5 |
| legitimo_complexo | 178 | 1.0 | 0.025 | 0.0 | 0.0 | 174.0 | 5 |
| sem_evento_climatico | 118 | 1.0 | 0.015 | 0.0 | 0.0 | 147.0 | 5 |
| orcamento_inflado | 25 | 1.0 | 0.821 | 0.0 | 1.0 | 169.0 | 3 |
| sem_cobertura | 16 | 0.0 | 0.003 | 0.0 | 0.0 | 244.5 | 3 |
| apolice_recente | 13 | 1.0 | 0.011 | 0.0 | 0.0 | 6.0 | 3 |
| dano_preexistente | 9 | 1.0 | 0.003 | 1.0 | 0.0 | 112.0 | 2 |
| prestador_concentrado | 5 | 1.0 | -0.014 | 0.0 | 0.0 | 132.0 | 2 |

## Consulta 6

```sql
SELECT 'flag_documento' AS tipo, f AS valor, count(*) AS avisos
FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos LATERAL VIEW explode(flags_documento) t AS f GROUP BY ALL
UNION ALL
SELECT 'alerta_qualidade', a, count(*)
FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos LATERAL VIEW explode(alertas_qualidade) t AS a GROUP BY ALL
ORDER BY tipo, avisos DESC
```

| tipo | valor | avisos |
|---|---|---|
| alerta_qualidade | sem_estacao_no_raio | 547 |
| flag_documento | preco_acima_referencia | 25 |
| flag_documento | menciona_dano_anterior | 9 |

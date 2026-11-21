# Gold do evento: cobertura, status dos pareceres, fast track por padrão e KPIs

Executado em 2026-11-21 13:16 com `uv run python scripts/registrar_evidencia.py src/governanca/94_conferir_gold.sql` (catálogo e schemas lidos do `.env`; D-016).

## Consulta 1

```sql
SELECT (SELECT count(*) FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos) AS avisos_silver,
  count(*) AS linhas_gold, count(DISTINCT id_aviso) AS avisos_distintos_gold,
  (SELECT count(*) FROM fe_bar_sinistros_catalog.silver.sinistros_enriquecidos s
   LEFT ANTI JOIN fe_bar_sinistros_catalog.gold.sinistros_analisados g ON g.id_aviso = s.id_aviso) AS avisos_sem_analise
FROM fe_bar_sinistros_catalog.gold.sinistros_analisados
```

| avisos_silver | linhas_gold | avisos_distintos_gold | avisos_sem_analise |
|---|---|---|---|
| 8000 | 7612 | 7612 | 388 |

## Consulta 2

```sql
SELECT status_parecer, llm, versao_prompt, versao_modelo, count(*) AS avisos, max(tentativas_parecer) AS max_tentativas
FROM fe_bar_sinistros_catalog.gold.sinistros_analisados GROUP BY ALL ORDER BY avisos DESC
```

| status_parecer | llm | versao_prompt | versao_modelo | avisos | max_tentativas |
|---|---|---|---|---|---|
| ok | databricks-claude-haiku-5-5 | 2 | 3 | 7607 | 3 |
| invalido | databricks-claude-haiku-5-5 | 2 | 3 | 5 | 2 |

## Consulta 3

```sql
SELECT gb.padrao, count(*) AS avisos,
  round(100 * avg(CASE WHEN g.fast_track THEN 1.0 ELSE 0.0 END), 1) AS pct_fast_track,
  round(100 * avg(CASE WHEN g.recomendacao_ia = gb.decisao_esperada THEN 1.0 ELSE 0.0 END), 1) AS pct_parecer_igual_gabarito,
  round(100 * avg(CASE WHEN g.score_suspeita >= 0.2 THEN 1.0 ELSE 0.0 END), 1) AS pct_score_bloqueia
FROM fe_bar_sinistros_catalog.gold.sinistros_analisados g
JOIN read_files('/Volumes/fe_bar_sinistros_catalog/ml/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) gb
  ON gb.id_aviso = g.id_aviso
GROUP BY gb.padrao ORDER BY gb.padrao
```

| padrao | avisos | pct_fast_track | pct_parecer_igual_gabarito | pct_score_bloqueia |
|---|---|---|---|---|
| apolice_recente | 147 | 0.0 | 100.0 | 97.3 |
| dano_preexistente | 154 | 0.0 | 100.0 | 100.0 |
| legitimo_complexo | 1888 | 0.8 | 99.0 | 1.2 |
| legitimo_simples | 4584 | 89.4 | 99.7 | 0.3 |
| orcamento_inflado | 303 | 0.0 | 100.0 | 100.0 |
| prestador_concentrado | 74 | 18.9 | 68.9 | 68.9 |
| sem_cobertura | 224 | 0.0 | 100.0 | 100.0 |
| sem_evento_climatico | 238 | 0.0 | 97.9 | 97.9 |

## Consulta 4

```sql
SELECT motivo, count(*) AS avisos
FROM fe_bar_sinistros_catalog.gold.sinistros_analisados LATERAL VIEW explode(bloqueios_fast_track) t AS motivo
GROUP BY motivo ORDER BY avisos DESC
```

| motivo | avisos |
|---|---|
| valor_acima_do_teto | 3122 |
| recomendacao_nao_integral | 1392 |
| score_suspeita | 1142 |
| preco_acima_referencia | 303 |
| evidencia_nao_forte | 249 |
| sem_cobertura | 224 |
| dano_anterior | 158 |
| preco_nao_conferido | 38 |
| parecer_nao_ok | 5 |
| extracao_falhou | 2 |

## Consulta 5

```sql
SELECT * FROM fe_bar_sinistros_catalog.gold.kpis_evento ORDER BY lote NULLS LAST
```

| lote | avisos | valor_reclamado | fast_track | pct_fast_track | valor_pago_fast_track | rec_pagar_integral | rec_pagar_parcial | rec_recusar | rec_investigar | ajuste_por_evidencia | pareceres_pendentes | score_medio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 800 | 8899899.55 | 388 | 0.485 | 879461.11 | 581 | 63 | 16 | 140 | 380012.85 | 0 | 0.2245 |
| 2 | 800 | 9226599.46 | 444 | 0.555 | 961199.6 | 683 | 75 | 18 | 24 | 533214.04 | 0 | 0.1056 |
| 3 | 800 | 8952791.73 | 457 | 0.5713 | 964414.35 | 677 | 74 | 26 | 23 | 603912.89 | 0 | 0.1257 |
| 4 | 800 | 9810896.09 | 437 | 0.5463 | 932738.17 | 671 | 79 | 25 | 25 | 457915.06 | 0 | 0.121 |
| 5 | 800 | 9441609.02 | 449 | 0.5613 | 970904.04 | 686 | 62 | 25 | 27 | 522470.39 | 0 | 0.1197 |
| 6 | 800 | 9232625.37 | 444 | 0.555 | 931678.09 | 667 | 76 | 32 | 25 | 569929.43 | 2 | 0.1403 |
| 7 | 800 | 9353461.41 | 448 | 0.56 | 977605.76 | 661 | 77 | 24 | 38 | 465582.51 | 2 | 0.1379 |
| 8 | 800 | 1.021138273E7 | 376 | 0.47 | 839136.88 | 581 | 77 | 21 | 121 | 463570.86 | 1 | 0.2359 |
| 9 | 800 | 9197314.54 | 439 | 0.5488 | 943314.89 | 663 | 82 | 24 | 31 | 563733.94 | 0 | 0.1349 |
| 10 | 412 | 4317868.14 | 243 | 0.5898 | 520755.49 | 350 | 37 | 13 | 12 | 255056.12 | 0 | 0.13 |
|  | 7612 | 8.864444804E7 | 4125 | 0.5419 | 8921208.38 | 6220 | 702 | 224 | 466 | 4815398.09 | 5 | 0.1484 |

## Consulta 6

```sql
SELECT posicao_fila, id_aviso, municipio, causa_declarada, valor_reclamado, round(score_suspeita, 3) AS score,
  recomendacao_ia, prioridade, bloqueios_fast_track
FROM fe_bar_sinistros_catalog.gold.fila_regulacao WHERE posicao_fila <= 10 ORDER BY posicao_fila
```

| posicao_fila | id_aviso | municipio | causa_declarada | valor_reclamado | score | recomendacao_ia | prioridade | bloqueios_fast_track |
|---|---|---|---|---|---|---|---|---|
| 1 | AV-2026-006744 | Arabutã | vendaval | 50950.7 | 1.0 | recusar | 0.9999 | ["valor_acima_do_teto","sem_cobertura","score_suspeita","recomendacao_nao_integral"] |
| 2 | AV-2026-003522 | Biguaçu | vendaval | 58765.12 | 1.0 | recusar | 0.9998 | ["valor_acima_do_teto","sem_cobertura","score_suspeita","recomendacao_nao_integral"] |
| 3 | AV-2026-005580 | Florianópolis | alagamento | 56927.99 | 1.0 | recusar | 0.9998 | ["valor_acima_do_teto","sem_cobertura","score_suspeita","recomendacao_nao_integral"] |
| 4 | AV-2026-002758 | Florianópolis | alagamento | 73374.41 | 0.999 | recusar | 0.9997 | ["valor_acima_do_teto","sem_cobertura","score_suspeita","recomendacao_nao_integral"] |
| 5 | AV-2026-004757 | Biguaçu | vendaval | 57466.41 | 0.999 | recusar | 0.9997 | ["valor_acima_do_teto","sem_cobertura","score_suspeita","recomendacao_nao_integral"] |
| 6 | AV-2026-002981 | Florianópolis | alagamento | 51333.98 | 0.999 | recusar | 0.9996 | ["valor_acima_do_teto","sem_cobertura","score_suspeita","recomendacao_nao_integral"] |
| 7 | AV-2026-006901 | Seara | granizo | 56486.79 | 0.999 | pagar_parcial | 0.9996 | ["valor_acima_do_teto","score_suspeita","recomendacao_nao_integral","preco_acima_referencia"] |
| 8 | AV-2026-002534 | Florianópolis | alagamento | 86418.7 | 0.999 | recusar | 0.9995 | ["valor_acima_do_teto","sem_cobertura","score_suspeita","recomendacao_nao_integral"] |
| 9 | AV-2026-003494 | Florianópolis | granizo | 63206.67 | 0.999 | recusar | 0.9995 | ["valor_acima_do_teto","sem_cobertura","score_suspeita","recomendacao_nao_integral"] |
| 10 | AV-2026-003896 | Florianópolis | granizo | 56705.3 | 0.999 | investigar | 0.9995 | ["valor_acima_do_teto","score_suspeita","recomendacao_nao_integral"] |

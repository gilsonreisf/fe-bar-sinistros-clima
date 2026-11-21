# Teste final: lotes do evento nunca vistos no treino nem na avaliação

Gerado em 2026-11-21 09:43 com `uv run python scripts/avaliar_teste_final.py`. Lotes: 2, 3, 4, 5 (2420 avisos). Fonte: `gold.sinistros_analisados` produzido pelo `job_evento` (score do `modelo_suspeita@champion`, parecer do prompt de produção, regras de fast track); o gabarito só é lido aqui.

## Score de suspeita × linha de base de regras

| métrica | modelo | regras |
|---|---|---|
| AUC | 0.9917 | 0.9519 |
| suspeitos com score < 0,2 (escapariam do bloqueio) | 0.05882 | 0.09343 |
| legítimos com score < 0,2 | 0.9916 | 0.9972 |
| precisão nos 10% do topo | 0.9959 | 0.9752 |
| recall nos 10% do topo | 0.8339 | 0.8166 |
| teto do recall nos 10% do topo | 0.8374 | 0.8374 |
| elegíveis ao fast track (≤ R$ 5 mil, cobertura, evidência forte) | 1392 | 1392 |
| suspeitos elegíveis | 35 | 35 |
| suspeitos elegíveis liberados | 10 | 13 |

## Parecer prévio (todos os avisos dos lotes)

- Recomendação igual à do gabarito: **98.6%**
- Valor sugerido a ±10% do devido (pagamentos esperados): **99.7%**
- Pareceres com status `ok`: 99.9%

## Fast track

- 1347 de 2420 avisos no fast track (**55,7%**). com R$ 2.871.967,59 pagos sem regulador
- Suspeitos que entraram no fast track: **9** (R$ 18.997,47)

## Por padrão

| padrao | avisos | parecer_correto | score_bloqueia | fast_track |
|---|---|---|---|---|
| apolice_recente | 39 | 1.0 | 0.974 | 0.0 |
| dano_preexistente | 52 | 1.0 | 1.0 | 0.0 |
| legitimo_complexo | 633 | 0.987 | 0.017 | 0.006 |
| legitimo_simples | 1498 | 0.994 | 0.005 | 0.891 |
| orcamento_inflado | 95 | 1.0 | 1.0 | 0.0 |
| prestador_concentrado | 27 | 0.407 | 0.407 | 0.333 |
| sem_cobertura | 69 | 1.0 | 1.0 | 0.0 |
| sem_evento_climatico | 7 | 1.0 | 1.0 | 0.0 |

## Por lote (o prestador concentrado só aparece com histórico de 30 dias)

| lote | avisos | suspeitos | suspeitos_liberados_pelo_score | prestador_concentrado_bloqueado | pct_fast_track |
|---|---|---|---|---|---|
| 2 | 800.0 | 83.0 | 6.0 | 0.0 | 0.552 |
| 3 | 800.0 | 108.0 | 10.0 | 0.286 | 0.571 |
| 4 | 800.0 | 96.0 | 1.0 | 0.875 | 0.546 |
| 5 | 20.0 | 2.0 | 0.0 |  | 0.55 |

# Teste final: lotes do evento nunca vistos no treino nem na avaliação

Gerado em 2026-11-21 13:16 com `uv run python scripts/avaliar_teste_final.py`. Lotes: 2, 3, 4, 5, 6, 7, 8, 9, 10 (6812 avisos). Fonte: `gold.sinistros_analisados` produzido pelo `job_evento` (score do `modelo_suspeita@champion`, parecer do prompt de produção, regras de fast track); o gabarito só é lido aqui.

## Score de suspeita × linha de base de regras

| métrica | modelo | regras |
|---|---|---|
| AUC | 0.9971 | 0.9618 |
| suspeitos com score < 0,2 (escapariam do bloqueio) | 0.02516 | 0.07442 |
| legítimos com score < 0,2 | 0.9954 | 0.9981 |
| precisão nos 10% do topo | 0.9956 | 0.9853 |
| recall nos 10% do topo | 0.7117 | 0.7044 |
| teto do recall nos 10% do topo | 0.7149 | 0.7149 |
| elegíveis ao fast track (≤ R$ 5 mil, cobertura, evidência forte) | 3857 | 3857 |
| suspeitos elegíveis | 94 | 94 |
| suspeitos elegíveis liberados | 15 | 33 |

## Parecer prévio (todos os avisos dos lotes)

- Recomendação igual à do gabarito: **99.4%**
- Valor sugerido a ±10% do devido (pagamentos esperados): **99.6%**
- Pareceres com status `ok`: 99.9%

## Fast track

- 3737 de 6812 avisos no fast track (**54,9%**). com R$ 8.041.747,27 pagos sem regulador
- Suspeitos que entraram no fast track: **11** (R$ 23.317,97)

## Por padrão

| padrao | avisos | parecer_correto | score_bloqueia | fast_track |
|---|---|---|---|---|
| apolice_recente | 134 | 1.0 | 0.97 | 0.0 |
| dano_preexistente | 145 | 1.0 | 1.0 | 0.0 |
| legitimo_complexo | 1710 | 0.992 | 0.01 | 0.009 |
| legitimo_simples | 4148 | 0.998 | 0.002 | 0.895 |
| orcamento_inflado | 278 | 1.0 | 1.0 | 0.0 |
| prestador_concentrado | 69 | 0.739 | 0.739 | 0.159 |
| sem_cobertura | 208 | 1.0 | 1.0 | 0.0 |
| sem_evento_climatico | 120 | 0.983 | 0.983 | 0.0 |

## Por lote (o prestador concentrado só aparece com histórico de 30 dias)

| lote | avisos | suspeitos | suspeitos_liberados_pelo_score | prestador_concentrado_bloqueado | pct_fast_track |
|---|---|---|---|---|---|
| 2 | 800.0 | 83.0 | 6.0 | 0.0 | 0.555 |
| 3 | 800.0 | 108.0 | 10.0 | 0.286 | 0.571 |
| 4 | 800.0 | 96.0 | 1.0 | 0.875 | 0.546 |
| 5 | 800.0 | 93.0 | 0.0 | 1.0 | 0.561 |
| 6 | 800.0 | 110.0 | 2.0 | 1.0 | 0.555 |
| 7 | 800.0 | 110.0 | 1.0 | 1.0 | 0.56 |
| 8 | 800.0 | 190.0 | 1.0 | 1.0 | 0.47 |
| 9 | 800.0 | 109.0 | 2.0 | 0.889 | 0.549 |
| 10 | 412.0 | 55.0 | 1.0 | 0.75 | 0.59 |

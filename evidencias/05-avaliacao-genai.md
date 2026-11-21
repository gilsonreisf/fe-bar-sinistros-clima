# Parecer prévio por IA: avaliação com MLflow (v1 × v2), portão e registro

Gerado em 2026-11-21 00:51 com `uv run python scripts/evidencia_parecer.py <task_run_id>`, a partir do job `job_avaliacao_parecer` (notebook `notebooks/avaliacao_parecer.py`; saídas em `notebooks/saidas/avaliacao_parecer.ipynb`).

## Configuração

- Dataset de avaliação (MLflow Evaluation Dataset no UC): `fe_bar_sinistros_catalog.ml.avaliacao_parecer_dataset`, 143 casos estratificados por padrão dos lotes de validação do evento.
- Prompt versionado no UC (tabela Delta; o Prompt Registry não está habilitado no workspace, D-022): `fe_bar_sinistros_catalog.ml.prompt_parecer`. Versões avaliadas: v1 = v1, v2 = v2. Alias `producao` → **v2** (promovido nesta execução: True).
- Modelo registrado: `fe_bar_sinistros_catalog.ml.parecer_sinistro` versão **1** (aliases: producao), com o prompt de produção congelado.
- Endpoint: `sinistros-clima-parecer-dev` (criado), com AI Gateway (inference table e usage tracking) e tracing; teste em `evidencias/05-endpoint-parecer.md`.
- Runs do MLflow: v1 `5ccfd16aba64499892c4a9f51173a2fa`, v2 `19cc0327ff4a444b84d73f037fb22828`, registro `1e2b16de8ab342d18095d1e4492d2840`.

## Métricas (v1 × v2)

| métrica | o que mede | v1 | v2 |
|---|---|---|---|
| `casos_pagamento_esperado` | casos com pagamento esperado | 84.000 | 84.000 |
| `cita_clausula/mean` | cita a cláusula esperada | 0.951 | 0.951 |
| `correctness/mean` | juiz LLM: fatos esperados presentes | 0.664 | 0.930 |
| `diretrizes_parecer/mean` | juiz LLM: diretrizes (português formal, sem recusa sem evidência, tom) | 0.685 | 0.923 |
| `json_valido/mean` | JSON válido na primeira ou na segunda tentativa | 0.986 | 1.000 |
| `padrao_identificado/mean` | motivos citam o fato que caracteriza o padrão | 0.895 | 0.993 |
| `recomendacao_correta/mean` | recomendação igual à do gabarito | 0.664 | 0.951 |
| `valor_dentro_tolerancia_pagamentos` | valor sugerido a ±10% do devido (casos com pagamento esperado) | 0.583 | 1.000 |

## Acurácia da recomendação por padrão (v1)

| padrao | casos | acuracia |
|---|---|---|
| apolice_recente | 13 | 1.0 |
| dano_preexistente | 9 | 0.778 |
| legitimo_complexo | 25 | 0.24 |
| legitimo_simples | 25 | 0.4 |
| orcamento_inflado | 25 | 0.72 |
| prestador_concentrado | 5 | 0.0 |
| sem_cobertura | 16 | 1.0 |
| sem_evento_climatico | 25 | 1.0 |

## Acurácia da recomendação por padrão (v2)

| padrao | casos | acuracia |
|---|---|---|
| apolice_recente | 13 | 1.0 |
| dano_preexistente | 9 | 1.0 |
| legitimo_complexo | 25 | 0.96 |
| legitimo_simples | 25 | 1.0 |
| orcamento_inflado | 25 | 1.0 |
| prestador_concentrado | 5 | 0.0 |
| sem_cobertura | 16 | 1.0 |
| sem_evento_climatico | 25 | 0.96 |

## Divergências do prompt v2 em relação ao gabarito

Apólices com menos de 30 dias vão para `investigar` pela cláusula CG-2.4 (análise de contratação recente), mesmo quando o gabarito diz que o sinistro é legítimo: é uma divergência de política, não de leitura.

| id_aviso | padrao | esperado | obtido | dias_desde_contratacao | motivos |
|---|---|---|---|---|---|
| AV-2026-000748 | prestador_concentrado | investigar | pagar_integral | 44.0 | Causa declarada (vendaval) enquadrada na cobertura de vendaval e granizo contratada, com cobertura válida na apólice AP-0036055 | Evento de 28/08/2026 confirmado por registro da Defesa Civil em Florianópolis (evidência forte), apesar de não haver estação meteorológica no raio | Laudo de vistoria de  |
| AV-2026-000301 | prestador_concentrado | investigar | pagar_integral | 94.0 | Cobertura de vendaval e granizo contratada e válida para a causa declarada (granizo), com LMI de R$ 42.000,00 e franquia de R$ 1.000,00 | Evento de 28/08/2026 confirmado por registro da Defesa Civil em Florianópolis (evidência forte); a ausência de estação meteorológica no raio não afasta a comprova |
| AV-2026-000714 | prestador_concentrado | investigar | pagar_integral | 132.0 | Causa declarada (vendaval) corresponde à cobertura de vendaval e granizo contratada na apólice AP-0054687, com LMI de R$ 427.000,00 e franquia de R$ 2.000,00 | Evento de 28/08/2026 em São José do Cedro com evidência forte, confirmado por registro da Defesa Civil; o alerta de ausência de estação no r |
| AV-2026-000071 | legitimo_complexo | pagar_integral | investigar | 19.0 | O sinistro ocorreu em 07/08/2026, 19 dias após o início da vigência (19/07/2026), dentro dos primeiros 30 dias. Por isso exige análise de contratação e de preexistência antes de qualquer indenização. | A cobertura de danos elétricos está contratada (LMI de R$ 15.000,00 e franquia de R$ 300,00), e a  |
| AV-2026-000784 | prestador_concentrado | investigar | pagar_integral | 292.0 | Causa declarada (granizo) coberta pela apólice AP-0052968, com a cobertura de vendaval e granizo contratada (LMI de R$ 424.000,00 e franquia de R$ 2.000,00) | Evento de 28/08/2026 confirmado por registro da Defesa Civil em Florianópolis (evidência forte); o alerta de ausência de estação meteorológic |
| AV-2026-000215 | sem_evento_climatico | investigar | pagar_integral | 243.0 | Cobertura de vendaval e granizo contratada na apólice AP-0039768 (LMI de R$ 42.000,00 e franquia de R$ 1.000,00), compatível com a causa declarada (granizo) | Não há evidência climática comprobatória: a força é fraca, sem fonte e sem registro da Defesa Civil, e não há estação no raio (a mais próxima |
| AV-2026-000747 | prestador_concentrado | investigar | pagar_integral | 221.0 | Causa declarada (granizo) coberta pela cobertura de vendaval e granizo contratada (LMI de R$ 103.000,00 e franquia de R$ 1.000,00) | Evento confirmado com evidência forte por registro da Defesa Civil em Florianópolis; o alerta de ausência de estação no raio não afeta a comprovação | Laudo de vistori |

# Comparação de LLMs no parecer prévio (mesmo dataset, prompt v2)

Gerado em 2026-11-21 00:52 com `uv run python scripts/evidencia_parecer.py comparacao <task_run_id>=<llm> ...`, a partir do job de avaliação no modo `publicar=nao` (avalia sem mexer no prompt, no modelo nem no endpoint).

| métrica | o que mede | `databricks-claude-sonnet-5-5` | `databricks-claude-haiku-5-5` |
|---|---|---|---|
| `casos_pagamento_esperado` | casos com pagamento esperado | 84.000 | 84.000 |
| `cita_clausula/mean` | cita a cláusula esperada | 0.951 | 0.951 |
| `correctness/mean` | juiz LLM: fatos esperados presentes | 0.930 | 0.930 |
| `diretrizes_parecer/mean` | juiz LLM: diretrizes (português formal, sem recusa sem evidência, tom) | 0.923 | 0.874 |
| `json_valido/mean` | JSON válido na primeira ou na segunda tentativa | 1.000 | 1.000 |
| `padrao_identificado/mean` | motivos citam o fato que caracteriza o padrão | 0.993 | 0.965 |
| `recomendacao_correta/mean` | recomendação igual à do gabarito | 0.951 | 0.951 |
| `valor_dentro_tolerancia_pagamentos` | valor sugerido a ±10% do devido (casos com pagamento esperado) | 1.000 | 1.000 |

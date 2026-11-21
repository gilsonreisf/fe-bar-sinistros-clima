# Genie "Sinistros Clima — Diretoria": benchmarks

Gerado em 2026-11-21 10:02 com `uv run python scripts/genie_diretoria.py`, pela avaliação de benchmarks do Genie (modo chat: compara o resultado do SQL gerado com o do SQL de referência).

- Fontes: metric views `sinistros_metrics` e `regulacao_metrics` e a visão `fila_regulacao`, todas do gold.
- Instruções de negócio: 8 regras; 3 exemplos de SQL (diferentes dos benchmarks).
- **Resultado: 16 de 16 benchmarks corretos** (status da execução: DONE).

| pergunta | avaliação | SQL gerado pelo Genie | motivo |
|---|---|---|---|
| Como se divide a exposição entre residencial e empresarial? | GOOD | `SELECT `Ramo`, MEASURE(`Valor reclamado`) AS `valor_reclamado` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` WHERE `Ramo` IS NOT NULL AND (`Ramo` ILIKE '%residencial%' OR `Ramo` ILIKE '%empresarial%') GROUP BY ALL ORDER BY `valor_reclamado` DESC` |  |
| Quantos sinistros são suspeitos e quanto eles reclamam? | GOOD | `SELECT MEASURE(`Sinistros suspeitos`) AS `sinistros_suspeitos`, MEASURE(`Valor reclamado suspeito`) AS `valor_reclamado_suspeito` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` GROUP BY ALL` |  |
| Quais são os 10 sinistros mais prioritários da fila? | GOOD | `SELECT `posicao_fila`, `id_aviso`, `lote`, `data_aviso`, `municipio`, `causa_declarada`, `valor_reclamado`, `score_suspeita`, `recomendacao_ia`, `valor_sugerido`, `confianca`, `status_parecer`, `prioridade`, `forca_evidencia_climatica`, `fonte_evidencia`, `cobertura_valida` FROM `fe_bar_sinistros_catalog`.`gold`.`fila_regulacao` WHERE `posicao_fila` IS NOT NULL ORDER BY `posicao_fila` ASC LIMIT 10` |  |
| Quanto já foi liberado pelo fast track? | GOOD | `SELECT MEASURE(`Valor liberado no fast track`) AS `valor_liberado_fast_track` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` GROUP BY ALL` |  |
| Quantos sinistros não têm evidência climática forte? | GOOD | `SELECT MEASURE(`Avisos`) AS `sinistros_sem_evidencia_forte` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` WHERE `Força da evidência climática` IS NOT NULL AND `Força da evidência climática` <> 'forte' GROUP BY ALL` |  |
| Qual a taxa de concordância dos reguladores com a IA? | GOOD | `SELECT MEASURE(`Concordância com a IA`) AS `taxa_concordancia` FROM `fe_bar_sinistros_catalog`.`gold`.`regulacao_metrics` GROUP BY ALL` |  |
| Qual a exposição total do evento, em valor reclamado? | GOOD | `SELECT MEASURE(`Valor reclamado`) AS `valor_reclamado_total` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` GROUP BY ALL` |  |
| Quais os 5 municípios com maior valor reclamado? | GOOD | `SELECT `Município`, MEASURE(`Valor reclamado`) AS `valor_reclamado` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` WHERE `Município` IS NOT NULL GROUP BY ALL ORDER BY `valor_reclamado` DESC LIMIT 5` |  |
| Quantos sinistros estão na fila do regulador? | GOOD | `SELECT MEASURE(`Na fila do regulador`) AS `sinistros_na_fila` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` GROUP BY ALL` |  |
| Quanto de pagamento indevido a IA ajudou a evitar? | GOOD | `SELECT MEASURE(`Ajuste sugerido pela IA`) AS `ajuste_sugerido_pela_ia` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` GROUP BY ALL` |  |
| Qual o score médio de suspeita por causa declarada? | GOOD | `SELECT `Causa declarada`, MEASURE(`Score médio de suspeita`) AS `score_medio_suspeita` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` WHERE `Causa declarada` IS NOT NULL GROUP BY ALL ORDER BY `score_medio_suspeita` DESC` |  |
| Quantos pareceres a IA deu de cada tipo de recomendação? | GOOD | `SELECT `Recomendação da IA`, MEASURE(`Avisos`) AS `pareceres` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` WHERE `Recomendação da IA` IS NOT NULL GROUP BY ALL ORDER BY `pareceres` DESC` |  |
| Quantos avisos temos por causa declarada? | GOOD | `SELECT `Causa declarada`, MEASURE(`Avisos`) AS `avisos` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` WHERE `Causa declarada` IS NOT NULL GROUP BY ALL ORDER BY `avisos` DESC` |  |
| Qual o percentual de sinistros liberados no fast track? | GOOD | `SELECT MEASURE(`Percentual de fast track`) AS `percentual_fast_track` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` GROUP BY ALL` |  |
| Qual o percentual de fast track em cada lote? | GOOD | `SELECT `Lote`, MEASURE(`Percentual de fast track`) AS `percentual_fast_track` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` WHERE `Lote` IS NOT NULL GROUP BY ALL ORDER BY `Lote` ASC` |  |
| Quantos avisos de sinistro recebemos no evento? | GOOD | `SELECT MEASURE(`Avisos`) AS `avisos` FROM `fe_bar_sinistros_catalog`.`gold`.`sinistros_metrics` GROUP BY ALL` |  |

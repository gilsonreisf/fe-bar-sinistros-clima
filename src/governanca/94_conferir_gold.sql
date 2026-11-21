-- Conferência da fase 5: o gold tem uma linha por aviso, sem duplicata nem aviso esquecido; status dos pareceres;
-- fast track por padrão do gabarito (o gabarito é lido só aqui, para conferir); KPIs do evento.
SELECT (SELECT count(*) FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos) AS avisos_silver,
  count(*) AS linhas_gold, count(DISTINCT id_aviso) AS avisos_distintos_gold,
  (SELECT count(*) FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos s
   LEFT ANTI JOIN ${catalogo}.${schema_gold}.sinistros_analisados g ON g.id_aviso = s.id_aviso) AS avisos_sem_analise
FROM ${catalogo}.${schema_gold}.sinistros_analisados;

SELECT status_parecer, llm, versao_prompt, versao_modelo, count(*) AS avisos, max(tentativas_parecer) AS max_tentativas
FROM ${catalogo}.${schema_gold}.sinistros_analisados GROUP BY ALL ORDER BY avisos DESC;

SELECT gb.padrao, count(*) AS avisos,
  round(100 * avg(CASE WHEN g.fast_track THEN 1.0 ELSE 0.0 END), 1) AS pct_fast_track,
  round(100 * avg(CASE WHEN g.recomendacao_ia = gb.decisao_esperada THEN 1.0 ELSE 0.0 END), 1) AS pct_parecer_igual_gabarito,
  round(100 * avg(CASE WHEN g.score_suspeita >= 0.2 THEN 1.0 ELSE 0.0 END), 1) AS pct_score_bloqueia
FROM ${catalogo}.${schema_gold}.sinistros_analisados g
JOIN read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) gb
  ON gb.id_aviso = g.id_aviso
GROUP BY gb.padrao ORDER BY gb.padrao;

SELECT motivo, count(*) AS avisos
FROM ${catalogo}.${schema_gold}.sinistros_analisados LATERAL VIEW explode(bloqueios_fast_track) t AS motivo
GROUP BY motivo ORDER BY avisos DESC;

SELECT * FROM ${catalogo}.${schema_gold}.kpis_evento ORDER BY lote NULLS LAST;

SELECT posicao_fila, id_aviso, municipio, causa_declarada, valor_reclamado, round(score_suspeita, 3) AS score,
  recomendacao_ia, prioridade, bloqueios_fast_track
FROM ${catalogo}.${schema_gold}.fila_regulacao WHERE posicao_fila <= 10 ORDER BY posicao_fila;

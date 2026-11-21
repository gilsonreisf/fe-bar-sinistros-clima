-- Conferência da fase 3: as features do modelo de suspeita têm o mesmo significado no histórico (treino) e no evento.
-- O gabarito é lido SÓ aqui, para conferir; o pipeline e o treino de features nunca o leem (spec 4.2).
SELECT 'silver' AS camada, 'historico_enriquecido' AS tabela, count(*) AS linhas FROM ${catalogo}.${schema_silver}.historico_enriquecido
UNION ALL SELECT 'silver', 'evidencia_climatica_historico', count(*) FROM ${catalogo}.${schema_silver}.evidencia_climatica_historico
UNION ALL SELECT 'silver', 'sinistros_enriquecidos', count(*) FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos;

-- Histórico 2025, por padrão do gabarito
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
FROM ${catalogo}.${schema_silver}.historico_enriquecido h
JOIN read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_historico_2025.csv', format => 'csv', header => true) g
  ON g.id_sinistro = h.id_sinistro
GROUP BY g.padrao ORDER BY g.padrao;

-- Evento 2026 (lotes publicados), mesmas colunas
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
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos s
JOIN read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) g
  ON g.id_aviso = s.id_aviso
GROUP BY g.padrao ORDER BY g.padrao;

-- Lacunas: sinistros sem evidência calculada, sem desvio de preço ou sem LMI apesar da cobertura
SELECT 'historico' AS base,
  sum(CASE WHEN e.id_sinistro IS NULL THEN 1 ELSE 0 END) AS sem_linha_de_evidencia,
  sum(CASE WHEN h.desvio_preco_pct IS NULL THEN 1 ELSE 0 END) AS sem_desvio,
  sum(CASE WHEN h.cobertura_valida AND h.lmi IS NULL THEN 1 ELSE 0 END) AS cobertura_sem_lmi,
  sum(CASE WHEN NOT h.cobertura_valida AND h.lmi IS NOT NULL THEN 1 ELSE 0 END) AS lmi_sem_cobertura
FROM ${catalogo}.${schema_silver}.historico_enriquecido h
LEFT JOIN ${catalogo}.${schema_silver}.evidencia_climatica_historico e ON e.id_sinistro = h.id_sinistro
UNION ALL
SELECT 'evento',
  sum(CASE WHEN e.id_aviso IS NULL THEN 1 ELSE 0 END),
  sum(CASE WHEN s.desvio_preco_pct IS NULL THEN 1 ELSE 0 END),
  sum(CASE WHEN s.cobertura_valida AND s.lmi IS NULL THEN 1 ELSE 0 END),
  sum(CASE WHEN NOT s.cobertura_valida AND s.lmi IS NOT NULL THEN 1 ELSE 0 END)
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos s
LEFT JOIN ${catalogo}.${schema_silver}.evidencia_climatica e ON e.id_aviso = s.id_aviso;

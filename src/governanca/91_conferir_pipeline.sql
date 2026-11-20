-- Conferência da fase 2: volumes por camada, leitura e extração dos documentos e paridade com o gabarito.
SELECT 'bronze' AS camada, 'avisos' AS tabela, count(*) AS linhas FROM ${catalogo}.${schema_bronze}.avisos
UNION ALL SELECT 'bronze', 'documentos', count(*) FROM ${catalogo}.${schema_bronze}.documentos
UNION ALL SELECT 'bronze', 'apolices', count(*) FROM ${catalogo}.${schema_bronze}.apolices
UNION ALL SELECT 'bronze', 'apolices_coberturas', count(*) FROM ${catalogo}.${schema_bronze}.apolices_coberturas
UNION ALL SELECT 'bronze', 'segurados', count(*) FROM ${catalogo}.${schema_bronze}.segurados
UNION ALL SELECT 'bronze', 'clima_inmet', count(*) FROM ${catalogo}.${schema_bronze}.clima_inmet
UNION ALL SELECT 'bronze', 'historico_sinistros', count(*) FROM ${catalogo}.${schema_bronze}.historico_sinistros
UNION ALL SELECT 'silver', 'avisos', count(*) FROM ${catalogo}.${schema_silver}.avisos
UNION ALL SELECT 'silver', 'documentos_extraidos', count(*) FROM ${catalogo}.${schema_silver}.documentos_extraidos
UNION ALL SELECT 'silver', 'clima_estacao_dia', count(*) FROM ${catalogo}.${schema_silver}.clima_estacao_dia
UNION ALL SELECT 'silver', 'evidencia_climatica', count(*) FROM ${catalogo}.${schema_silver}.evidencia_climatica
UNION ALL SELECT 'silver', 'sinistros_enriquecidos', count(*) FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos;

SELECT tipo_documento, count(*) AS documentos, sum(CAST(legivel AS INT)) AS legiveis,
  sum(CAST(erro_extracao IS NOT NULL AS INT)) AS erros_extracao
FROM ${catalogo}.${schema_silver}.documentos_extraidos GROUP BY tipo_documento ORDER BY tipo_documento;

SELECT g.forca_evidencia_esperada, s.forca_evidencia_climatica, g.fonte_evidencia_esperada, s.fonte_evidencia, count(*) AS avisos
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos s
JOIN read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) g
  ON g.id_aviso = s.id_aviso
GROUP BY ALL ORDER BY avisos DESC;

WITH gab AS (
  SELECT id_aviso, round(sum(CAST(valor_total AS DOUBLE)), 2) AS total_gabarito, count(*) AS itens_gabarito
  FROM read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_itens_evento_2026.csv', format => 'csv', header => true)
  GROUP BY id_aviso
)
SELECT count(*) AS avisos,
  round(100 * avg(CASE WHEN abs(r.valor_orcamento - gab.total_gabarito) <= 0.01 THEN 1.0 ELSE 0.0 END), 1) AS pct_total_exato,
  round(100 * avg(CASE WHEN r.itens_extraidos = gab.itens_gabarito THEN 1.0 ELSE 0.0 END), 1) AS pct_qtd_itens_exata,
  round(100 * sum(r.itens_casados) / sum(r.itens_extraidos), 1) AS pct_itens_casados_com_preco
FROM ${catalogo}.${schema_silver}.documentos_resumo r JOIN gab ON gab.id_aviso = r.id_aviso;

SELECT g.padrao, count(*) AS avisos,
  round(avg(CAST(s.cobertura_valida AS INT)), 2) AS pct_cobertura_valida,
  round(avg(s.desvio_preco_pct), 3) AS desvio_preco_medio,
  round(avg(CAST(array_contains(s.flags_documento, 'menciona_dano_anterior') AS INT)), 2) AS pct_dano_anterior,
  round(avg(CAST(array_contains(s.flags_documento, 'preco_acima_referencia') AS INT)), 2) AS pct_preco_acima,
  percentile(s.dias_desde_contratacao, 0.5) AS mediana_dias_contratacao,
  max(s.qtd_orcamentos_prestador) AS max_orcamentos_prestador
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos s
JOIN read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) g
  ON g.id_aviso = s.id_aviso
GROUP BY g.padrao ORDER BY avisos DESC;

SELECT 'flag_documento' AS tipo, f AS valor, count(*) AS avisos
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos LATERAL VIEW explode(flags_documento) t AS f GROUP BY ALL
UNION ALL
SELECT 'alerta_qualidade', a, count(*)
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos LATERAL VIEW explode(alertas_qualidade) t AS a GROUP BY ALL
ORDER BY tipo, avisos DESC;

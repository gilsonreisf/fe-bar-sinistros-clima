-- Silver: sinistros regulados em 2025 (base de treino do modelo de suspeita), com as MESMAS colunas de entrada do
-- evento (silver.sinistros_enriquecidos) e pelas mesmas regras. Decisão, valor pago e motivo ficam de fora (vazam o rótulo).
CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.historico_enriquecido
COMMENT 'Histórico 2025 enriquecido para o treino: mesmas features do evento (evidência, desvio de preço, prestador).'
AS WITH h AS (
  SELECT id_sinistro, to_date(data_ocorrencia) AS data_ocorrencia, to_date(data_aviso) AS data_aviso, causa_declarada,
    CAST(valor_reclamado AS DOUBLE) AS valor_reclamado, canal, CAST(codigo_ibge AS INT) AS codigo_ibge, municipio,
    id_prestador, ramo, CAST(cobertura_contratada AS BOOLEAN) AS cobertura_valida,
    -- como no evento: sem a cobertura da causa, não há LMI nem franquia (o join com a cobertura não casa)
    CASE WHEN CAST(cobertura_contratada AS BOOLEAN) THEN CAST(lmi_cobertura AS DOUBLE) END AS lmi,
    CASE WHEN CAST(cobertura_contratada AS BOOLEAN) THEN CAST(franquia AS DOUBLE) END AS franquia,
    datediff(to_date(data_ocorrencia), to_date(inicio_vigencia)) AS dias_desde_contratacao,
    -- no evento, o equivalente é o laudo lido por IA (menciona_dano_anterior)
    coalesce(CAST(menciona_preexistente AS BOOLEAN), false) AS menciona_dano_anterior
  FROM ${catalogo}.${schema_bronze}.historico_sinistros
),
precos AS (
  SELECT lower(regexp_replace(trim(descricao), '\\s+', ' ')) AS chave, CAST(preco_referencia AS DOUBLE) AS preco_referencia
  FROM ${catalogo}.${schema_bronze}.precos_referencia
),
desvio AS (
  SELECT i.id_sinistro, count(*) AS itens, count(p.preco_referencia) AS itens_casados,
    round(sum(CASE WHEN p.preco_referencia IS NOT NULL THEN CAST(i.quantidade AS DOUBLE) * CAST(i.valor_unitario AS DOUBLE) END)
          / sum(CAST(i.quantidade AS DOUBLE) * p.preco_referencia) - 1, 4) AS desvio_preco_pct
  FROM ${catalogo}.${schema_bronze}.historico_itens i
  LEFT JOIN precos p ON p.chave = lower(regexp_replace(trim(i.descricao), '\\s+', ' '))
  GROUP BY i.id_sinistro
),
-- Participação do prestador point-in-time (D-020/D-021): só avisos ANTERIORES ao dia do aviso, janela de 30 dias
dia_total AS (SELECT data_aviso AS dia, count(*) AS n FROM h GROUP BY data_aviso),
dia_prestador AS (SELECT id_prestador, data_aviso AS dia, count(*) AS n FROM h GROUP BY id_prestador, data_aviso),
janela_total AS (
  SELECT k.data_aviso, sum(t.n) AS avisos_janela
  FROM (SELECT DISTINCT data_aviso FROM h) k
  JOIN dia_total t ON t.dia >= date_sub(k.data_aviso, 30) AND t.dia < k.data_aviso
  GROUP BY k.data_aviso
),
janela_prestador AS (
  SELECT k.id_prestador, k.data_aviso, sum(p.n) AS avisos_prestador
  FROM (SELECT DISTINCT id_prestador, data_aviso FROM h) k
  JOIN dia_prestador p ON p.id_prestador = k.id_prestador AND p.dia >= date_sub(k.data_aviso, 30) AND p.dia < k.data_aviso
  GROUP BY k.id_prestador, k.data_aviso
)
SELECT h.id_sinistro, h.data_ocorrencia, h.data_aviso, h.causa_declarada, h.valor_reclamado, h.canal, h.codigo_ibge,
  h.municipio, h.id_prestador, h.ramo, h.cobertura_valida, h.lmi, h.franquia, h.dias_desde_contratacao,
  h.menciona_dano_anterior,
  coalesce(e.forca_evidencia_climatica, 'fraca') AS forca_evidencia_climatica,
  coalesce(e.fonte_evidencia, 'nenhuma') AS fonte_evidencia,
  e.distancia_estacao_km, e.chuva_mm, e.chuva_max_hora_mm, e.rajada_max_ms,
  d.itens, d.itens_casados, d.desvio_preco_pct,
  -- suavizada: (avisos do prestador + 1) / (avisos na janela + 2000); janela pequena não exagera (D-021)
  round((coalesce(avisos_prestador, 0) + 1.0) / (coalesce(avisos_janela, 0) + 2000), 6) AS participacao_prestador_30d
FROM h
LEFT JOIN ${catalogo}.${schema_silver}.evidencia_climatica_historico e ON e.id_sinistro = h.id_sinistro
LEFT JOIN desvio d ON d.id_sinistro = h.id_sinistro
LEFT JOIN janela_total jt ON jt.data_aviso = h.data_aviso
LEFT JOIN janela_prestador jp ON jp.id_prestador = h.id_prestador AND jp.data_aviso = h.data_aviso;

-- Silver: o sinistro enriquecido, com o aviso cruzado com a apólice, a evidência climática e os documentos.
-- Expectations só medem (warn): nenhum aviso é descartado em silêncio, e toda falha vai para o regulador (spec 10.3).
CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.sinistros_enriquecidos (
  CONSTRAINT apolice_existente EXPECT (apolice_existe),
  CONSTRAINT ocorrencia_na_vigencia EXPECT (dentro_vigencia),
  CONSTRAINT datas_coerentes EXPECT (coalesce(data_ocorrencia <= data_aviso, false)),
  CONSTRAINT valor_positivo EXPECT (coalesce(valor_reclamado > 0, false)),
  CONSTRAINT documento_lido EXPECT (NOT array_contains(flags_documento, 'documento_ilegivel')),
  CONSTRAINT estacao_no_raio EXPECT (coalesce(distancia_estacao_km <= 30, false))
)
COMMENT 'Sinistro enriquecido: aviso + apólice e cobertura + evidência climática (duas fontes) + documentos e preços.'
AS WITH apolice AS (
  SELECT DISTINCT id_apolice, ramo, inicio_vigencia, fim_vigencia
  FROM ${catalogo}.${schema_silver}.apolices_coberturas
),
base AS (
  SELECT a.*, ap.ramo, ap.inicio_vigencia, ap.fim_vigencia,
    CASE a.causa_declarada
      WHEN 'granizo' THEN 'vendaval_granizo'
      WHEN 'vendaval' THEN 'vendaval_granizo'
      ELSE a.causa_declarada
    END AS cobertura_necessaria
  FROM ${catalogo}.${schema_silver}.avisos a
  LEFT JOIN apolice ap ON ap.id_apolice = a.id_apolice
),
prestador AS (
  -- contagem no evento inteiro: informativa para o app; fora do modelo porque muda a cada lote (D-020)
  SELECT id_prestador, count(*) AS qtd_orcamentos_prestador
  FROM ${catalogo}.${schema_silver}.avisos
  GROUP BY id_prestador
),
-- Participação do prestador point-in-time (D-020/D-021), igual à do histórico: só avisos de dias ANTERIORES ao
-- aviso, numa janela de 30 dias; lotes chegam em ordem de data_aviso, então um lote novo não muda valores já pontuados
dia_total AS (SELECT data_aviso AS dia, count(*) AS n FROM ${catalogo}.${schema_silver}.avisos GROUP BY data_aviso),
dia_prestador AS (
  SELECT id_prestador, data_aviso AS dia, count(*) AS n FROM ${catalogo}.${schema_silver}.avisos GROUP BY id_prestador, data_aviso
),
janela_total AS (
  SELECT k.data_aviso, sum(t.n) AS avisos_janela
  FROM (SELECT DISTINCT data_aviso FROM ${catalogo}.${schema_silver}.avisos) k
  JOIN dia_total t ON t.dia >= date_sub(k.data_aviso, 30) AND t.dia < k.data_aviso
  GROUP BY k.data_aviso
),
janela_prestador AS (
  SELECT k.id_prestador, k.data_aviso, sum(p.n) AS avisos_prestador
  FROM (SELECT DISTINCT id_prestador, data_aviso FROM ${catalogo}.${schema_silver}.avisos) k
  JOIN dia_prestador p ON p.id_prestador = k.id_prestador AND p.dia >= date_sub(k.data_aviso, 30) AND p.dia < k.data_aviso
  GROUP BY k.id_prestador, k.data_aviso
),
juntos AS (
  SELECT b.*,
    b.inicio_vigencia IS NOT NULL AS apolice_existe,
    c.lmi IS NOT NULL AS cobertura_valida, c.lmi, c.franquia,
    datediff(b.data_ocorrencia, b.inicio_vigencia) AS dias_desde_contratacao,
    coalesce(b.data_ocorrencia BETWEEN b.inicio_vigencia AND b.fim_vigencia, false) AS dentro_vigencia,
    e.forca_evidencia_climatica, e.fonte_evidencia, e.distancia_estacao_km, e.registro_defesa_civil,
    e.chuva_mm, e.chuva_max_hora_mm, e.rajada_max_ms, e.granizo_provavel,
    r.valor_orcamento, coalesce(r.itens_extraidos, 0) AS itens_extraidos, coalesce(r.itens_casados, 0) AS itens_casados,
    r.desvio_preco_pct, r.tem_orcamento, r.tem_ilegivel, r.laudo_dano_anterior, r.extracao_falhou, r.docs_recebidos,
    p.qtd_orcamentos_prestador, jt.avisos_janela, jp.avisos_prestador
  FROM base b
  LEFT JOIN ${catalogo}.${schema_silver}.apolices_coberturas c
    ON c.id_apolice = b.id_apolice AND c.cobertura = b.cobertura_necessaria
  LEFT JOIN ${catalogo}.${schema_silver}.evidencia_climatica e ON e.id_aviso = b.id_aviso
  LEFT JOIN ${catalogo}.${schema_silver}.documentos_resumo r ON r.id_aviso = b.id_aviso
  LEFT JOIN prestador p ON p.id_prestador = b.id_prestador
  LEFT JOIN janela_total jt ON jt.data_aviso = b.data_aviso
  LEFT JOIN janela_prestador jp ON jp.id_prestador = b.id_prestador AND jp.data_aviso = b.data_aviso
)
SELECT
  id_aviso, id_apolice, cpf_segurado, data_ocorrencia, data_aviso, causa_declarada, descricao, valor_reclamado, canal,
  codigo_ibge, municipio, lat, lon, id_prestador, documentos, ramo, cobertura_necessaria, apolice_existe,
  cobertura_valida, lmi, franquia, inicio_vigencia, dias_desde_contratacao, dentro_vigencia,
  coalesce(forca_evidencia_climatica, 'fraca') AS forca_evidencia_climatica,
  coalesce(fonte_evidencia, 'nenhuma') AS fonte_evidencia,
  distancia_estacao_km, registro_defesa_civil, chuva_mm, chuva_max_hora_mm, rajada_max_ms, granizo_provavel,
  valor_orcamento, itens_extraidos, itens_casados, desvio_preco_pct, qtd_orcamentos_prestador,
  -- features do modelo de suspeita com o mesmo significado de silver.historico_enriquecido (D-021)
  coalesce(laudo_dano_anterior = 1, false) AS menciona_dano_anterior,
  -- suavizada: (avisos do prestador + 1) / (avisos na janela + 2000); janela pequena não exagera (D-021).
  -- CAST para DOUBLE: com o literal 1.0 o Spark devolvia DECIMAL, recusado pela assinatura do modelo
  round(CAST(coalesce(avisos_prestador, 0) + 1 AS DOUBLE) / (coalesce(avisos_janela, 0) + 2000), 6) AS participacao_prestador_30d,
  filter(array(
    CASE WHEN coalesce(tem_orcamento, 0) = 0 THEN 'sem_orcamento' END,
    CASE WHEN tem_ilegivel = 1 THEN 'documento_ilegivel' END,
    CASE WHEN laudo_dano_anterior = 1 THEN 'menciona_dano_anterior' END,
    CASE WHEN abs(valor_orcamento - valor_reclamado) > 0.01 * greatest(1.0, valor_reclamado) THEN 'valor_divergente' END,
    CASE WHEN desvio_preco_pct >= 0.30 THEN 'preco_acima_referencia' END,
    -- revisão #1: falhas que não podem deixar o sinistro parecer limpo (spec 10.3)
    CASE WHEN extracao_falhou = 1 THEN 'extracao_falhou' END,
    CASE WHEN tem_orcamento = 1 AND desvio_preco_pct IS NULL THEN 'preco_nao_conferido' END,
    CASE WHEN coalesce(docs_recebidos, 0) < size(documentos) THEN 'documento_ausente' END
  ), x -> x IS NOT NULL) AS flags_documento,
  filter(array(
    CASE WHEN NOT apolice_existe THEN 'apolice_inexistente' END,
    CASE WHEN apolice_existe AND NOT dentro_vigencia THEN 'fora_vigencia' END,
    CASE WHEN NOT coalesce(data_ocorrencia <= data_aviso, false) THEN 'datas_incoerentes' END,
    CASE WHEN NOT coalesce(valor_reclamado > 0, false) THEN 'valor_invalido' END,
    CASE WHEN causa_declarada IS NULL OR causa_declarada NOT IN ('granizo', 'vendaval', 'alagamento', 'danos_eletricos') THEN 'causa_desconhecida' END,
    CASE WHEN distancia_estacao_km IS NULL OR distancia_estacao_km > 30 THEN 'sem_estacao_no_raio' END
  ), x -> x IS NOT NULL) AS alertas_qualidade
FROM juntos;

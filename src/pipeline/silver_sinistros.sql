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
  SELECT id_prestador, count(*) AS qtd_orcamentos_prestador
  FROM ${catalogo}.${schema_silver}.avisos
  GROUP BY id_prestador
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
    p.qtd_orcamentos_prestador
  FROM base b
  LEFT JOIN ${catalogo}.${schema_silver}.apolices_coberturas c
    ON c.id_apolice = b.id_apolice AND c.cobertura = b.cobertura_necessaria
  LEFT JOIN ${catalogo}.${schema_silver}.evidencia_climatica e ON e.id_aviso = b.id_aviso
  LEFT JOIN ${catalogo}.${schema_silver}.documentos_resumo r ON r.id_aviso = b.id_aviso
  LEFT JOIN prestador p ON p.id_prestador = b.id_prestador
)
SELECT
  id_aviso, id_apolice, cpf_segurado, data_ocorrencia, data_aviso, causa_declarada, descricao, valor_reclamado, canal,
  codigo_ibge, municipio, lat, lon, id_prestador, documentos, ramo, cobertura_necessaria, apolice_existe,
  cobertura_valida, lmi, franquia, inicio_vigencia, dias_desde_contratacao, dentro_vigencia,
  coalesce(forca_evidencia_climatica, 'fraca') AS forca_evidencia_climatica,
  coalesce(fonte_evidencia, 'nenhuma') AS fonte_evidencia,
  distancia_estacao_km, registro_defesa_civil, chuva_mm, chuva_max_hora_mm, rajada_max_ms, granizo_provavel,
  valor_orcamento, itens_extraidos, itens_casados, desvio_preco_pct, qtd_orcamentos_prestador,
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

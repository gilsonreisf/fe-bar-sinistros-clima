-- Silver: entrada do parecer prévio por IA (spec 6.2), um JSON por sinistro com o que o regulador olharia: aviso,
-- apólice e coberturas, evidência climática (duas fontes), documentos (itens com preço de referência e trecho do
-- laudo), prestador e alertas. Usada pela avaliação, pelo gold e pelo app (D-022). Nenhum rótulo entra aqui.
CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.entrada_parecer
COMMENT 'Entrada do parecer prévio por IA: sinistro enriquecido, coberturas, evidência, itens com preço de referência e laudo, em JSON.'
AS WITH coberturas AS (
  SELECT id_apolice, collect_list(named_struct('cobertura', cobertura, 'lmi', lmi, 'franquia', franquia)) AS coberturas
  FROM ${catalogo}.${schema_silver}.apolices_coberturas
  GROUP BY id_apolice
),
precos AS (
  SELECT lower(regexp_replace(trim(descricao), '\\s+', ' ')) AS chave, CAST(preco_referencia AS DOUBLE) AS preco_referencia
  FROM ${catalogo}.${schema_bronze}.precos_referencia
),
itens_orcamento AS (
  -- LATERAL VIEW não pode vir antes de um JOIN no Spark SQL: primeiro explode, depois junta com a tabela de preços
  SELECT d.id_aviso, i.descricao, i.quantidade, i.unidade, i.valor_unitario, i.valor_total
  FROM ${catalogo}.${schema_silver}.documentos_extraidos d
  LATERAL VIEW explode(d.itens) t AS i
  WHERE d.tipo_documento = 'orcamento' AND d.legivel
),
itens AS (
  SELECT it.id_aviso,
    collect_list(named_struct('descricao', it.descricao, 'quantidade', it.quantidade, 'unidade', it.unidade,
      'valor_unitario', it.valor_unitario, 'valor_total', it.valor_total, 'preco_referencia', p.preco_referencia)) AS itens
  FROM itens_orcamento it
  LEFT JOIN precos p ON p.chave = lower(regexp_replace(trim(it.descricao), '\\s+', ' '))
  GROUP BY it.id_aviso
),
laudo AS (
  -- trecho limitado: o laudo sintético é curto, e o limite protege o custo do prompt com laudos reais longos
  SELECT id_aviso, substr(concat_ws('\n', collect_list(texto)), 1, 3000) AS texto_laudo
  FROM ${catalogo}.${schema_silver}.documentos_texto
  WHERE tipo_documento = 'laudo'
  GROUP BY id_aviso
)
SELECT s.id_aviso,
  to_json(named_struct(
    'aviso', named_struct('id_aviso', s.id_aviso, 'data_ocorrencia', s.data_ocorrencia, 'data_aviso', s.data_aviso,
      'causa_declarada', s.causa_declarada, 'descricao', s.descricao, 'valor_reclamado', s.valor_reclamado,
      'municipio', s.municipio, 'canal', s.canal),
    'apolice', named_struct('id_apolice', s.id_apolice, 'ramo', s.ramo, 'inicio_vigencia', s.inicio_vigencia,
      'dias_desde_contratacao', s.dias_desde_contratacao, 'cobertura_necessaria', s.cobertura_necessaria,
      'cobertura_valida', s.cobertura_valida, 'lmi', s.lmi, 'franquia', s.franquia,
      'coberturas_contratadas', c.coberturas),
    'evidencia_climatica', named_struct('forca', s.forca_evidencia_climatica, 'fonte', s.fonte_evidencia,
      'registro_defesa_civil', s.registro_defesa_civil, 'distancia_estacao_km', s.distancia_estacao_km,
      'chuva_mm', s.chuva_mm, 'chuva_max_hora_mm', s.chuva_max_hora_mm, 'rajada_max_ms', s.rajada_max_ms,
      'granizo_provavel', s.granizo_provavel),
    'documentos', named_struct('valor_orcamento', s.valor_orcamento, 'desvio_preco_pct', s.desvio_preco_pct,
      'menciona_dano_anterior', s.menciona_dano_anterior, 'flags', s.flags_documento, 'itens', i.itens,
      'laudo', l.texto_laudo),
    'prestador', named_struct('id_prestador', s.id_prestador, 'participacao_prestador_30d', s.participacao_prestador_30d),
    'alertas_qualidade', s.alertas_qualidade
  )) AS entrada_json
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos s
LEFT JOIN coberturas c ON c.id_apolice = s.id_apolice
LEFT JOIN itens i ON i.id_aviso = s.id_aviso
LEFT JOIN laudo l ON l.id_aviso = s.id_aviso;

-- Silver: texto dos PDFs (ai_parse_document) e campos estruturados (ai_extract). Cada PDF é processado uma única vez
-- (streaming). Documento ilegível vira flag, não erro (spec 10.3).
CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_silver}.documentos_texto
COMMENT 'Texto de cada PDF do aviso, extraído com ai_parse_document (sem descrições de imagem, para reduzir custo).'
AS SELECT
  regexp_extract(_arquivo, '(AV-[0-9]{4}-[0-9]{6})_', 1) AS id_aviso,
  regexp_extract(_arquivo, '_(orcamento|laudo)[.]pdf$', 1) AS tipo_documento,
  _arquivo,
  concat_ws('\n', transform(try_cast(parsed:document:elements AS ARRAY<VARIANT>), e -> e:content::STRING)) AS texto,
  -- error_status é uma lista por página; vazia (ou ausente) significa leitura sem erro
  CASE WHEN size(try_cast(parsed:error_status AS ARRAY<VARIANT>)) > 0 THEN parsed:error_status::STRING END AS erro_leitura,
  _ingerido_em
FROM (
  SELECT _arquivo, _ingerido_em,
    ai_parse_document(content, map('version', '2.0', 'descriptionElementTypes', '')) AS parsed
  FROM STREAM(${catalogo}.${schema_bronze}.documentos)
);

CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_silver}.documentos_extraidos
COMMENT 'Campos estruturados de orçamentos e laudos (ai_extract): prestador, itens, valores e menção a dano anterior.'
AS SELECT
  id_aviso, tipo_documento, _arquivo, legivel,
  -- ai_extract 2.1 devolve cada valor como {"value": ...}; try_variant_get deixa nulo o que faltar, sem derrubar o stream
  try_variant_get(extraido, '$.response.nome_prestador.value', 'STRING') AS nome_prestador,
  try_variant_get(extraido, '$.response.cnpj_prestador.value', 'STRING') AS cnpj_prestador,
  try_variant_get(extraido, '$.response.valor_total.value', 'DOUBLE') AS valor_total,
  try_variant_get(extraido, '$.response.menciona_dano_anterior.value', 'BOOLEAN') AS menciona_dano_anterior,
  transform(try_cast(extraido:response:itens AS ARRAY<VARIANT>), i -> named_struct(
    'descricao', try_variant_get(i, '$.descricao.value', 'STRING'),
    'quantidade', try_variant_get(i, '$.quantidade.value', 'DOUBLE'),
    'unidade', try_variant_get(i, '$.unidade.value', 'STRING'),
    'valor_unitario', try_variant_get(i, '$.valor_unitario.value', 'DOUBLE'),
    'valor_total', try_variant_get(i, '$.valor_total.value', 'DOUBLE'))) AS itens,
  extraido:error_message::STRING AS erro_extracao,
  _ingerido_em
FROM (
  SELECT *,
    CASE WHEN legivel THEN ai_extract(
      texto,
      '{"nome_prestador": {"type": "string"}, "cnpj_prestador": {"type": "string"}, "valor_total": {"type": "number"}, "menciona_dano_anterior": {"type": "boolean"}, "itens": {"type": "array", "items": {"type": "object", "properties": {"descricao": {"type": "string"}, "quantidade": {"type": "number"}, "unidade": {"type": "string"}, "valor_unitario": {"type": "number"}, "valor_total": {"type": "number"}}}}}',
      map('version', '2.1', 'instructions',
        'Documentos de sinistro residencial no Brasil: orçamentos de reparo e laudos de vistoria, em português. Valores em reais no formato brasileiro: R$ 1.925,00 significa 1925.00. Em orçamentos, itens traz uma linha por item. A descrição é o nome do item ou serviço copiado exatamente como está no documento, incluindo o texto entre parênteses, mas sem a quantidade e sem a unidade (em 95 m de Reparo de fiação elétrica (padrão economico), a descrição é Reparo de fiação elétrica (padrão economico), a quantidade é 95 e a unidade é m). valor_total é o total do orçamento. Em laudos, não há itens nem valor_total, e menciona_dano_anterior é true somente se o texto indicar dano anterior ao evento.')
    ) END AS extraido
  FROM (
    SELECT *, (erro_leitura IS NULL AND length(trim(texto)) > 20) AS legivel
    FROM STREAM(${catalogo}.${schema_silver}.documentos_texto)
  )
);

CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.documentos_resumo
COMMENT 'Resumo dos documentos de cada aviso: valor do orçamento, itens casados com a tabela de preços e desvio de preço.'
AS WITH docs AS (
  SELECT id_aviso,
    max(CASE WHEN tipo_documento = 'orcamento' AND legivel THEN 1 ELSE 0 END) AS tem_orcamento,
    max(CASE WHEN NOT legivel THEN 1 ELSE 0 END) AS tem_ilegivel,
    max(CASE WHEN tipo_documento = 'laudo' AND legivel AND menciona_dano_anterior THEN 1 ELSE 0 END) AS laudo_dano_anterior,
    max(CASE WHEN tipo_documento = 'orcamento' AND legivel THEN valor_total END) AS valor_orcamento
  FROM ${catalogo}.${schema_silver}.documentos_extraidos
  GROUP BY id_aviso
),
itens AS (
  SELECT d.id_aviso, i.descricao, i.quantidade, i.valor_unitario
  FROM ${catalogo}.${schema_silver}.documentos_extraidos d
  LATERAL VIEW explode(d.itens) t AS i
  WHERE d.tipo_documento = 'orcamento' AND d.legivel
),
precos AS (
  SELECT lower(regexp_replace(trim(descricao), '\\s+', ' ')) AS chave, CAST(preco_referencia AS DOUBLE) AS preco_referencia
  FROM ${catalogo}.${schema_bronze}.precos_referencia
),
casados AS (
  SELECT it.id_aviso,
    count(*) AS itens_extraidos,
    count(p.preco_referencia) AS itens_casados,
    sum(CASE WHEN p.preco_referencia IS NOT NULL THEN it.quantidade * it.valor_unitario END) AS valor_casado,
    sum(it.quantidade * p.preco_referencia) AS valor_referencia
  FROM itens it
  LEFT JOIN precos p ON p.chave = lower(regexp_replace(trim(it.descricao), '\\s+', ' '))
  GROUP BY it.id_aviso
)
SELECT d.id_aviso, d.tem_orcamento, d.tem_ilegivel, d.laudo_dano_anterior, d.valor_orcamento,
  coalesce(c.itens_extraidos, 0) AS itens_extraidos, coalesce(c.itens_casados, 0) AS itens_casados,
  round(c.valor_casado / c.valor_referencia - 1, 4) AS desvio_preco_pct
FROM docs d
LEFT JOIN casados c ON c.id_aviso = d.id_aviso;

-- Silver: avisos tipados. As violações viram métricas de qualidade e não descartam o aviso (spec 5 e 10.3).
CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_silver}.avisos (
  CONSTRAINT valor_positivo EXPECT (valor_reclamado > 0),
  CONSTRAINT datas_coerentes EXPECT (data_ocorrencia <= data_aviso),
  CONSTRAINT tem_documento EXPECT (size(documentos) > 0),
  CONSTRAINT causa_conhecida EXPECT (causa_declarada IN ('granizo', 'vendaval', 'alagamento', 'danos_eletricos')),
  CONSTRAINT sem_campo_resgatado EXPECT (_rescued_data IS NULL)
)
COMMENT 'Avisos de sinistro tipados, um por linha, como chegaram do canal (app, corretor ou central).'
AS SELECT
  id_aviso, id_apolice, cpf_segurado,
  to_date(data_ocorrencia) AS data_ocorrencia,
  to_date(data_aviso) AS data_aviso,
  causa_declarada, descricao, valor_reclamado, canal, codigo_ibge, municipio, lat, lon, id_prestador, documentos,
  _rescued_data, _arquivo, _ingerido_em
FROM STREAM(${catalogo}.${schema_bronze}.avisos);

-- Silver: apólices com coberturas e ocorrências da Defesa Civil ligadas ao código IBGE.
CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.apolices_coberturas
COMMENT 'Apólice com cada cobertura contratada (LMI e franquia): uma linha por apólice e cobertura.'
AS SELECT
  a.id_apolice, a.id_segurado, a.id_corretor, a.ramo, CAST(a.codigo_ibge AS INT) AS codigo_ibge, a.municipio,
  to_date(a.inicio_vigencia) AS inicio_vigencia, to_date(a.fim_vigencia) AS fim_vigencia,
  CAST(a.premio_anual AS DOUBLE) AS premio_anual,
  c.cobertura, CAST(c.lmi AS DOUBLE) AS lmi, CAST(c.franquia AS DOUBLE) AS franquia
FROM ${catalogo}.${schema_bronze}.apolices a
JOIN ${catalogo}.${schema_bronze}.apolices_coberturas c ON c.id_apolice = a.id_apolice;

CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.ocorrencias_defesa_civil (
  CONSTRAINT municipio_reconhecido EXPECT (codigo_ibge IS NOT NULL)
)
COMMENT 'Ocorrências da Defesa Civil de SC por município e episódio, com o código IBGE (segunda fonte de evidência; D-015).'
AS SELECT
  o.episodio, to_date(o.data_inicio) AS data_inicio, to_date(o.data_fim) AS data_fim, o.municipio,
  CAST(m.codigo_ibge AS INT) AS codigo_ibge, CAST(o.moradias_atingidas AS INT) AS moradias_atingidas, o.fonte_url
FROM ${catalogo}.${schema_bronze}.ocorrencias_defesa_civil o
LEFT JOIN ${catalogo}.${schema_bronze}.municipios m ON m.municipio = o.municipio;

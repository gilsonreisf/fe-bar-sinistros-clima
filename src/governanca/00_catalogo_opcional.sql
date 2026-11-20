-- Opcional: cria o catálogo onde o usuário tem CREATE CATALOG no metastore.
-- No FEVM não há essa permissão; lá o catálogo já vem criado com o workspace (D-016).
CREATE CATALOG IF NOT EXISTS ${catalogo}
  COMMENT 'FE Bar: regulação inteligente de sinistros em eventos climáticos. Dados sintéticos e públicos.';

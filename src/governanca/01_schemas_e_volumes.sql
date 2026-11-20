-- Schemas e volumes do projeto (idempotente). O catálogo precisa existir (veja 00_catalogo_opcional.sql).
-- Os nomes vêm do módulo `ambiente` (FE_BAR_CATALOGO e FE_BAR_PREFIXO_SCHEMA).
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_landing}
  COMMENT 'Arquivos brutos recebidos (avisos, documentos, apólices, clima, referências).';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_bronze}
  COMMENT 'Dados ingeridos como chegaram, com metadados de ingestão.';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_silver}
  COMMENT 'Dados limpos, tipados, extraídos dos documentos e cruzados com apólice e clima.';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_gold}
  COMMENT 'Sinistros analisados, fila de regulação, KPIs e metric views.';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_ml}
  COMMENT 'Modelos, prompts, features, gabarito e avaliações.';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_operacional}
  COMMENT 'Histórico das tabelas operacionais do Lakebase (Lakehouse Sync).';
CREATE VOLUME IF NOT EXISTS ${catalogo}.${schema_landing}.arquivos
  COMMENT 'Arquivos brutos, uma pasta por entidade: avisos/, documentos/, apolices/, segurados/, clima_horario/, historico_sinistros/ etc.';
CREATE VOLUME IF NOT EXISTS ${catalogo}.${schema_ml}.restrito
  COMMENT 'Gabarito dos dados sintéticos. Acesso restrito; nunca lido pelo pipeline de features.';
SHOW SCHEMAS IN ${catalogo};

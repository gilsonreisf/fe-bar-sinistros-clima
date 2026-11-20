-- Sanidade de leitura do Volume no warehouse (tarefa 1.11). Uma pasta por entidade (D-018).
SELECT 'apolices' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/${catalogo}/${schema_landing}/arquivos/apolices/', format => 'csv', header => true);
SELECT 'segurados' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/${catalogo}/${schema_landing}/arquivos/segurados/', format => 'csv', header => true);
SELECT 'historico' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/${catalogo}/${schema_landing}/arquivos/historico_sinistros/', format => 'csv', header => true);
SELECT 'clima_2026' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/${catalogo}/${schema_landing}/arquivos/clima_horario/inmet_sc_horario_2026.csv', format => 'csv', header => true);
SELECT 'gabarito_evento' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true);
COMMENT ON VOLUME ${catalogo}.${schema_landing}.arquivos IS 'Arquivos brutos, uma pasta por entidade: avisos/, documentos/, apolices/, segurados/, clima_horario/, historico_sinistros/ etc.';

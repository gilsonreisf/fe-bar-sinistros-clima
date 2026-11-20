# Recursos do bundle

Um arquivo YAML por recurso (pipeline, jobs, app, endpoint, experimentos), incluídos por `databricks.yml`.
Nomes de catálogo e schema nunca ficam fixos: use `${var.catalogo}` e `${var.prefixo_schema}<camada>` (D-016).
O que o DAB não suporta é criado por `scripts/provisionar.py` (veja D-013, D-017 e as verificações em `evidencias/00a-verificacoes-ambiente.md`).
- `pipeline_sinistros.yml`: pipeline Lakeflow (bronze e silver) com a configuração `catalogo`, `schema_bronze`, `schema_silver` e `volume_arquivos`.

# Verificações do ambiente

Executado em 2026-11-20 19:20 pelo script `scripts/verificar_recursos.py`.

| Item | Status | Detalhe |
|---|---|---|
| SQL Warehouse | ✅ ok | Serverless Starter Warehouse (serverless=True) |
| Modelo fundacional Claude Sonnet (parecer) | ✅ ok | databricks-claude-sonnet-4-5, databricks-claude-sonnet-4-6, databricks-claude-sonnet-5, databricks-claude-sonnet-5-5 |
| ai_parse_document | ✅ ok | 360 caracteres extraídos |
| Políticas ABAC | ✅ ok | SHOW POLICIES executou |
| Lakebase (postgres API) e Lakehouse Sync | ✅ ok | 0 projetos; API de CDF (Lakehouse Sync) presente no SDK; ativação real na fase 6 |
| Recursos suportados pelo DAB | ✅ ok | presentes: pipelines, jobs, apps, model_serving_endpoints, experiments, registered_models, postgres_projects, postgres_synced_tables, synced_database_tables, database_instances, genie_spaces, dashboards, volumes, schemas; ausentes: nenhum |

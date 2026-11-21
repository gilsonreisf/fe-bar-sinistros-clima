# Regulação inteligente de sinistros em eventos climáticos

Protótipo para o **FE Bar**. Seguradoras de ramos patrimoniais (residencial e empresarial) recebem milhares de avisos de sinistro em poucos dias após enchentes, vendavais e granizo. Esta solução prioriza, pré-analisa e acelera cada sinistro com dados e IA na Databricks. O tempo até a indenização cai de semanas para dias e pagamentos indevidos são evitados.

> Todos os dados deste projeto são **sintéticos ou públicos**. Nenhum dado real de cliente é utilizado.

## Status

| Etapa | Situação |
|---|---|
| Caso de uso e problema de negócio | ✅ Definido |
| Desenho da solução (spec) | ✅ Aprovada (`docs/specs/`) |
| Plano de implementação | ✅ Roadmap + fases 0 e 1 aprovados, em execução (`docs/planos/`) |
| Build (Lakeflow → UC → Lakebase → ML/GenAI → Genie → App) | 🔄 Em andamento |
| Build: fase 0 (ambiente) | ✅ Concluída |
| Build: fase 1 (dados) | ✅ Concluída (`evidencias/00b-geracao-dados.md`, `evidencias/00c-conferencia-volume.md`) |
| Build: fase 2 (pipeline bronze e silver) | ✅ Concluída com o lote 1 (`evidencias/01-ingestao.md`); custo em `evidencias/09-custo-real.md` aguarda o faturamento |
| Build: fase 3 (modelo de suspeita) | ✅ LightGBM no UC com alias `champion`. Teste de 2025: AUC de 0,997 contra 0,960 da linha de base de regras, e 55% menos suspeitos liberados no fast track. Lote 1 do evento: AUC de 0,983 (`evidencias/04-ml.md`, D-021) |
| Build: fase 4 (parecer prévio por IA) | ✅ Prompt v2: 95,1% de recomendações corretas (contra 66,4% do v1) e 100% dos valores a ±10%. Endpoint com AI Gateway e tracing (`evidencias/05-*.md`, D-022) |
| Evidências de execução | 🔄 Fases 1 a 4 em `evidencias/` |
| Deck de apresentação | ⏳ Pendente |
| Ensaio do roleplay | ⏳ Pendente |

## Ambiente

- Workspace: FEVM serverless (AWS us-west-2), acessado pelo profile `fe-bar` da Databricks CLI.
- Variáveis locais: copie `.env.exemplo` para `.env` e preencha o ID do SQL Warehouse, o catálogo (`FE_BAR_CATALOGO`) e, se quiser, o prefixo dos schemas (`FE_BAR_PREFIXO_SCHEMA`). Nenhum nome de catálogo ou schema fica fixo no código (D-016).

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `docs/negocio/` | Problema de negócio, ganhos, KPIs e personas |
| `docs/dados/` | Análises das fontes de dados públicas (ex.: cobertura do INMET) |
| `docs/specs/` | Especificação de design da solução |
| `docs/planos/` | Roadmap e planos de implementação por fase |
| `docs/decisoes-e-tradeoffs.md` | Registro das decisões tomadas e alternativas descartadas |
| `src/ambiente/` | Nomes do catálogo, dos schemas e dos volumes, lidos do `.env` (nada fixo no código; D-016) |
| `src/regras/` | Regras de negócio compartilhadas pelo gerador, pelo pipeline e pelo modelo (clima, evidência de duas fontes e features do modelo de suspeita) |
| `src/ml/` | Treino, métricas e portão de promoção do modelo de suspeita, e o modelo MLflow servido (*models from code*) |
| `src/parecer/` | Parecer prévio por IA: cláusulas, prompts v1/v2, validação do JSON, valor calculado em código, avaliação, modelo servido e endpoint |
| `src/gold/` | Camada gold: sinistros analisados (score + parecer + fast track + prioridade), fila e KPIs |
| `src/dados_sinteticos/` | Leitores dos dados públicos, gerador sintético (cadastros, histórico, evento, PDFs) e gabarito |
| `src/pipeline/` | Pipeline Lakeflow (SDP): bronze com Auto Loader e silver com `ai_parse_document`, `ai_extract`, cruzamentos, evidência climática e as features do histórico de treino |
| `notebooks/` | Notebooks executados como jobs (fonte `.py`); em `notebooks/saidas/`, a execução com as saídas em texto (`.ipynb`) |
| `src/governanca/` | SQL do Unity Catalog (schemas, volumes, conferências), com placeholders `${catalogo}` e `${schema_<camada>}` |
| `scripts/` | Execução de SQL e registro de evidências, verificação do workspace, preparo dos dados públicos, publicação dos lotes do evento e do pacote Python usado pelo pipeline e pelos jobs, e exportação das execuções de notebooks e do modelo como evidência |
| `scripts/exploracao/` | Scripts de exploração das fontes de dados |
| `dados/publicos/` | Dados públicos curados (INMET, IBGE, Defesa Civil), com as fontes em `FONTES.md` |
| `dados/amostras/` | Amostras legíveis dos avisos gerados, por padrão |
| `evidencias/` | Evidências de execução em texto (verificações do ambiente, geração, conferência do Volume) |
| `testes/` | Testes automatizados (`uv run pytest`) |
| `databricks.yml`, `recursos/` | Bundle (DAB) com o target `dev` e as variáveis `catalogo` e `prefixo_schema`: pipeline, job de treino e experimento MLflow |
| `_interno/` | Material de apoio local, **não versionado** (veja `.gitignore`) |

Os scripts leem o `.env`. Antes de rodá-los, carregue as variáveis com `set -a; source .env; set +a`.

Deploy do pipeline e dos jobs: `PKG=$(uv run python scripts/publicar_pacote.py)` e, em seguida, `databricks bundle deploy -t dev --var warehouse_id=$FE_BAR_WAREHOUSE_ID --var pacote_python=$PKG` (D-019). Na primeira vez, crie a pasta do experimento MLflow: `databricks workspace mkdirs /Shared/sinistros_clima/dev`.

Treino do modelo de suspeita: `databricks bundle run -t dev job_treino_modelo` (mesmas variáveis do deploy). Em seguida, as evidências: `uv run python scripts/evidencia_modelo.py <task_run_id>` e `uv run python scripts/exportar_execucao.py <task_run_id> notebooks/saidas/treino_modelo_suspeita.ipynb`.

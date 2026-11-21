# Regulação inteligente de sinistros em eventos climáticos

Protótipo para o **FE Bar**. Seguradoras de ramos patrimoniais (residencial e empresarial) recebem milhares de avisos de sinistro em poucos dias depois de enchentes, vendavais e granizo. Esta solução prioriza, pré-analisa e acelera cada sinistro com dados e IA na Databricks. O tempo até a indenização cai de semanas para dias, e pagamentos indevidos são evitados.

> Todos os dados deste projeto são **sintéticos ou públicos** (clima do INMET, ocorrências da Defesa Civil de SC e municípios do IBGE). Nenhum dado real de cliente é usado.

## O problema e o valor

- **Hoje:** fila por ordem de chegada, regulador lendo PDF por PDF, cerca de 30 dias até a indenização, pagamento indevido no pico e prazo da SUSEP apertado (`docs/negocio/`).
- **Com a solução:** casos simples liberados sem fila (fast track), fila priorizada por suspeita, valor e espera, parecer prévio da IA ao lado das evidências e decisão do regulador medida contra a IA.
- **Ganho de referência, a calibrar na PoC:** cerca de R$ 2,4 milhões por evento de 8 mil avisos, somando *leakage* evitado e custo de regulação (`docs/negocio/02-ganhos-kpis-e-personas.md`).

## Resultados medidos (evento sintético de 8 mil avisos)

| O quê | Resultado | Evidência |
|---|---|---|
| Fast track | ~55% dos avisos liberados sem fila nos lotes de teste | `evidencias/04c-teste-final.md` |
| Modelo de suspeita × regra fixa (lotes nunca vistos) | AUC de 0,99 contra 0,95; menos suspeitos liberados no fast track | `evidencias/04c-teste-final.md`, `evidencias/04-ml.md` |
| Parecer prévio da IA (lotes nunca vistos) | ~98% de recomendações iguais ao gabarito; ~99,7% dos valores a ±10% | `evidencias/04c-teste-final.md` |
| Avaliação do prompt v1 × v2 | 66,4% → 95,1% de recomendações corretas, com juízes do MLflow | `evidencias/05-avaliacao-genai.md` |
| Genie da diretoria | 16 de 16 benchmarks corretos | `evidencias/06-genie.md` |
| Fila no Lakebase | Dois reguladores ao mesmo tempo, sem repetição; clique duplo sem duplicata | `evidencias/03-lakebase.md` |
| Custo por sinistro (pipeline + parecer) | ~US$ 0,006, referência a calibrar na PoC | `evidencias/09-custo-real.md` |

## Como funciona

Uma plataforma, do arquivo que chega ao lakehouse até a decisão do regulador, governada e rastreável no Unity Catalog:

**Lakeflow** (Auto Loader + `ai_parse_document`/`ai_extract`) → **Unity Catalog** (governança, LGPD, metric views) → **ML** (modelo de suspeita no UC) e **GenAI** (parecer avaliado e versionado, endpoint com AI Gateway) → **gold** → **Lakebase** (fila e decisões) → **App** (AppKit) e **Genie** → decisões de volta ao UC pelo **Lakehouse Sync**.

O desenho completo está em `docs/arquitetura.md`, o uso de IA (no produto e no build) em `docs/uso-de-ia.md` e o roteiro da demo em `docs/roteiro-demo.md`.

## Status

| Etapa | Situação |
|---|---|
| Caso de uso, problema de negócio e spec | ✅ `docs/negocio/`, `docs/specs/` |
| Fases 0 e 1: ambiente e dados | ✅ `evidencias/00*` |
| Fase 2: pipeline bronze e silver | ✅ `evidencias/01-ingestao.md` |
| Fase 3: modelo de suspeita | ✅ `evidencias/04-ml.md` (D-021) |
| Fase 4: parecer prévio e avaliação | ✅ `evidencias/05-*.md` (D-022) |
| Fase 5: gold, fast track e job do evento | ✅ `evidencias/04c-teste-final.md`, `evidencias/05c-gold.md` (D-023) |
| Fase 6: Lakebase | ✅ `evidencias/03-lakebase.md` (D-024) |
| Fase 7: governança, metric views e Genie | ✅ `evidencias/02-governanca.md`, `evidencias/06-genie.md` (D-025) |
| Fase 8: app | ✅ `evidencias/07-app.md` (D-026) |
| Fase 9: rastreio, custo e documentação | ✅ `evidencias/08-rastreio-ponta-a-ponta.md`, `evidencias/09-custo-real.md` |
| Próximo passo | Retreino com as decisões dos reguladores (o laço já fecha até a tela de supervisão); desvios da spec em D-027 |
| Deck e ensaio do roleplay | ⏳ Pendentes |

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `docs/negocio/` | Problema de negócio, ganhos, KPIs e personas |
| `docs/dados/` | Análises das fontes públicas (ex.: cobertura do INMET) |
| `docs/specs/`, `docs/planos/` | Especificação da solução e planos por fase |
| `docs/arquitetura.md`, `docs/uso-de-ia.md`, `docs/roteiro-demo.md` | Arquitetura, uso de IA e roteiro da demo |
| `docs/decisoes-e-tradeoffs.md` | Decisões tomadas (D-001 a D-027), alternativas descartadas e riscos |
| `src/ambiente/` | Nomes do catálogo, dos schemas e dos volumes, lidos do `.env` (nada fixo no código; D-016) |
| `src/regras/` | Regras de negócio compartilhadas: clima, evidência de duas fontes, features, fast track e prioridade |
| `src/pipeline/` | Pipeline Lakeflow (SDP): bronze com Auto Loader e silver com AI Functions e cruzamentos |
| `src/ml/` | Treino, métricas e portão de promoção do modelo de suspeita |
| `src/parecer/` | Parecer prévio: cláusulas, prompts, validação do JSON, valor em código, avaliação e endpoint |
| `src/gold/` | Gold: sinistros analisados, fila, KPIs, detalhe com CPF mascarado e processamento incremental |
| `src/lakebase/` | Schema `operacao` do Postgres e as consultas da fila e das decisões |
| `src/governanca/` | SQL do Unity Catalog: schemas, governança (`95`), metric views (`96`), conferências e custo |
| `src/dados_sinteticos/` | Gerador sintético (cadastros, histórico, evento, PDFs) e gabarito |
| `notebooks/` | Notebooks executados como jobs (fonte `.py`); em `notebooks/saidas/`, a execução com saídas (`.ipynb`) |
| `app/` | App AppKit (Node + React) com bundle próprio; veja `app/README.md` |
| `scripts/` | Provisão (Lakebase, Genie, permissões do app), simulação do evento, publicação do pacote e geração das evidências |
| `dados/publicos/`, `dados/amostras/` | Dados públicos curados (com `FONTES.md`) e amostras legíveis dos avisos |
| `evidencias/` | Evidências de execução em texto, de `00` a `09` |
| `testes/` | Testes automatizados (`uv run pytest`) |
| `databricks.yml`, `recursos/` | Bundle principal: pipeline, jobs (evento, treino, avaliação do parecer) e experimentos |
| `_interno/` | Material de apoio local, **não versionado** |

## Como reproduzir

Pré-requisitos: Databricks CLI com um profile, `uv` e Node 22. Copie `.env.exemplo` para `.env` e preencha o warehouse, o catálogo (`FE_BAR_CATALOGO`) e, se quiser, o prefixo dos schemas (`FE_BAR_PREFIXO_SCHEMA`). Os scripts leem o `.env`: rode `set -a; source .env; set +a` antes.

1. **Schemas e volumes:** `uv run python scripts/executar_sql.py src/governanca/01_schemas_e_volumes.sql`.
2. **Dados:**
   - `uv run python scripts/preparar_dados_publicos.py`;
   - gerador sintético: `uv run python -m dados_sinteticos.gerar --saida _saida --escala 1.0`;
   - publicação do lote 1: `uv run python scripts/simular_evento.py --lotes 1`.
3. **Pipeline e jobs:**
   - `PKG=$(uv run python scripts/publicar_pacote.py)`;
   - `databricks bundle deploy -t dev --var warehouse_id=$FE_BAR_WAREHOUSE_ID --var pacote_python=$PKG` (D-019);
   - na primeira vez, `databricks workspace mkdirs /Shared/sinistros_clima/dev`;
   - `databricks bundle run -t dev pipeline_sinistros` (bronze e silver do lote 1).
4. **Modelo e parecer:**
   - `databricks bundle run -t dev job_treino_modelo`;
   - `databricks bundle run -t dev job_avaliacao_parecer` (avalia o v1 × v2, promove o prompt e publica o endpoint).
5. **Gold do lote 1:** `databricks bundle run -t dev job_evento` (cria `gold.sinistros_analisados` e as visões).
6. **Lakebase:** `uv run python scripts/provisionar_lakebase.py` (precisa do gold do passo 5).
7. **Evento:** `uv run python scripts/simular_evento.py --lotes 9 --paralelo 16`. A chegada dos arquivos dispara o `job_evento`; se o parecer em lote passar do tempo máximo, o job pede a própria continuação.
8. **Governança, metric views e Genie:**
   - `uv run python scripts/aplicar_visoes_gold.py`;
   - `uv run python scripts/executar_sql.py src/governanca/95_governanca.sql`;
   - `uv run python scripts/executar_sql.py src/governanca/96_metric_views.sql`;
   - `uv run python scripts/genie_diretoria.py`.
9. **App:** veja `app/README.md` (deploy pelo bundle do app e `scripts/permissoes_app.py`).
10. **Evidências:**
   - `scripts/testar_lakebase.py`, `scripts/avaliar_teste_final.py`, `scripts/rastrear_sinistro.py` e `scripts/custo_por_unidade.py`;
   - `scripts/registrar_evidencia.py` para os arquivos SQL de conferência.

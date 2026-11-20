# Regulação inteligente de sinistros em eventos climáticos

Protótipo para o **FE Bar**. Seguradoras de ramos patrimoniais (residencial e empresarial) recebem milhares de avisos de sinistro em poucos dias após enchentes, vendavais e granizo. Esta solução prioriza, pré-analisa e acelera cada sinistro com dados e IA na Databricks. O tempo até a indenização cai de semanas para dias e pagamentos indevidos são evitados.

> Todos os dados deste projeto são **sintéticos ou públicos**. Nenhum dado real de cliente é utilizado.

## Status

| Etapa | Situação |
|---|---|
| Caso de uso e problema de negócio | ✅ Definido |
| Desenho da solução (spec) | ✅ Aprovada (`docs/specs/`) |
| Plano de implementação | ✅ Roadmap + fases 0 e 1 aprovados, em execução (`docs/planos/`) |
| Build (Lakeflow → UC → Lakebase → ML/GenAI → Genie → App) | ⏳ Pendente |
| Evidências de execução | ⏳ Pendente |
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
| `scripts/exploracao/` | Scripts de exploração das fontes de dados |
| `_interno/` | Material de apoio local, **não versionado** (veja `.gitignore`) |

Pastas de código (pipelines, notebooks, app, bundle) e evidências serão criadas na fase de implementação, conforme o plano.

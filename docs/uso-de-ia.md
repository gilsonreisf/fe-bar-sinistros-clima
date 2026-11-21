# Uso de IA: no produto e no build

## 1. IA no produto

A regra de desenho é simples: **a IA lê, cruza e recomenda; o código calcula; o regulador decide.** Cada uso tem avaliação, versão e rastreio.

| Onde | O que faz | Como é controlado | Evidência |
|---|---|---|---|
| `ai_parse_document` + `ai_extract` (pipeline) | Lê orçamentos, laudos e notas em PDF e extrai valor, itens, prestador e menção a dano anterior | Expectations no pipeline; documento ilegível ou com falha de extração vira flag e bloqueia o fast track | `01-ingestao.md`, `00c-conferencia-volume.md` |
| Modelo de suspeita (LightGBM no UC) | Dá o score de fraude ou *leakage* de cada aviso, com os fatores principais | Portão de promoção contra a linha de base de regras, alias `champion` e teste final em lotes nunca vistos | `04-ml.md`, `04c-teste-final.md` (D-021) |
| Parecer prévio (LLM) | Recomenda pagar, pagar parcial, recusar ou investigar, com motivos e cláusulas citadas | Saída em JSON validada em código com nova tentativa; **o valor é calculado em código**, não pelo LLM; prompt versionado no UC; avaliação v1 × v2 com `mlflow.genai.evaluate` (métricas de código + juízes `Correctness` e `Guidelines`); portão de qualidade antes de ir para produção | `05-avaliacao-genai.md`, `05-comparacao-llm.md` (D-022, D-023) |
| Endpoint do parecer (app) | "Reanalisar com IA" sob demanda, com Claude Sonnet 5.5 | AI Gateway (inference table e controle de uso), trace do MLflow por chamada e gravação da reanálise no Lakebase | `05-endpoint-parecer.md`, `08-rastreio-ponta-a-ponta.md` |
| Genie da diretoria | Perguntas em português sobre o evento | Fonte única: as metric views; instruções de negócio; 16 benchmarks avaliados | `06-genie.md` (D-025) |
| Supervisão humana | O regulador decide; a concordância IA × regulador é medida | Decisão idempotente no Lakebase, volta ao UC pelo Lakehouse Sync e tela "IA sob supervisão" | `03-lakebase.md` (D-024, D-026) |

**Escolha de modelo por custo e qualidade (D-023):**
- Para o lote, o Claude Haiku 5.5 empatou com o Sonnet na recomendação correta (95,1%), com um custo medido de cerca de US$ 0,001 por parecer.
- No app, o texto é lido pelo regulador, então ficou o Sonnet (melhor no juiz de diretrizes: 0,923 contra 0,874).

**O que a IA não faz sozinha:**
- não paga sinistro fora do fast track;
- não calcula valor;
- não vê CPF completo;
- não muda prompt nem modelo sem passar pelo portão de qualidade.

## 2. IA no build

O projeto foi construído com o **Claude Code** (Opus 5.5) como par de engenharia, com as skills oficiais da Databricks carregadas para cada produto: pipelines, Lakebase, apps, metric views, Genie, MLflow evaluation e Unity Catalog.

**Como o trabalho foi organizado:**
- **Spec primeiro.** O desenho da solução (`docs/specs/`) e o plano de cada fase (`docs/planos/`) foram escritos e aprovados antes do código.
- **Decisões registradas.** Toda decisão não trivial virou uma entrada D-0XX em `docs/decisoes-e-tradeoffs.md`, com contexto, escolha, alternativa descartada e risco. A partir da fase 3, o autor delegou a execução e as decisões ao agente, e a revisão das decisões ficou com ele (D-021 a D-027).
- **Teste antes do código.** As regras de negócio (clima, fast track, prioridade, validação do parecer, valor) têm testes `pytest` (228); o app tem testes `vitest` do contrato das rotas.
- **Ensaios locais.** Os notebooks foram ensaiados localmente, com stubs de Spark e MLflow, antes de ir ao workspace. Isso pegou vários erros sem gastar computação.
- **Fatos medidos no workspace.** Várias premissas foram verificadas e mudaram o desenho. Exemplos:
  - o Claude 5.5 no FMAPI devolve o conteúdo em partes e não aceita `json_schema`;
  - o Prompt Registry estava desabilitado no FEVM, e os prompts foram para uma tabela Delta;
  - a vazão do FMAPI ficou em ~21 pareceres por minuto;
  - o Lakehouse Sync leva o UUID como BINARY.
- **Revisão independente.** Ao fim das fases, um revisor separado (outro agente, sem o contexto de quem implementou) leu o diff procurando erros graves. Os pontos críticos e importantes foram corrigidos e registrados.
- **Segurança e reuso:**
  - varredura de segredos a cada commit;
  - nenhum nome de catálogo, schema ou usuário fixo no código (D-016);
  - nenhum dado real (todos os dados são sintéticos ou públicos);
  - nenhuma publicação sem autorização do autor (D-013).

**Onde o humano decidiu:**
- o caso de uso;
- o escopo e os cortes de prazo (retreino como próximo passo, governança enxuta, Genie com link no app);
- a premissa de custo de referência;
- a revisão final antes de publicar.

# Fase 4: parecer prévio por IA e avaliação com MLflow — plano de implementação

> **Para agentes:** sub-skill obrigatória: superpowers:executing-plans (modo NATIVE). Os passos usam checkbox (`- [ ]`).
> **Autorização:** a mesma da fase 3. Execução autônoma até o projeto técnico ficar pronto; o autor revisa depois (D-013 continua valendo para push e publicação).

**Objetivo:** para cada sinistro, um parecer prévio em JSON validado (recomendação, valor sugerido, motivos, cláusulas e confiança), gerado por Claude Sonnet com um prompt versionado no Prompt Registry do UC. O parecer é avaliado com `mlflow.genai.evaluate()` (v1 × v2), registrado como modelo MLflow e servido num endpoint com tracing e AI Gateway.

**Arquitetura:**
- **Entrada:** `silver.entrada_parecer`, uma MV nova no pipeline que monta o JSON de entrada de cada sinistro (aviso, apólice e coberturas, evidência climática, itens com preço de referência, trecho do laudo, prestador e alertas). A mesma entrada serve a avaliação, o gold (fase 5) e o app.
- **Pacote `src/parecer/` (puro e testável com LLM simulado):**
  - `gerar_parecer()` monta o prompt, chama o LLM, valida o JSON (com 1 nova tentativa) e **calcula o valor em código** a partir da base escolhida pelo LLM;
  - cada etapa vira um span de trace.
- **Notebook `avaliacao_parecer` (job serverless `job_avaliacao_parecer`):**
  1. dataset estratificado do lote 1 → MLflow Evaluation Dataset no UC;
  2. prompts v1 e v2 no Registry;
  3. `evaluate` com scorers de código e juízes (`Correctness` e `Guidelines`);
  4. portão de qualidade → alias `producao` do prompt;
  5. registro de `ml.parecer_sinistro` (*models from code*, com o template congelado e passthrough de auth para o LLM);
  6. publicação ou atualização do endpoint com AI Gateway (inference table e usage tracking) e tracing.

**Tech stack:** MLflow 3 (GenAI evaluate, Prompt Registry, Evaluation Datasets, tracing), Databricks SDK (`serving_endpoints.query`), FMAPI `databricks-claude-sonnet-5-5`, Model Serving (CPU Small, scale-to-zero), Lakeflow SDP e DAB.

**Spec:** seções 6.2, 6.4, 10.2 e 10.3. **Decisões herdadas:** D-008 (parecer prévio), D-017 (modelo do parecer `databricks-claude-sonnet-5-5`) e D-021 (score e fatores da fase 3).

## Fatos verificados antes do plano (2026-11-21)

- `databricks-claude-sonnet-5-5` **não aceita `response_format` com `json_schema`** ("translation requires forced tool use") **nem `temperature`**. O JSON sai pelo prompt e é validado em código, como manda a spec 10.3. Sem `temperature`, há variação entre execuções, e a comparação v1 × v2 tem ruído.
- Uma chamada simples leva ~2,5 s. Preço de lista: `ENTERPRISE_ANTHROPIC_MODEL_SERVING`, a US$ 0,07 por DBU. O consumo em DBU por token será medido no faturamento.
- No MLflow 3.18, a API é:
  - `mlflow.genai.datasets.create_dataset(name, experiment_id, tags)` e `delete_dataset(name)`;
  - `mlflow.genai.register_prompt(name, template, commit_message, tags)`, `load_prompt(...)` e `set_prompt_alias(name, alias, version)`;
  - `Guidelines(name=..., guidelines=[...])` e `Correctness()` (exige `expected_facts`).
- **Métrica de valor fora dos scorers:** um scorer que devolve "skip" mistura tipos na agregação. Por isso, `valor_dentro_tolerancia` é calculada só nos casos com pagamento esperado e logada à parte.

## Restrições globais

- Nada fixo: catálogo, schemas, nome do endpoint e experimento vêm de parâmetros do job e de variáveis do bundle (D-016). Nenhum nome de usuário.
- **Saída do parecer:** `recomendacao` ∈ {`pagar_integral`, `pagar_parcial`, `recusar`, `investigar`}; `valor_sugerido` (calculado em código); `motivos[]`, `clausulas[]` (códigos de `parecer.clausulas.CLAUSULAS`) e `confianca` ∈ [0, 1]. Mais `status_parecer` (`ok` ou `invalido`), `versao_prompt` e `trace_id`.
- **JSON inválido** depois de 1 nova tentativa: `recomendacao = investigar`, `status_parecer = invalido` e o motivo registrado (spec 10.3).
- **A IA nunca recusa sozinha:** `recusar` e `investigar` sempre vão ao regulador. Isso é aplicado na fase 5, porque só `pagar_integral` entra no fast track.
- O gabarito do evento só é lido no notebook de avaliação, para montar as expectativas. Nunca entra na entrada do parecer.
- **Custo:** ~143 casos × 2 prompts ≈ 290 chamadas ao LLM, mais ~580 chamadas de juízes. O endpoint é Small com scale-to-zero.

## Decisões deste plano (registrar como D-022)

1. **"O LLM decide, o código calcula."**
   - O LLM devolve `base_valor` ∈ {`reclamado`, `tabela_referencia`, `itens_validos`, `zero`} e, em `itens_validos`, os `itens_excluidos`.
   - O código calcula `valor_sugerido`: franquia, LMI e soma dos itens.
   - O prompt recebe também os valores pré-calculados (`valor_liquido_reclamado`, `valor_liquido_tabela` e `excede_lmi`).
   - **Motivo:** aritmética é o ponto fraco dos LLMs, e a regra de indenização é determinística.
2. **Template congelado no modelo:** o modelo registrado leva o texto e a versão do prompt num artefato. O Registry continua sendo a fonte das versões e do alias `producao`, mas o endpoint não depende de ler o Registry em tempo de execução (permissão do endpoint e latência).
3. **Endpoint publicado pelo job, depois do portão de qualidade** (create ou update pelo SDK, de forma idempotente). A versão servida só existe depois da avaliação, e declarar o endpoint no DAB exigiria um deploy em dois passos, que quebra a primeira instalação. Os jobs, o experimento e o pipeline continuam no DAB.
4. **Chamada ao LLM pelo Databricks SDK** (`serving_endpoints.query`): funciona no notebook e no serving com o passthrough (`resources=[DatabricksServingEndpoint]`), sem a dependência do `openai`.
5. **O score e os fatores do modelo de suspeita entram na entrada do parecer** (integração ML → GenAI). Chegam como colunas opcionais, porque o score é calculado no gold.
6. **Cláusulas sintéticas** (`parecer/clausulas.py`): condições gerais fictícias da seguradora (coberturas, franquia, LMI, preexistência, comprovação do evento, orçamento, vistoria). O LLM cita os códigos; não há texto real de apólice.
7. **Dataset de avaliação do lote 1:** até 25 casos por padrão (~143 casos, porque o lote 1 tem só 5 `prestador_concentrado`, 9 `dano_preexistente` e 13 `apolice_recente`). A spec fala em ~200; a diferença é registrada e o dataset cresce na fase 5 com os lotes 2 a 10.

## Foco de revisão

1. **JSON quebrado ou incompleto do LLM** (cercas ```json, texto antes do JSON, chave faltando, enum inválido, confiança fora de [0, 1]). Esperado: uma nova tentativa e, depois, `investigar` com `status_parecer = invalido`. Testes em `test_parecer_esquema.py` e `test_parecer_gerar.py`.
2. **Valor sugerido fora da regra** (franquia maior que o valor, LMI excedido, item excluído com grafia diferente da do orçamento). Esperado: nunca negativo, nunca acima do LMI; exclusão por nome-base sem acento e sem caixa. Testes em `test_parecer_valor.py`.
3. **Entrada sem itens, sem laudo, sem cobertura ou sem score** (sinistro sem orçamento legível, apólice inexistente). Esperado: o parecer sai, sem erro. Teste com uma entrada mínima.
4. **Endpoint frio ou LLM indisponível.** Esperado: erro capturado e `status_parecer = pendente` no lote, sem derrubar o batch (spec 10.3). Teste com um LLM simulado que lança exceção.
5. **Reexecução do job** (dataset e prompts já existem, endpoint já existe). Esperado: o dataset é recriado; um prompt só ganha versão nova se o texto mudou; o endpoint é atualizado, não duplicado. Teste de `registrar_prompt_se_mudou` com um cliente simulado e ensaio local.

---

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/parecer/__init__.py` | Pacote do parecer prévio |
| `src/parecer/clausulas.py` | Condições gerais sintéticas (código → texto) |
| `src/parecer/prompts.py` | Templates v1 (básico) e v2 (regras explícitas e exemplos), com `{{entrada}}` e `{{clausulas}}` |
| `src/parecer/esquema.py` | Domínios, `extrair_json`, `validar_parecer`, `parecer_invalido` e `parecer_pendente` |
| `src/parecer/valor.py` | `valores_de_referencia(entrada)` e `calcular_valor(entrada, base, itens_excluidos)` |
| `src/parecer/gerar.py` | `gerar_parecer(...)` com trace, nova tentativa e cálculo do valor; `chamar_llm_databricks(endpoint)` |
| `src/parecer/modelo_pyfunc.py` | Modelo MLflow servido (`ParecerSinistro`): `entrada_json` (+ score e fatores opcionais) → parecer |
| `src/parecer/avaliacao.py` | Expectativas por padrão, amostra estratificada, métricas de código, `registrar_prompt_se_mudou` |
| `src/parecer/endpoint.py` | `config_endpoint(...)` (pura) e `publicar_endpoint(w, ...)` (create ou update) |
| `src/pipeline/silver_parecer.sql` | MV `entrada_parecer` |
| `notebooks/avaliacao_parecer.py` | Notebook do job de avaliação, registro e publicação |
| `recursos/job_avaliacao_parecer.yml` | Job serverless e experimento `/Shared/${bundle.name}/${bundle.target}/parecer_sinistro` |
| `scripts/testar_endpoint_parecer.py` | Teste do endpoint publicado com 3 sinistros, checando o trace |
| `scripts/evidencia_parecer.py` | `evidencias/05-avaliacao-genai.md` (v1 × v2, por padrão, erros, endpoint) |
| `testes/test_parecer_*.py` | Testes (LLM simulado) |

---

### Task 4.1: núcleo do parecer (esquema, valor, prompts, cláusulas e geração)

**Interfaces (produz):**
- `RECOMENDACOES`, `BASES_VALOR`, `validar_parecer(texto: str) -> tuple[dict | None, list[str]]` (o dict tem `recomendacao`, `base_valor`, `itens_excluidos`, `motivos`, `clausulas` e `confianca`), `parecer_invalido(erros) -> dict` e `parecer_pendente(erro) -> dict`.
- `valores_de_referencia(entrada: dict) -> dict` (`valor_liquido_reclamado`, `valor_liquido_tabela` e `excede_lmi`) e `calcular_valor(entrada, base_valor, itens_excluidos) -> float`.
- `PROMPTS = {"v1": PROMPT_V1, "v2": PROMPT_V2}`, `renderizar_prompt(template, entrada) -> str` e `CLAUSULAS: dict[str, str]`.
- `gerar_parecer(entrada: dict, template: str, chamar_llm: Callable[[str], str], versao_prompt: str, tentativas: int = 2) -> dict`. A saída tem as chaves do esquema mais `valor_sugerido`, `status_parecer`, `versao_prompt`, `erros` e `trace_id`.

**Testes (RED primeiro):**
- **Esquema:**
  - JSON válido;
  - JSON com cerca ```json e texto antes;
  - chave faltando;
  - enum inválido;
  - confiança 1,5;
  - cláusula com código desconhecido (é removida, com um aviso nos erros, e o parecer continua válido se sobrar ao menos uma);
  - `itens_excluidos` obrigatório quando `base_valor = itens_validos`.
- **Valor:**
  - integral com franquia;
  - franquia maior que o valor → 0;
  - LMI excedido → LMI;
  - tabela usa o preço de referência só nos itens casados;
  - itens válidos excluem por nome-base sem acento e sem caixa (`"Telha cerâmica"` exclui `"telha ceramica (padrão popular)"`);
  - `zero` → 0;
  - sem LMI ou sem franquia não quebra.
- **Geração (LLM simulado):**
  - primeira resposta válida → `status_parecer = ok` e o valor calculado em código;
  - primeira inválida e segunda válida → `ok`, com 2 chamadas;
  - duas inválidas → `investigar` e `invalido`;
  - o LLM lança exceção → `pendente`, sem propagar;
  - o prompt renderizado contém os valores de referência e as cláusulas;
  - a entrada mínima (sem itens, sem laudo e sem score) funciona.

**Passos:**
- [ ] Escrever os testes e rodar (FAIL).
- [ ] Implementar os módulos e rodar (PASS).
- [ ] Commit `feat: núcleo do parecer prévio (esquema, valor em código, prompts e geração com nova tentativa)`.

### Task 4.2: entrada do parecer no pipeline

**Interfaces (produz):** a MV `silver.entrada_parecer` (`id_aviso`, `entrada_json` STRING). O JSON tem:
- `aviso`;
- `apolice` (com `coberturas_contratadas`);
- `evidencia_climatica`;
- `documentos` (`valor_orcamento`, `desvio_preco_pct`, `menciona_dano_anterior`, `flags`, `itens[]` com `preco_referencia` e `laudo`, este com no máximo 3.000 caracteres);
- `prestador`;
- `alertas_qualidade`.

**Testes estáticos (RED):** o SQL não lê o gabarito, usa só as chaves da configuração, lê `documentos_texto` só para laudos e usa a mesma chave de preço das outras MVs.

**Passos:**
- [ ] Escrever os testes estáticos (FAIL).
- [ ] Implementar a MV (PASS).
- [ ] Deploy e `start-update`, sem full refresh e sem custo de IA, porque as tabelas com IA são streaming e não têm dado novo.
- [ ] Conferir 800 linhas e um JSON de exemplo por padrão, que o `json_valido` da validação local precisa aceitar.
- [ ] Commit.

### Task 4.3: avaliação, portão de qualidade, registro e endpoint (job)

**Interfaces:**
- `avaliacao.py`: `expectativas(linha_gabarito) -> dict` (`recomendacao_esperada`, `valor_devido`, `padrao` e `expected_facts`); `amostra_estratificada(df, por, n_max, seed)`; `recomendacao_correta`, `padrao_identificado` e `cita_clausula` (funções puras, embrulhadas em `@scorer` no notebook); `valor_dentro_tolerancia(valor, devido, tolerancia=0.10)`; `registrar_prompt_se_mudou(registrar, buscar_versoes, nome, template, mensagem) -> versao`.
- `endpoint.py`: `config_endpoint(modelo, versao, experimento_id, catalogo, schema, prefixo_tabela) -> dict` e `publicar_endpoint(w, nome, config) -> str`.

**Testes (RED):**
- expectativas por padrão (as 8 classes);
- amostra estratificada (limite e estabilidade com a seed);
- métricas puras;
- `registrar_prompt_se_mudou` (texto igual reaproveita a versão; texto novo registra);
- `config_endpoint`:
  - scale-to-zero e workload Small;
  - variáveis de tracing;
  - AI Gateway com inference table e usage tracking;
  - nada fixo.

**Notebook (seções):**
1. Objetivo e decisões.
2. Parâmetros.
3. Dataset: `entrada_parecer` + `sinistros_enriquecidos` + score do `modelo_suspeita@champion` + gabarito do evento. Amostra estratificada → `create_dataset` (recriado) e `merge_records`.
4. Prompts v1 e v2 no Registry (`registrar_prompt_se_mudou`).
5. `evaluate` para v1 e v2, em runs nomeados. Os scorers são os 3 de código mais `json_valido`, `Correctness()` e `Guidelines` (4 diretrizes). Depois, a métrica de valor, a matriz de confusão das recomendações, a acurácia por padrão e a tabela de erros, como artefatos.
6. Portão: `producao` vai para a versão com `recomendacao_correta` maior ou igual à do `producao` atual, com a métrica guardada como tag da versão do prompt.
7. Registro de `ml.parecer_sinistro` com o template de `producao`, os `resources` do LLM, a assinatura e o exemplo de entrada; alias `producao` também no modelo.
8. `publicar_endpoint` e espera por READY.
9. `exit` com as métricas, as versões e o nome do endpoint.

**Passos:**
- [ ] Rodar os testes.
- [ ] Ensaio local do notebook com um LLM simulado (stubs de Spark; o MLflow aponta para o workspace só no job).
- [ ] Deploy, rodar o job e corrigir o que falhar, registrando no ledger.
- [ ] Aceite:
  - `json_valido` ≥ 0,95;
  - `recomendacao_correta` (v2) ≥ 0,80;
  - endpoint READY;
  - modelo com alias `producao`.
- [ ] Commit.

### Task 4.4: teste do endpoint e evidências

**Passos:**
- [ ] `scripts/testar_endpoint_parecer.py`:
  - consultar o endpoint com 3 sinistros (um legítimo, um sem evento e um inflado) e imprimir o parecer, a latência e o `trace_id`;
  - procurar o trace no experimento;
  - registrar se a inference table já existe (ela tem atraso).
- [ ] `scripts/evidencia_parecer.py` → `evidencias/05-avaliacao-genai.md`:
  - v1 × v2 (métricas agregadas);
  - acurácia por padrão;
  - os 10 primeiros erros, com o motivo;
  - versões do prompt e do modelo, mais o dataset;
  - endpoint (estado, AI Gateway, resultado do teste).
- [ ] Exportar o notebook executado para `notebooks/saidas/avaliacao_parecer.ipynb`.
- [ ] Documentação:
  - D-022 com os resultados reais;
  - README (status, estrutura e comandos);
  - roadmap;
  - memória.
- [ ] Commit.

### Task 4.5: revisão independente

- [ ] Revisor (opus) com o diff da fase. Focos: validação e segurança do JSON, regra de indenização em código, vazamento do gabarito, honestidade das métricas (ruído sem temperature), custo e idempotência.
- [ ] Corrigir os pontos críticos e importantes, registrar no ledger e fazer o merge local.

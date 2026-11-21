# Fase 5: gold e orquestração — plano de implementação

> **Para agentes:** sub-skill obrigatória: superpowers:executing-plans (modo NATIVE). A autorização é a mesma das fases 3 e 4: execução autônoma; push e publicação dependem do autor.

**Objetivo:** cada aviso que chega vira, sem intervenção, um sinistro analisado com:
- score de suspeita;
- parecer prévio;
- decisão de fast track com os motivos de bloqueio;
- prioridade na fila.

Os lotes 2 a 10 do evento chegam pelo Volume, disparam o job e servem de **teste final honesto** do modelo e do parecer.

**Arquitetura:**
- **`job_evento`, disparado pela chegada de arquivos** em `landing/arquivos/avisos/`:
  1. `pipeline_task` (bronze e silver);
  2. notebook `processar_evento`, que pega os avisos novos (e os pareceres `pendente` ou `invalido`, com até 3 tentativas), pontua com o `modelo_suspeita@champion`, gera o parecer com o prompt de produção, aplica as regras de fast track e de prioridade e faz `MERGE` em `gold.sinistros_analisados`.
- **Visões gold** (`fila_regulacao`, `kpis_evento` e `sinistro_detalhe`), recriadas pelo próprio notebook a partir de uma função pura.
- **Regras de fast track e de prioridade** em `src/regras/fast_track.py` (pandas puro, testado).

**Spec:** seções 5 (gold), 6.3, 10.3 e 11 (jobs). **Decisões herdadas:**
- D-020: alertas que bloqueiam o fast track;
- D-021: score, contrato e validação × teste final;
- D-022: parecer, o LLM decide e o código calcula, e os prompts ficam numa tabela do UC.

## Decisões deste plano (registrar como D-023)

1. **O lote chama `gerar_parecer` direto** (o mesmo código do endpoint), em paralelo, e não via `ai_query` no endpoint.
   - **Motivo:** o endpoint Small, com scale-to-zero, atende poucas requisições simultâneas (~6 s cada), e 7.200 pareceres levariam horas.
   - **O que não muda:** a validação, o cálculo do valor e o trace são idênticos.
   - O endpoint segue para o app ("Reanalisar com IA") e para o teste ponta a ponta.
   - É um desvio da spec (seção 5, `ai_query`), por vazão.
2. **LLM do lote:** o mais barato que passar no portão de qualidade da fase 4 (`recomendacao_correta` até 2 p.p. abaixo do Sonnet no mesmo dataset), comparado pelo modo `publicar=nao` do job de avaliação. A decisão e os números vão para a D-023.
3. **Fast track** (spec 6.3 + D-020): todas as condições abaixo.
   - valor ≤ R$ 5 mil;
   - cobertura válida;
   - evidência `forte`;
   - score < 0,2;
   - recomendação `pagar_integral`;
   - `status_parecer = ok`;
   - nenhum alerta ou flag bloqueante: `apolice_inexistente`, `fora_vigencia`, `datas_incoerentes`, `valor_invalido`, `causa_desconhecida`, `documento_ilegivel`, `extracao_falhou`, `preco_nao_conferido` e `documento_ausente`.
   - `sem_estacao_no_raio` é só informativo.
   - Cada sinistro guarda os motivos de bloqueio (lista), para o regulador e para os KPIs.
4. **Prioridade dos demais:** 0,45 × suspeita + 0,35 × valor normalizado (valor ÷ R$ 50 mil, com teto em 1) + 0,20 × espera (dias desde o aviso ÷ 15, com teto em 1).
   - Os pesos ficam configuráveis por parâmetro do job.
   - **Motivo dos pesos:** a suspeita pesa mais porque é a principal fonte de *leakage*; o valor, porque concentra a exposição; a espera, porque protege o segurado (NPS e retenção).
5. **Teste final:** os lotes 2 a 10 nunca foram vistos no treino nem na avaliação do parecer. Lá se medem:
   - AUC e vazamento do score;
   - acurácia do parecer por padrão;
   - taxa de fast track;
   - suspeitos que entraram no fast track.
6. **Custo:** antes de publicar os lotes 2 a 10, o faturamento do lote 1 foi conferido (AI Functions com ~US$ 3,28 para 951 PDFs), e o custo do parecer foi medido por token. Depois do processamento, `evidencias/09-custo-real.md` traz o custo por PDF, por aviso e por parecer.

## Tasks

### Task 5.1: regras de fast track e prioridade

**Arquivos:** `src/regras/fast_track.py` e `testes/test_fast_track.py`.

**Interfaces:**
- `BLOQUEANTES` (tupla de alertas e flags);
- `avaliar_fast_track(df) -> pd.DataFrame` (colunas `fast_track` bool e `bloqueios_fast_track` list[str]);
- `prioridade(df, pesos=PESOS_PRIORIDADE, hoje=...) -> pd.Series` (0 a 1).

**Testes:**
- cada condição bloqueia sozinha, com o motivo certo;
- `sem_estacao_no_raio` não bloqueia;
- nulos (score, parecer ausente) bloqueiam;
- prioridade monotônica em cada componente e limitada a [0, 1];
- os pesos somam 1 (o código valida).

### Task 5.2: gold e processamento incremental

**Arquivos:**
- `src/gold/__init__.py`;
- `src/gold/visoes.py` (`ddl_gold(catalogo, schema_silver, schema_gold) -> list[str]`: tabela `sinistros_analisados` e visões `fila_regulacao`, `kpis_evento` e `sinistro_detalhe`);
- `src/gold/processar.py` (`selecionar_para_analise(silver, gold, max_tentativas)`, `montar_linhas_gold(...)`, `gerar_pareceres(entradas, gerar, paralelo)`);
- `notebooks/processar_evento.py`;
- testes `test_gold.py`.

**Testes:**
- seleção: aviso novo entra; `ok` não entra; `pendente` com menos de 3 tentativas entra; com 3, não;
- o DDL não tem nome fixo e as visões leem só gold e silver;
- `gerar_pareceres` com um gerador que falha em 1 de 5 → 4 `ok` e 1 `pendente`, sem derrubar o lote.

### Task 5.3: job do evento e publicação dos lotes 2 a 10

**Arquivos:** `recursos/job_evento.yml` (gatilho de chegada de arquivo, `pipeline_task` → notebook; parâmetros: catálogo, schemas, LLM do lote, pesos, paralelismo) e testes estáticos.

**Execução:**
- deploy;
- `run-now` com o lote 1, para popular o gold;
- `simular_evento.py --lotes 9 --paralelo 16`, que dispara o job pela chegada dos arquivos;
- acompanhar até o gold ter 8.000 linhas.

### Task 5.4: teste final e evidências

**Arquivos:**
- `scripts/avaliar_teste_final.py` → `evidencias/04c-teste-final.md` (score nos lotes 2 a 10 contra a linha de base de regras; parecer por padrão; fast track e vazamento);
- `src/governanca/94_conferir_gold.sql` → `evidencias/05c-gold.md`;
- `evidencias/09-custo-real.md` regenerado, com o custo por unidade;
- D-023, README, roadmap e memória.

### Task 5.5: revisão independente

Revisor opus com o diff das fases 4 e 5. Corrigir os pontos críticos e importantes e fazer o merge.

## Foco de revisão

1. Um aviso processado duas vezes, por reexecução ou gatilho duplo, não pode duplicar a linha nem gerar um segundo parecer pago: `MERGE` por `id_aviso` e seleção que exclui `ok`.
2. Uma falha do LLM no meio do lote não pode perder os pareceres já gerados: grava por partes (blocos de 200).
3. Um suspeito não pode entrar no fast track por dado faltante: nulo bloqueia.
4. Um lote pode chegar enquanto o job roda: `max_concurrent_runs: 1` e o gatilho com espera depois da última mudança.
5. Os números do teste final só podem usar os lotes 2 a 10.

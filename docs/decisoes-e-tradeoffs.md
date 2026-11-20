# Decisões e trade-offs

Registro das decisões do projeto, com as alternativas consideradas e o motivo da escolha.

## D-001: Caso de uso — regulação de sinistros patrimoniais em eventos climáticos

**Data:** 2026-11-20

**Alternativas consideradas:**

| # | Caso | Por que não foi escolhido |
|---|---|---|
| 1 | Antifraude no Pix (bancos e fintechs) | Forte candidato. Muito bom em decisão em tempo real, mas tem menos espaço para GenAI sobre documentos e é um tema mais saturado em demos. |
| 2 | Perdas não técnicas de energia (distribuidoras) | Muito regional, mas com menor reuso entre segmentos. |
| 3 | Ruptura de gôndola no varejo | Mais reutilizável e com dados públicos prontos, mas com menos destaque e diferenciação. |
| 4 | Auditoria de contas médicas (operadoras de saúde) | Bom caso, com padrão parecido com o escolhido, mas com menor apelo de urgência. |
| 5 | Risco climático no crédito rural | Bom uso de dados públicos, mas o Lakebase tem papel menos natural. |
| 6 | **Sinistros em eventos climáticos (seguros patrimoniais)** | **Escolhido.** |

**Motivo da escolha:**
- O problema é atual e muito relevante na região.
- GenAI sobre documentos não estruturados tem papel central (orçamentos, laudos, apólices).
- As seis camadas se integram de forma natural, com um laço operacional: o parecer do regulador volta para a base e realimenta o modelo.
- Serve para qualquer seguradora com carteira patrimonial, para resseguradoras e para corretoras grandes, sem mencionar nenhum cliente específico.
- Rende um roleplay forte com as duas personas (diretor de sinistros e arquiteto).

**Restrição:** fora do escopo o seguro de automóvel, por decisão do autor.

## D-002: Workspace dedicado (FEVM novo)

**Data:** 2026-11-20

**Alternativas consideradas:** o FEVM existente (`fevm-daiwt`) e o workspace compartilhado `e2-demo-west`.

**Motivo da escolha:**
- Um workspace isolado e serverless, com as features novas habilitadas (Lakebase, Apps, Genie, AI Functions).
- As evidências de execução ficam limpas e reprodutíveis.
- O build não depende de demos de terceiros nem de permissões compartilhadas.

## D-003: Repositório público na conta pessoal do GitHub

**Data:** 2026-11-20

**Alternativas consideradas:** um repo privado na org EMU (conectado no formulário de submissão) e decidir mais tarde.

**Motivo da escolha:**
- É o caminho mais simples para o avaliador ler o repo.
- Todos os dados são sintéticos ou públicos.
- O material interno fica fora do versionamento (`_interno/` no `.gitignore`).

## D-004: Ambição "Strongly passed"

**Data:** 2026-11-20

**Alternativa considerada:** um "Pass enxuto" (as seis camadas no mínimo necessário, em ~4 a 6 horas).

**Motivo da escolha:** o escopo completo e bem acabado dá margem para se destacar nos quatro domínios:
- seis camadas integradas;
- laço de retorno do regulador para o modelo;
- avaliação do LLM com MLflow;
- evidências de execução ricas;
- decisões documentadas.

## D-005: Arquitetura "pipeline como espinha dorsal, com laço de retorno"

**Data:** 2026-11-20

**Alternativas consideradas:**
- **B, centrada em agente:** parecer sob demanda via agente com ferramentas e RAG. Muitas peças móveis, risco ao vivo e foco desviado do fluxo integrado.
- **C, tempo real:** Zerobus mais score online. O problema do caso é volume, não latência, então seria complexidade sem ganho.

**Escolha:** a abordagem A.
- Um pipeline Lakeflow (SDP) com Auto Loader e as camadas bronze, silver e gold.
- `ai_parse_document` e `ai_query` dentro do pipeline.
- O modelo de ML registrado no UC pontua cada sinistro.
- A fila gold é sincronizada para o Lakebase.
- O app grava a decisão do regulador no Lakebase, e essa decisão volta ao lakehouse para realimentar o modelo.
- Genie Agent mais metric view.
- Elemento da abordagem B incorporado: um botão **"Reanalisar com IA"** no app, que roda o mesmo prompt sob demanda para um sinistro.

## D-006: Avaliação do LLM com MLflow e rastreabilidade total

**Data:** 2026-11-20

O parecer gerado pelo LLM é avaliado com MLflow contra um gabarito sintético. **Requisito do autor:** o experimento deve ser logado com traces, artefatos, gráficos e rastreabilidade total (versão do prompt, do modelo e dos dados ligadas a cada execução).

## D-007: Recorte climático — temporada de granizo e vendaval em SC, ago–set/2026

**Data:** 2026-11-20

**Alternativas consideradas:**
- **Enchentes do RS em 2024:** descartadas pelo autor por terem sido um evento trágico.
- **Tornado no PR em novembro de 2025 e chuvas no PR em setembro de 2026:** descartados por terem tido vítimas.
- **Temporais urbanos em SP:** não foi possível confirmar um evento recente específico, sem vítimas, com os dados necessários.
- **Evento fictício com clima sintético:** perde o realismo de dados públicos.

**Escolha:** a temporada de granizo e vendaval em Santa Catarina em agosto e setembro de 2026, com dados reais do INMET.
- O dano é material, típico do seguro residencial (destelhamento, vidros, danos elétricos).
- O evento é recente.
- O fallback previsto, a mesma temporada de 2025, **não foi necessário**: o INMET já publicou 2026 até 31/10. Veja `docs/dados/inmet-cobertura-sc.md`.

**Trade-off assumido:** a cobertura das estações é parcial. A solução usa a estação válida mais próxima por variável e marca os casos de "evidência climática fraca" para o regulador, em vez de recusá-los.

## D-008: Parecer da IA servido como endpoint do Model Serving

**Data:** 2026-11-20

**Alternativa considerada:** colocar o prompt direto no `ai_query` do pipeline, chamando o modelo fundacional. É mais simples, mas teria duas implementações (o lote e o botão do app), não geraria traces por chamada e deixaria o versionamento mais fraco.

**Escolha:**
- A função `gerar_parecer()` é empacotada como modelo MLflow e registrada no UC.
- O prompt fica no MLflow Prompt Registry.
- A função é servida em um endpoint com tracing ativo.
- O pipeline chama o endpoint via `ai_query`, e o botão "Reanalisar com IA" chama o mesmo endpoint.
- Cada parecer guarda a versão do modelo, a versão do prompt e o `trace_id`.

**Custo assumido:** um endpoint a mais (com scale-to-zero) e mais latência no lote.

**Regra de governança associada:** a IA nunca recusa sozinha. Recusas e casos marcados como "investigar" passam sempre pelo regulador.

## D-009: AppKit, com Lakebase para a operação e SQL Warehouse para a análise

**Data:** 2026-11-20

**Alternativas consideradas:** Streamlit ou Dash em Python. São mais rápidos de prototipar, mas têm visual menos profissional e integração menos nativa com Lakebase e Genie.

**Escolha:**
- **App:** AppKit (React + TypeScript).
- **Lakebase:** fila e detalhe (synced tables), mais `atribuicoes`, `decisoes_regulador` (apenas inserções) e `reanalises`. A concorrência é controlada com `FOR UPDATE SKIP LOCKED`.
- **SQL Warehouse:** KPIs e gráficos sobre o gold e a metric view.
- **Genie:** embutido no app.
- **Sincronização:** a synced table roda em modo Triggered, encadeada no job do pipeline. O Lakehouse Sync leva o schema `operacao` de volta ao UC em SCD2.

**Motivo:** usar cada ferramenta no que ela faz melhor. O Lakebase cuida das gravações transacionais e da concorrência (OLTP), e o lakehouse cuida das análises. Esse argumento também é útil com a persona técnica do roleplay.

## D-010: Métricas governadas em metric views, compartilhadas pelo app e pelo Genie

**Data:** 2026-11-20

**Alternativa considerada:** calcular os KPIs em SQL dentro do app e configurar o Genie direto sobre as tabelas gold. É mais rápido, mas a definição de "valor pago" e de "*leakage*" poderia divergir entre o app e o Genie.

**Escolha:** duas metric views no UC, usadas tanto pelo painel do app quanto pelo Genie Agent "Sinistros Clima — Diretoria".
- `gold.mv_sinistros`: avisado, aprovado, pago, fast track, tempo até a indenização, *leakage* evitado e concordância entre IA e regulador.
- `gold.mv_exposicao`: LMI e prêmio expostos por município e clima.

O Genie tem glossário e consultas de exemplo em português, e é avaliado com benchmarks (~15 perguntas). Os resultados vão para `evidencias/`.

## D-011: Governança por persona com tags, máscaras e filtros de linha (ABAC quando disponível)

**Data:** 2026-11-20

**Escolha:**
- **Grupos:** `grp_engenharia_dados`, `grp_regulacao`, `grp_diretoria_sinistros` e `grp_atuarial`, mais o service principal do app.
- **Tags LGPD** nas colunas pessoais.
- **Máscaras:** CPF parcial; endereço reduzido a município e UF para quem não é da regulação.
- **Filtro de linha:** cada regulador vê só a sua regional.
- **Abordagem:** políticas ABAC baseadas nas tags, se o FEVM tiver; caso contrário, funções de máscara e de filtro aplicadas tabela a tabela.
- **Rastreabilidade:** lineage do UC, histórico SCD2 das decisões e `trace_id` permitem auditar "quem decidiu, quando, com qual parecer, de qual versão de modelo e prompt".
- **IA:** AI Gateway no endpoint do parecer, com inference tables.

**Trade-off:** o FEVM tem um único usuário humano. As personas são simuladas com grupos e service principals de teste, e as provas ficam em texto, com consultas executadas por identidade e salvas em `evidencias/`.

## D-012: Evidências geradas por script e o princípio "toda falha leva ao regulador"

**Data:** 2026-11-20

**Escolha:**
- **Evidências:** notebooks commitados em `.ipynb` com as saídas, mais a pasta `evidencias/`, com um Markdown por camada gerado por `scripts/coletar_evidencias.py`. A evidência principal é o rastreio de um único sinistro por todas as camadas (`08-rastreio-ponta-a-ponta.md`). O custo real do protótipo é medido em `system.billing.usage`.
- **Testes:** expectations no pipeline, pytest nas regras e na validação do parecer, teste de ponta a ponta com 50 avisos e portões de qualidade para promover o modelo e o prompt.
- **Erros:** toda falha (endpoint, JSON inválido, PDF ilegível, ausência de clima) envia o sinistro ao regulador. Nunca há pagamento ou recusa automáticos.

**Motivo:** o avaliador só lê texto, e evidência reprodutível vale mais que saída colada à mão. A degradação segura é um argumento de risco forte para as duas personas do roleplay.

## D-013: Estrutura do repositório e deploy com DAB mais script de provisionamento

**Data:** 2026-11-20

**Escolha:**
- **Repositório:** pensado para o avaliador, com o negócio primeiro, depois a arquitetura, o código e a prova (`src/`, `app/`, `notebooks/`, `evidencias/`, `testes/`, `scripts/`, `docs/`, `deck/`).
- **Compute:** tudo serverless.
- **DAB:** pipeline, jobs, app, endpoint e experimentos.
- **`scripts/provisionar.py`, idempotente:** o que o DAB não cobre ou não cobre bem (Lakebase e synced tables, Lakehouse Sync, Genie, metric views, governança), conferido item a item.
- **Jobs:** `job_evento` é disparado por chegada de arquivo; `job_retreino` roda diariamente.
- **Git:** commits locais a cada marco. O repo público e cada push dependem da autorização do autor.

**Motivo:** reprodutibilidade com poucos comandos, sem forçar no DAB recursos que ele não suporta (o recurso de synced tables no DAB está descontinuado).

## D-014: Modelo de suspeita treinado em um histórico de 2025, separado do evento de 2026

**Data:** 2026-11-20

**Alternativa considerada:** treinar com parte dos próprios avisos do evento de 2026, usando os rótulos do gabarito.

**Escolha:**
- Gerar um histórico sintético de ~20 mil sinistros já regulados em 2025, com o clima real do INMET 2025 e os itens já estruturados, sem PDF.
- Treinar o `champion` nesse histórico e aplicá-lo ao evento de 2026.
- O gabarito do evento é usado apenas na avaliação e nunca como feature.

**Motivo:**
- É o fluxo realista: a seguradora treina com o passado e aplica no evento novo.
- Evita vazamento de rótulo.
- Aproveita os dados do INMET de 2025, que já foram baixados e analisados.

## D-015: Ocorrências da Defesa Civil como peso geográfico e como segunda fonte de evidência climática

**Data:** 2026-11-20

**Contexto:** a busca na web (agora funcionando) trouxe os balanços da Defesa Civil de SC para dois episódios: de 28/08 a 01/09, com Florianópolis (3.749 moradias) e Biguaçu (~3.255), e de 27 a 29/09, com o Oeste e o Meio-Oeste, incluindo Seara (1.344). A estação do INMET de **Florianópolis não tem dados** no período. Com o INMET como única fonte, a cidade mais atingida ficaria inteira com evidência "fraca", e a meta de ~30% de fast track se tornaria inviável.

**Alternativas consideradas:**
- Usar só o INMET e aceitar uma taxa baixa de fast track. Isso distorce o caso de negócio.
- Interpolar o clima entre estações distantes. A interpolação é pouco confiável para um fenômeno local como o granizo e é difícil de explicar ao segurado.

**Escolha:**
- **(1) Pesos geográficos:** os avisos legítimos sintéticos seguem a geografia e as datas reais dos episódios, em proporção às moradias atingidas.
- **(2) Segunda fonte de evidência:** a evidência climática é `forte` quando o INMET (a até 30 km, com sinal) **ou** a Defesa Civil (ocorrência no município dentro da janela) confirmam o evento. Cada sinistro registra a fonte que confirmou.

**Motivo:** é o que as seguradoras fazem na prática, aceitando o decreto ou registro da Defesa Civil como prova do evento. O caso fica fiel aos dados públicos reais e a solução fica mais justa com o segurado. Os dados curados, com as fontes, estão em `docs/dados/defesa-civil-sc-2026.md`.

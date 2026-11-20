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

## D-016: Nomes de catálogo e schemas parametrizados (sem nome fixo no código)

**Data:** 2026-11-20

**Contexto:** no workspace FEVM, o `CREATE CATALOG` falhou: o usuário não tem essa permissão no metastore compartilhado. O FEVM já cria, junto com o workspace, o catálogo `fe_bar_sinistros_catalog`, em que o usuário tem ALL_PRIVILEGES. O plano previa o nome fixo `sinistros_clima` em scripts, SQL, caminhos de Volume e bundle.

**Alternativas consideradas:**
- Criar pelo FEVM um catálogo standalone `sinistros_clima` (TTL de 90 dias). Isso mantém o nome, mas cria mais um recurso para gerenciar e continua amarrando o código a um nome.
- Trocar o nome fixo por `fe_bar_sinistros_catalog`. Funciona só neste workspace e o asset deixa de ser reutilizável.

**Escolha:** usar o catálogo do FEVM e **parametrizar** os nomes:
- `FE_BAR_CATALOGO` define o catálogo (padrão `sinistros_clima`; no FEVM, `fe_bar_sinistros_catalog`);
- `FE_BAR_PREFIXO_SCHEMA` é um prefixo opcional dos schemas (padrão vazio), para várias instalações no mesmo catálogo;
- o módulo `src/ambiente` é a fonte única dos nomes em Python; os `.sql` usam os placeholders `${catalogo}` e `${schema_<camada>}`, preenchidos pelo `executar_sql.py`, que falha se faltar valor; o bundle usa as variáveis `catalogo` e `prefixo_schema` (o target `dev` define o catálogo do FEVM);
- o `CREATE CATALOG` ficou em `src/governanca/00_catalogo_opcional.sql`, para workspaces em que há permissão.

**Motivo:** o asset fica reutilizável em qualquer workspace ou cliente só com a troca do `.env` e das variáveis do bundle. Um teste garante que nenhum `.sql` do projeto tenha placeholder sem valor ou nome do FEVM fixo.

## D-017: Resultado das verificações do workspace (spec, seção 12)

**Data:** 2026-11-20

**Contexto:** as verificações rodaram no workspace FEVM com `scripts/verificar_recursos.py`. A evidência está em `evidencias/00a-verificacoes-ambiente.md`. A seção 12 da spec define uma regra de decisão para cada item.

**Escolhas:**
- **Modelo do parecer:** `databricks-claude-sonnet-5-5`, o Claude Sonnet mais recente entre os disponíveis (`4-5`, `4-6`, `5` e `5-5`). O endpoint está `READY` e respondeu a um `ai_query` de teste.
- **Governança:** usar **políticas ABAC** baseadas em tags, porque o `SHOW POLICIES` executou. Se a criação da política falhar na fase 7, o plano B continua sendo as funções de máscara e de filtro por tabela.
- **DAB:** o schema do bundle (CLI 1.25) aceita todos os recursos verificados: pipelines, jobs, apps, endpoints, experimentos, modelos registrados, `postgres_projects`, `postgres_synced_tables`, `genie_spaces`, dashboards, volumes e schemas. Esses recursos vão para o bundle, o que reduz o escopo do `provisionar.py` (D-013) ao que o DAB não declara: metric views, tags e grants de governança e a ativação do Lakehouse Sync. As synced tables usam `postgres_synced_tables`, não o recurso descontinuado `synced_database_tables`.
- **`ai_parse_document`:** funciona. Ele extraiu o texto de um PDF de teste com acentos e valores em reais.
- **Custo de `ai_parse_document` e `ai_query`:** ainda não medido. Na fase 2, o pipeline roda primeiro com o lote 1 (800 avisos), e o custo é medido em `system.billing` antes de publicar os demais lotes.
- **Lakehouse Sync:** a API de CDF está presente no SDK, e a ativação real fica para a fase 6. O plano B (job agendado de Lakebase para Delta) continua valendo.

**Motivo:** aplicar as regras da spec com o que foi medido no workspace, sem supor disponibilidade.

## D-018: Ajustes da revisão independente das fases 0 e 1

**Data:** 2026-11-20

**Contexto:** a revisão independente ao fim da fase 1, feita antes de enviar os dados ao Volume, não encontrou nada crítico e apontou seis pontos importantes. Todos mudavam o conteúdo dos dados e foram corrigidos antes do upload, cada um com um teste que falhou antes da correção.

**Escolhas:**
- **Carteira de apólices (spec 4.2):** 40% da carteira é proporcional à **população do Censo 2022** (IBGE, tabela 4709, agora em `municipios_sc.csv`). Os outros 60% refletem a concentração regional da Vértice Seguros (fictícia) nos municípios atingidos, pelo peso da Defesa Civil. *Alternativa descartada:* 100% proporcional à população. Com 8 mil avisos concentrados em poucos municípios (premissa do caso), Biguaçu, com ~76 mil habitantes, teria mais avisos do que apólices. *Trade-off:* a Vértice é uma seguradora regional forte na Grande Florianópolis e no Oeste. Joinville, Blumenau e Chapecó passam a ter carteira grande e poucos sinistros, o que deixa a análise exposição × sinistralidade realista no Genie.
- **Regra `contraria` (spec 4.3):** `contraria` exige estação válida **sem nenhum sinal**. Sinal parcial (ex.: chuva intensa sem rajada forte num aviso de granizo) agora é **inconclusivo** e vira `fraca`, indo para o regulador.
- **Sinal de granizo:** o "sinal compatível" é a tempestade severa no período (chuva ≥ 10 mm/h **e** rajada ≥ 15 m/s, em qualquer hora da janela). O indicador horário `granizo_provavel` (as três condições na mesma hora, com queda de temperatura) é mais estrito e fica como detalhe para o parecer, não como condição da evidência. *Motivo:* as estações ficam a dezenas de km do local, e exigir as três condições na mesma hora marcaria como sem sinal a maior parte do granizo real.
- **Histórico 2025:** os sinistros "sem estação" (20% do histórico) agora só nascem em local e data com evidência `fraca`, nunca `contraria`. O rótulo (`padrao` e `motivo_decisao`) saiu do landing e foi para `restrito/gabarito_historico_2025.csv`. No landing ficam só a decisão final e o valor pago, como numa base real de sinistros regulados.
- **Layout do Volume:** uma pasta por entidade (`apolices/`, `segurados/`, `apolices_coberturas/`, `historico_sinistros/`, `clima_horario/` etc.), cada uma com um único schema, para um Auto Loader por pasta (spec 5).
- **Publicação dos lotes:** o estado fica num arquivo por destino e guarda a impressão digital da geração. Publicar uma geração diferente no mesmo destino é recusado, e o gerador se recusa a apagar uma saída que já tem lotes publicados (opção `--forcar`).

**Motivo:** a spec é a autoridade. Corrigir antes do upload evita reenviar tudo e reiniciar os checkpoints do pipeline nas fases seguintes.

## D-019: Desenho do pipeline bronze e silver (fase 2)

**Data:** 2026-11-20

**Contexto:** a spec 5 descreve a silver com `ai_parse_document` seguido de `ai_query` e um conjunto mínimo de tabelas. Na implementação surgiram escolhas de função, de granularidade das tabelas e de onde as regras de negócio rodam.

**Escolhas:**
- **`ai_extract` (v2.1) em vez de `ai_query` para extrair os documentos.** É a função específica para extração estruturada: não exige escolher endpoint, aceita schema com itens aninhados e recebe instruções em português (formato "R$ 1.925,00", descrição copiada como está no documento). O `ai_query` fica reservado para o parecer (fase 4), que precisa de um modelo e de um prompt versionados.
- **Tabelas silver adicionais:**
  - `documentos_texto` separa o OCR da extração, para reprocessar só a extração quando as instruções mudarem;
  - `documentos_resumo` concentra os itens casados com a tabela de preços e o desvio;
  - `evidencia_climatica` isola a regra de duas fontes;
  - `clima_estacao_dia` substitui `clima_municipio_dia`, porque a evidência usa a estação válida mais próxima **do local do sinistro**, por variável, e não um clima por município.
- **Regras Python reaproveitadas no pipeline:**
  - a agregação diária do INMET e a evidência climática rodam com `applyInPandas` chamando `src/regras`, as mesmas funções do gerador;
  - as regras chegam ao pipeline como **wheel do projeto num Volume do UC** (`ml/artefatos/<hash>/`, publicado por `scripts/publicar_pacote.py`), instalado com `--no-deps`, porque pandas e numpy já estão no ambiente. Duas tentativas falharam antes:
    - `--editable` do projeto inteiro;
    - `root_path` em `src/`.
    As duas falharam pelo mesmo motivo: o compute serverless do pipeline não lê os arquivos do workspace fora das próprias fontes (`EIO`). O hash no caminho impede que um wheel antigo seja reaproveitado;
  - o pipeline roda com `development: true`: sem a cadeia de retentativas automáticas e com início mais rápido (não muda nomes);
  - um teste de paridade confere, aviso a aviso, que a evidência no formato do pipeline é idêntica à do gabarito.
- **Nada é descartado:** as expectations só medem (warn), e as violações viram `alertas_qualidade` e `flags_documento` no sinistro, que vai ao regulador (spec 10.3).
- **Só o lote 1 nesta fase (D-017):** 800 avisos e 951 PDFs, com o custo medido antes dos demais lotes. Os lotes 2 a 10 chegam na fase 5, pelo `job_evento` disparado por chegada de arquivo, que é a demonstração do pico do evento.

**Resultado no lote 1 (`evidencias/01-ingestao.md`):**
- a evidência climática bateu com o gabarito nos 800 avisos;
- o total do orçamento extraído pela IA bateu em 100% dos avisos, e 99,1% dos itens casaram com a tabela de preços;
- o orçamento inflado aparece com desvio médio de +82% (todos sinalizados), contra +2% nos legítimos;
- os 9 laudos de dano preexistente foram detectados.

**Motivo:** menor custo e reprocessamento seletivo, uma única implementação das regras (sem divergência entre gerador e pipeline) e fidelidade à regra da spec de que toda falha vai para o regulador.

## D-020: Pendências da revisão da fase 2 que dependem de decisões de modelagem

**Data:** 2026-11-20

**Contexto:** a revisão independente da fase 2 apontou dois pontos que não são defeitos do pipeline. São definições que as fases 3 a 5 precisam fixar antes de depender delas.

**Escolhas:**
- **`qtd_orcamentos_prestador` passa a ser point-in-time na fase 3.** Hoje a feature conta todos os avisos presentes, então o valor de um aviso antigo muda quando chegam os lotes seguintes, e a escala do histórico de 2025 (12 meses) difere da do evento.
  - **Antes do treino:** a feature será redefinida como a quantidade de avisos com orçamento do mesmo prestador nos N dias anteriores a `data_aviso`, calculada do mesmo jeito no histórico e no evento.
  - **Quem fecha:** o plano da fase 3 define N e o teste de igualdade entre treino e serving.
  - **Até lá:** a coluna atual é só descritiva.
- **Semântica dos alertas para a fase 5:** `alertas_qualidade` mistura alertas que bloqueiam e alertas informativos.
  - **Informativo:** `sem_estacao_no_raio` (68% do lote 1, a maioria em municípios com registro da Defesa Civil) não bloqueia o fast track quando a evidência é `forte` pela Defesa Civil. A D-015 foi criada justamente para esse caso.
  - **Bloqueiam o fast track:** `apolice_inexistente`, `fora_vigencia`, `datas_incoerentes`, `valor_invalido`, `causa_desconhecida` e as flags `documento_ilegivel`, `extracao_falhou`, `preco_nao_conferido` e `documento_ausente`.
- **Os desvios da spec registrados na D-019** (`ai_extract`, tabelas silver adicionais e `clima_estacao_dia`) ficam **para aprovação do autor**, porque o plano da fase 2 foi executado sem aprovação prévia.

**Motivo:** fixar essas definições antes do treino e do fast track evita divergência entre treino e serving e mantém a meta de fast track coerente com a regra de duas fontes.

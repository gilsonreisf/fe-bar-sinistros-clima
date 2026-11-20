# Spec de design: regulação inteligente de sinistros em eventos climáticos

**Data:** 2026-11-20
**Status:** em revisão pelo autor
**Contexto:** protótipo para o FE Bar. Todo o conteúdo é em português, e nenhum cliente específico é citado.
**Decisões relacionadas:** D-001 a D-015 em `docs/decisoes-e-tradeoffs.md`.

---

## 1. Problema de negócio e valor

**Setor:** seguros patrimoniais (residencial e empresarial) na América Latina.
**Comprador:** diretor(a) de sinistros de uma seguradora com carteira patrimonial.

Eventos de granizo e vendaval geram um pico de milhares de avisos de sinistro em poucos dias. A regulação manual, documental e por ordem de chegada causa três problemas ao mesmo tempo:

1. o segurado espera semanas pela indenização;
2. a seguradora faz pagamentos indevidos (*claims leakage*);
3. o custo de regulação explode, e a diretoria não sabe em tempo real quanto o evento custou.

**A solução:** cada aviso é priorizado e pré-analisado assim que chega. A IA lê os documentos, confronta o pedido com a apólice e com o clima real medido pelo INMET e sugere um parecer. Os casos simples seguem por fast track, e o regulador concentra o tempo nos casos de alto valor ou suspeitos. A diretoria acompanha o evento em linguagem natural.

**Valor de referência** (premissas nossas, a calibrar; detalhes em `docs/negocio/02-ganhos-kpis-e-personas.md`):
- **Cenário:** 8 mil avisos por evento × R$ 12 mil de ticket médio = R$ 96 mi avisados; 3 eventos por ano.
- *Leakage* −1 p.p. → ~R$ 1,0 mi por evento.
- Fast track em 30% dos casos × ~R$ 600 → ~R$ 1,4 mi por evento.
- Retenção +5 p.p. → ~R$ 0,6 mi por ano.
- **Total: ~R$ 2,4 mi por evento, ~R$ 7,8 mi por ano.**
- Tempo até a indenização cai de ~30 para ~7 dias.

**Personas:**
- Diretor(a) de sinistros: patrocinador e persona de negócio do roleplay.
- Gerente de regulação: dono do processo.
- Regulador: usuário diário.
- CFO e atuarial.
- Arquiteto ou TI: persona técnica do roleplay.

## 2. Escopo

**Dentro do escopo:**
- **Fluxo de dados:** ingestão (Lakeflow SDP), governança (UC), operação (Lakebase), inteligência (ML e GenAI), consulta em linguagem natural (Genie) e app de negócio (AppKit), tudo integrado.
- **Inteligência:** um modelo de suspeita com retreino a partir das decisões do regulador, e um parecer de IA servido como endpoint, avaliado com MLflow.
- **Prova:** evidências de execução em texto, deck e roteiro de demo.

**Fora do escopo:**
- seguro de automóvel;
- integração com sistemas legados reais de sinistros;
- pagamento efetivo;
- processamento de imagens ou fotos de danos;
- qualquer dado real de cliente.

## 3. Arquitetura (D-005)

```
Volume UC landing/ ──Auto Loader──▶ BRONZE ──▶ SILVER ──▶ GOLD ──synced table──▶ LAKEBASE fila
 (avisos, PDFs,                      (SDP serverless)        │                        │
  apólices, INMET, IBGE)             ai_parse_document       │ score ML (UC champion) │ app grava
                                     cruzamento clima        │ parecer (endpoint)     ▼
                                                             │ prioridade/fast track  operacao.decisoes_regulador
                                                             ▼                        │
                                                   metric views ──▶ GENIE             │ Lakehouse Sync (SCD2)
                                                             │                        ▼
                                                             └──▶ DATABRICKS APP ◀── UC: histórico de decisões
                                                                                      → retreino + acurácia IA
```

**Fluxo:**
1. `simular_evento.py` solta lotes de avisos e PDFs no Volume.
2. O `job_evento` é disparado pela chegada de arquivos e roda o pipeline: bronze, silver (extração dos PDFs e cruzamento com apólice e clima) e gold (score, parecer, prioridade).
3. As synced tables são atualizadas e a fila aparece no app.
4. O regulador decide no app, e a decisão é gravada no Lakebase.
5. O Lakehouse Sync leva a decisão ao UC, onde ela alimenta o retreino e o painel de acurácia da IA.

Um único lineage no UC vai do JSON bruto até a decisão.

## 4. Dados (D-007)

### 4.1 Fontes públicas
- **INMET:** dados horários das estações automáticas de SC.
  - `2026.zip`, de 01/01 a 31/10/2026: é o **evento**, a temporada de granizo e vendaval de agosto e setembro de 2026.
  - `2025.zip`: é o **histórico** usado para treinar o modelo.
  - A cobertura é parcial (veja `docs/dados/inmet-cobertura-sc.md`). O INMET não mede granizo.
- **IBGE:** municípios de SC, com código, nome e coordenadas.
- **Defesa Civil de SC:** ocorrências por município e por episódio, com moradias atingidas, curadas a partir dos boletins oficiais e da imprensa, com a fonte registrada em cada linha (veja `docs/dados/defesa-civil-sc-2026.md`). Os dados são usados de duas formas: como peso geográfico e temporal dos avisos sintéticos e como segunda fonte de evidência climática (D-015).

### 4.2 Dados sintéticos
O gerador usa Faker pt_BR e reportlab, com seed fixa.

| Entidade | Volume | Observações |
|---|---|---|
| Segurados | ~50 mil | CPF fictício em formato válido, endereço com município e coordenadas |
| Corretores | ~300 | |
| Apólices | ~60 mil | Ramo residencial ou empresarial; coberturas (vendaval, granizo, danos elétricos, alagamento) com LMI e franquia; vigência; prêmio; corretor |
| Tabela de preços de referência | ~200 itens e serviços | Inspirada no SINAPI |
| **Histórico de sinistros regulados (2025)** | ~20 mil | Com decisão final e itens já estruturados, sem PDF. É a base de treino do modelo, com clima do INMET 2025 |
| **Avisos do evento (2026)** | ~8 mil, em ~10 lotes | Em JSON, com descrição em texto livre |
| PDFs do evento | 1 orçamento por aviso, mais laudo quando o valor reclamado passa de R$ 20 mil | Texto em formato livre e realista |

**Geografia e datas reais guiando os dados sintéticos (D-015):**
- **Episódio 1, de 28/08 a 01/09/2026:** Grande Florianópolis (Florianópolis e Biguaçu) e Oeste (Ipuaçu, São José do Cedro, Bom Jesus e outros).
- **Episódio 2, de 27 a 29/09/2026:** Oeste e Meio-Oeste (Seara, Ponte Serrada, Santiago do Sul, Anita Garibaldi e outros).
- **Distribuição dos avisos legítimos:** ~90% vão para os municípios com registro da Defesa Civil, em proporção às moradias atingidas. Os municípios sem número publicado recebem um peso mínimo (equivalente a 20 moradias). As datas de ocorrência caem dentro de cada episódio.
- **Os ~10% restantes:** ocorrências menores espalhadas por agosto e setembro (Bela Vista do Toldo, Capinzal e outras), nas datas em que o INMET registrou sinal.
- **Padrão "sem evento climático":** gerado em municípios e datas **sem** registro da Defesa Civil **e** sem sinal do INMET.
- **Carteira de apólices:** distribuída pelos municípios de SC de forma proporcional à população (premissa nossa), para que a exposição seja realista.

**Distribuição de padrões**, igual no histórico e no evento:

| Padrão | % | Decisão esperada |
|---|---|---|
| `legitimo_simples` | ~60% | pagar integral (candidato a fast track) |
| `legitimo_complexo` | ~25% | pagar integral ou parcial, pelo regulador |
| `sem_evento_climatico` | ~3% | investigar ou recusar |
| `orcamento_inflado` | ~4% | pagar parcial (valor da referência) |
| `sem_cobertura` | ~3% | recusar |
| `apolice_recente` | ~2% | investigar |
| `dano_preexistente` | ~2% | pagar parcial ou recusar |
| `prestador_concentrado` | ~1% | investigar |

**Gabarito:** a tabela `ml.gabarito` guarda o padrão, a decisão esperada, o valor devido e o motivo de cada aviso. Ela **nunca é lida pelo pipeline de features**. É usada só como rótulo do histórico e como referência na avaliação, o que evita vazamento de rótulo.

### 4.3 Regras climáticas (valores de referência, calibráveis)
- **Estação usada:** para cada variável (chuva e rajada), a estação **válida mais próxima** do local do sinistro, com a distância registrada.
- **Indicador de granizo provável** (o INMET não mede granizo), quando ocorrem juntos:
  - chuva ≥ 10 mm/h;
  - rajada ≥ 15 m/s;
  - queda de temperatura ≥ 4 °C em até 2 horas.
- **Força da evidência climática** na janela de D−1 a D+1 da data de ocorrência, combinando **duas fontes** (D-015):
  - `forte`: há uma estação do INMET válida a até 30 km com sinal compatível com a causa declarada, **ou** há registro de ocorrência da Defesa Civil no município dentro da janela;
  - `fraca`: nenhuma das duas fontes confirma o evento, e falta dado (estação a mais de 30 km ou variável ausente);
  - `contraria`: há uma estação válida a até 30 km sem nenhum sinal **e** não há registro da Defesa Civil.
- **Fonte registrada:** cada sinistro guarda qual fonte confirmou o evento (`inmet`, `defesa_civil` ou `ambas`), para auditoria e para o parecer.
- **Evidência fraca nunca leva à recusa.** O caso vai para o regulador.

### 4.4 Modelo de dados
Catálogo configurável: `FE_BAR_CATALOGO`, com padrão `sinistros_clima` (no FEVM, `fe_bar_sinistros_catalog`). Os schemas abaixo aceitam um prefixo opcional (`FE_BAR_PREFIXO_SCHEMA`, padrão vazio). Nenhum nome fica fixo no código (D-016).

| Schema | Objetos |
|---|---|
| `landing` | Volume `arquivos` com `avisos/`, `documentos/`, `apolices/`, `clima/`, `referencias/` |
| `bronze` | `avisos`, `apolices`, `segurados`, `corretores`, `documentos` (binário), `clima_inmet`, `municipios`, `ocorrencias_defesa_civil`, `precos_referencia`, `historico_sinistros` |
| `silver` | `avisos`, `apolices_coberturas`, `documentos_extraidos`, `clima_municipio_dia`, `sinistros_enriquecidos` |
| `gold` | `sinistros_analisados`, `fila_regulacao`, `sinistro_detalhe`, `kpis_evento`, `decisoes_regulador`, `acuracia_ia`, `mv_sinistros`, `mv_exposicao` |
| `ml` | `gabarito`, `features_treino`, `avaliacao_parecer_dataset`, o modelo `modelo_suspeita`, o modelo `parecer_sinistro` e o prompt `prompt_parecer` |
| `operacional` | Tabelas `lb_*_history` do Lakehouse Sync |

**Campos-chave:**
- **Aviso:** `id_aviso`, `id_apolice`, `cpf_segurado`, `data_ocorrencia`, `data_aviso`, `causa_declarada`, `descricao`, `valor_reclamado`, `canal`, `municipio`, `lat`, `lon`, `documentos[]`.
- **Sinistro enriquecido:** os campos do aviso mais `cobertura_valida`, `lmi`, `franquia`, `dias_desde_contratacao`, `forca_evidencia_climatica`, `fonte_evidencia`, `distancia_estacao_km`, `chuva_mm`, `rajada_max_ms`, `granizo_provavel`, `desvio_preco_pct`, `qtd_orcamentos_prestador`, `flags_documento[]`.
- **Sinistro analisado:** os campos anteriores mais `score_suspeita`, `versao_modelo`, `recomendacao_ia`, `valor_sugerido`, `motivos[]`, `clausulas[]`, `confianca`, `versao_prompt`, `trace_id`, `status_parecer`, `prioridade`, `fast_track`.

## 5. Pipeline Lakeflow (SDP, serverless)
- **Bronze:** Auto Loader por pasta do Volume, mais as colunas de metadados (arquivo e momento da ingestão).
- **Silver:**
  - tipagem e limpeza;
  - `ai_parse_document` nos PDFs, seguido de `ai_query` com saída em JSON estruturado para extrair itens, valores, prestador e menções relevantes;
  - cruzamento do aviso com a apólice e suas coberturas;
  - associação com a estação válida mais próxima por variável e cálculo da evidência climática.
- **Gold:**
  - score do `modelo_suspeita@champion`;
  - parecer via `ai_query` no endpoint `parecer_sinistro`, com `failOnError => false`;
  - regra de prioridade e de fast track;
  - tabelas da fila e de KPIs.
- **Expectations:** apólice existente, datas coerentes (ocorrência ≤ aviso, ocorrência dentro da vigência), valor > 0, PDF lido com sucesso e estação dentro do raio. As violações geram flags e métricas e não descartam o sinistro em silêncio.

## 6. Inteligência

### 6.1 Modelo de suspeita (D-014)
- **Algoritmo:** LightGBM, treinado no histórico de 2025. O alvo é "suspeito": todos os padrões diferentes de `legitimo_*`.
- **Features:** valor em relação ao LMI, desvio de preço, dias desde a contratação, força da evidência climática, chuva, rajada, distância até a estação, compatibilidade entre causa e cobertura, concentração no prestador e flags dos documentos.
- **Registro no MLflow:**
  - parâmetros e métricas (AUC, precisão e recall nos 10% mais suspeitos);
  - `log_input` com a versão da tabela Delta;
  - assinatura;
  - artefatos: curvas ROC e PR, matriz de confusão e SHAP.
- **No UC:** `ml.modelo_suspeita`, com os aliases `champion` e `challenger`.
- **Retreino:** o `job_retreino` usa como rótulos as decisões do regulador (via Lakehouse Sync) e o histórico. O `challenger` só é promovido se tiver AUC maior que o `champion` atual no mesmo conjunto de teste.

### 6.2 Parecer prévio (D-008)
- **Entrada da função `gerar_parecer()`:** o sinistro enriquecido, as coberturas da apólice, a evidência climática e os itens extraídos.
- **Saída:** um JSON validado por schema, com:
  - `recomendacao`, entre `pagar_integral`, `pagar_parcial`, `recusar` e `investigar`;
  - `valor_sugerido`;
  - `motivos[]`;
  - `clausulas[]`;
  - `confianca`.
- **Prompt:** em `ml.prompt_parecer`, no MLflow Prompt Registry, com versões e aliases.
- **LLM:** um modelo fundacional do workspace via Foundation Model API. **Regra de escolha:** o modelo Claude Sonnet mais recente disponível no FEVM; a escolha é registrada nas decisões.
- **Empacotamento e serviço:** modelo MLflow (*models from code*) registrado como `ml.parecer_sinistro` e servido em um endpoint do Model Serving (CPU pequena, scale-to-zero), com tracing e AI Gateway (inference tables e acompanhamento de uso).
- **Quem consome:** o pipeline, em lote via `ai_query`, e o botão "Reanalisar com IA" do app.
- **Rastreabilidade:** cada linha registra a versão do modelo, a versão do prompt e o `trace_id`.
- **Governança:** a IA nunca recusa sozinha. `recusar` e `investigar` são sempre encaminhados ao regulador.

### 6.3 Prioridade e fast track
- **Fast track:** o sinistro vai direto quando cumpre todas as condições:
  - valor reclamado ≤ R$ 5 mil;
  - `cobertura_valida`;
  - evidência `forte`;
  - `score_suspeita` < 0,2;
  - recomendação `pagar_integral`;
  - `status_parecer = ok`.
- **Prioridade dos demais:** é a soma ponderada do valor normalizado, do score de suspeita e dos dias de espera. Os pesos ficam configuráveis.

### 6.4 Avaliação com MLflow (D-006)
- **Dataset:** um MLflow Evaluation Dataset em UC (`ml.avaliacao_parecer_dataset`) com ~200 casos estratificados, cobrindo todos os padrões.
- **Avaliação com `mlflow.genai.evaluate()`:**
  - **Métricas calculadas por código:** `recomendacao_correta`, `valor_dentro_tolerancia` (±10%), `padrao_identificado`, `json_valido` e `cita_clausula`.
  - **Juízes LLM:** `Correctness` (fatos esperados) e `Guidelines` (português formal, não recusar sem evidência, citar a cobertura, tom adequado ao segurado).
- **O que fica logado:**
  - um trace por caso;
  - as métricas agregadas;
  - os artefatos: matriz de confusão das recomendações, acurácia por padrão, tabela de erros e relatório;
  - o vínculo com a versão do prompt, do modelo e do dataset.
- **Iteração:** o prompt v1 (básico) é comparado ao v2 (regras explícitas e exemplos) no mesmo experimento.
- **Portão de qualidade:** uma nova versão do prompt só ganha o alias de produção se `recomendacao_correta` for maior ou igual à da versão atual.
- **Exportação:** os resultados também vão em Markdown e CSV para `evidencias/05-avaliacao-genai.md`.

## 7. Lakebase e app (D-009)

### 7.1 Lakebase
- **Projeto:** `sinistros-clima`, branch `production`.
- **`fila.fila_regulacao` e `fila.sinistro_detalhe`:** synced tables vindas do gold, em modo Triggered, atualizadas pelo `job_evento` depois do pipeline. São somente leitura.
- **`operacao.atribuicoes`:** quando o regulador assume um sinistro, o app usa `SELECT … FOR UPDATE SKIP LOCKED`, de modo que dois reguladores nunca peguem o mesmo caso.
- **`operacao.decisoes_regulador`:** recebe **apenas inserções**. Os campos são `id_decisao` (UUID gerado no cliente, com restrição de unicidade), `id_aviso`, `regulador`, `decisao`, `valor_aprovado`, `motivo`, `concordou_com_ia`, `versao_modelo`, `versao_prompt`, `trace_id` e `criado_em`.
- **`operacao.reanalises`:** o resultado de cada "Reanalisar com IA", com `trace_id`.
- **Volta ao lakehouse:** o Lakehouse Sync (Beta) leva o schema `operacao` para `<catálogo>.operacional`, como histórico SCD2. **Plano B**, se o recurso não estiver disponível: um job agendado lê o Lakebase e grava em Delta.

### 7.2 App (AppKit, React + TypeScript)

| Tela | Persona | Fonte de dados | Conteúdo |
|---|---|---|---|
| Painel do evento | Diretoria | SQL Warehouse (metric views) | Avisado, regulado e pago; % fast track; tempo até a indenização; *leakage* evitado; distribuição por município e por causa |
| Fila de regulação | Regulador | Lakebase | Lista priorizada com filtros e o botão "Assumir próximo" |
| Detalhe do sinistro | Regulador | Lakebase e endpoint | Aviso, apólice e coberturas; evidência climática; itens comparados com a referência; score e SHAP; parecer com link para o trace; decisão; "Reanalisar com IA" |
| Pergunte ao Genie | Diretoria e gerente | Genie | Conversa embutida no app |
| IA sob supervisão | Gerente de regulação | SQL Warehouse | Concordância entre IA e regulador ao longo do tempo e por padrão, com as versões em uso |

**Autenticação:** o service principal do app acessa o Lakebase e o endpoint. As consultas analíticas e o Genie rodam em nome do usuário (on-behalf-of), para que as máscaras e filtros do UC valham por pessoa.

## 8. Genie e metric views (D-010)
- **`gold.mv_sinistros`:**
  - dimensões: município, região, causa, ramo, faixa de valor, data do aviso, status, fast track, padrão de suspeita, corretor e força da evidência;
  - medidas: avisos, valor avisado, valor aprovado, valor pago, % fast track, tempo médio até a indenização, *leakage* evitado e % de concordância entre IA e regulador.
- **`gold.mv_exposicao`:** apólices vigentes cruzadas com o clima por município e dia; mostra as apólices expostas, o LMI exposto e o prêmio exposto.
- **Genie Agent "Sinistros Clima — Diretoria":**
  - fontes: as duas metric views mais as tabelas de municípios e estações;
  - glossário e instruções em português;
  - de 6 a 8 consultas de exemplo;
  - ~15 benchmarks, com o resultado exportado para `evidencias/06-genie.md`.

## 9. Governança (D-011)
- **Grupos:** `grp_engenharia_dados`, `grp_regulacao`, `grp_diretoria_sinistros` e `grp_atuarial`, mais o service principal do app. As permissões ficam no catálogo e nos schemas.
- **Tags LGPD:** `classificacao_lgpd = dado_pessoal` em CPF, nome, endereço e telefone.
- **Máscaras:** CPF parcial; endereço reduzido a município e UF para quem não é da regulação.
- **Filtro de linha:** cada regulador vê só a sua regional.
- **Abordagem:** políticas ABAC baseadas nas tags, se o FEVM tiver; senão, funções de máscara e de filtro aplicadas por tabela. A escolha é registrada nas decisões.
- **Simulação das personas:** o FEVM tem um único usuário humano, então as personas são representadas por grupos e service principals de teste, com `is_account_group_member()`.
- **Rastreabilidade:** lineage do UC, auditoria em `system.access.audit` e `system.access.table_lineage`, histórico SCD2 das decisões e `trace_id`.
- **Higiene:** comentários em português em todas as tabelas e colunas, nenhum segredo no código e declaração no README de que os dados são sintéticos ou públicos.

## 10. Evidências, testes e erros (D-012)

### 10.1 Evidências (em texto)
- Notebooks commitados em `.ipynb` com as saídas, mais uma cópia em `.py`.
- `evidencias/` com os arquivos de 01 a 09, gerados por `scripts/coletar_evidencias.py`:
  - `01-ingestao`
  - `02-governanca`
  - `03-lakebase`
  - `04-ml`
  - `05-avaliacao-genai`
  - `06-genie`
  - `07-app`
  - `08-rastreio-ponta-a-ponta`: um sinistro acompanhado por todas as camadas
  - `09-custo-real`: medido em `system.billing.usage`

### 10.2 Testes
- Expectations no pipeline.
- pytest para:
  - as regras de fast track e de prioridade;
  - a validação do JSON do parecer, com o LLM simulado;
  - o cálculo de distância até a estação;
  - a regra de evidência climática;
  - as proporções do gerador sintético.
- Teste de ponta a ponta com 50 avisos: confere a chegada na fila do Lakebase, a gravação da decisão e o retorno ao UC.
- App: checagem de tipos, build e testes rápidos das rotas da API.
- Portões de promoção do modelo e do prompt (seções 6.1 e 6.4).

### 10.3 Tratamento de erros
O princípio é que toda falha leva o sinistro ao regulador.

| Falha | Tratamento |
|---|---|
| Endpoint do parecer indisponível | `status_parecer = pendente`, sem fast track, com nova tentativa pelo job |
| JSON inválido | Validação de schema; recomendação `investigar`, com o motivo registrado |
| PDF ilegível | Flag `documento_ilegivel`; vai para o regulador |
| Sem estação climática válida | Evidência `fraca`; vai para o regulador |
| Lakebase acordando ou token expirado | Nova tentativa com espera crescente e renovação do token OAuth |
| Clique duplo em "Decidir" | `id_decisao` gerado no cliente, com restrição de unicidade |

## 11. Repositório e deploy (D-013)
- **Estrutura:** `README.md`, `databricks.yml`, `recursos/`, `src/` (`dados_sinteticos`, `pipeline`, `ml`, `parecer`, `lakebase`, `governanca`, `metricas`, `genie`), `app/`, `notebooks/`, `evidencias/`, `testes/`, `scripts/`, `docs/` (com `arquitetura.md`, `uso-de-ia.md` e `roteiro-demo.md`), `deck/` e `_interno/` (este último não versionado).
- **Compute:** tudo serverless.
- **Deploy:**
  - o DAB cobre o pipeline, os jobs, o app, o endpoint e os experimentos;
  - o `scripts/provisionar.py`, idempotente, cobre o que o DAB não suporta: projeto Lakebase, synced tables, Lakehouse Sync, Genie, metric views e governança;
  - a cobertura do DAB é conferida item a item, e o DAB é usado sempre que houver suporte.
- **Jobs:** `job_preparacao`, `job_evento` (disparado por chegada de arquivo), `job_treino_modelo`, `job_avaliacao_parecer`, `job_retreino` (diário) e `job_evidencias`.
- **Como reproduzir:**
  1. `databricks bundle deploy -t dev`
  2. `python scripts/provisionar.py`
  3. `databricks bundle run job_preparacao`
  4. `python scripts/simular_evento.py --lotes 10`
- **Git:** commits locais a cada marco. Criar o repo público e fazer push exigem a autorização do autor, precedida de varredura de segredos e de dados reais.

## 12. Verificações no início da implementação
Cada item tem uma regra de decisão definida. O resultado é registrado em `docs/decisoes-e-tradeoffs.md`.

| Item | Se disponível | Se não disponível |
|---|---|---|
| Lakehouse Sync (Beta) no FEVM | Usar | Job agendado de Lakebase para Delta |
| Políticas ABAC no FEVM | Usar políticas baseadas em tags | Funções de máscara e de filtro por tabela |
| Suporte do DAB a cada recurso | Declarar no bundle | Criar em `provisionar.py` |
| Modelo fundacional para o parecer | Claude Sonnet mais recente no FEVM | Outro modelo fundacional disponível, com o motivo registrado |
| Custo do `ai_parse_document` e do `ai_query` | Rodar os 8 mil avisos | Primeiro rodar 500 avisos em dev para medir; reduzir o volume do evento se o custo medido for desproporcional |

## 13. Critérios de aceite, mapeados aos domínios do FE Bar

| Domínio | Critério |
|---|---|
| **Industry** | O problema é de cliente, específico de seguros patrimoniais, com KPIs do comprador quantificados, dados climáticos reais do INMET e ocorrências reais da Defesa Civil |
| **Product** | As seis camadas estão presentes e **conectadas** por um lineage único no UC; cada produto é usado no papel certo (Lakebase para OLTP, SQL Warehouse para análise, Genie sobre metric views) |
| **Build + AI Mindset** | Tudo foi executado com evidência em texto (`evidencias/` e notebooks com saída); modelo e prompt são versionados, avaliados e rastreáveis por `trace_id`; existe um laço de retorno; `docs/uso-de-ia.md` documenta como a IA foi usada no build |
| **Customer Skills** | O README e o deck abrem pelo problema e pelo valor; o roteiro tell-show-tell está em `docs/roteiro-demo.md`; as objeções das duas personas foram preparadas |

**Pronto para submissão quando:**
- o fluxo de ponta a ponta tiver rodado com o evento completo;
- os arquivos de 01 a 09 em `evidencias/` estiverem gerados;
- o app estiver publicado e funcionando;
- a avaliação v1 contra v2 estiver registrada;
- os benchmarks do Genie estiverem executados;
- o deck estiver em PDF;
- o repo público estiver legível.

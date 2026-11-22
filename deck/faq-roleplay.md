# Guia do roleplay: roteiro, números e perguntas prováveis

Preparação para a apresentação ao vivo (Yoodli, 20 a 30 minutos) para duas personas na mesma sala:

- **Diretora de sinistros** (negócio): patrocinadora, responde pela sinistralidade, pelo tempo até a indenização, pelas reclamações e pelo prazo da SUSEP. Vai perguntar de **custo, risco e tempo até o valor**.
- **Arquiteto de TI** (técnica): vai operar a solução. Vai perguntar de **arquitetura, qualidade do dado, segurança e integração**.

As speaker notes de cada slide (`N` ou `S` no deck) têm a fala completa. Este guia é a cola: roteiro com tempo, números para decorar e respostas curtas para as objeções, primeiro na altitude de negócio e depois com o detalhe técnico.

## 1. Roteiro em 15 minutos (tell, show, tell)

| Tempo | Slide | O que fazer | Frase âncora |
|---|---|---|---|
| 0:00 | 1. Capa | Enquadrar: quem está na sala, o momento do evento e o que vou mostrar | "Vou falar dos dias depois de uma enchente ou de um granizo." |
| 0:30 | 2. Resumo executivo | A história inteira em um slide; pergunta de descoberta | "Quanto do avisado no último evento foi pago sem precisar?" |
| 1:30 | 3. Problema | As três dores; perguntar qual doeu mais | "Qual desses três doeu mais no último evento de vocês?" |
| 3:00 | 4. Mensagem | Pausa | "Pagar em dias quem tem direito e segurar quem não tem." |
| 3:20 | 5. KPIs | Combinar a régua antes da demo | "Hoje e meta são referência nossa; a PoC troca pelos números de vocês." |
| 4:20 | 6. Como funciona | O caminho de um aviso em 4 passos | "A IA lê e recomenda, o código calcula, o regulador decide." |
| 5:20 | 7. Demo (tell) | Dizer o que vão ver e os dois momentos para prestar atenção | "Prestem atenção em quanto sai sem fila e em como o regulador decide." |
| 5:40 | App (show) | Painel, fila, detalhe, reanálise, decisão, supervisão e Genie | "O valor sai de cálculo, não do modelo de linguagem." |
| 14:30 | 8. Resultados (tell) | O que os números provam, com a ressalva dos dados sintéticos | "Treinado em 2025, testado em lotes que nunca viu." |
| 16:00 | 9 e 10. Valor | R$ 2,4 mi por evento e a composição | "Usei 30% de fast track, e não os 55% medidos." |
| 17:00 | 11. Custo | Menos de um centavo de dólar por sinistro | "O custo da plataforma não é o que decide este projeto." |
| 18:00 | 12. Confiança | Responder ao "e se a IA errar?" antes da pergunta | "Fora do fast track, toda decisão é humana." |
| 19:00 | 13 a 15. Técnico | Trocar de altitude: arquitetura, integração, LGPD e escala | "Diretora, o ponto para você é: uma plataforma, um catálogo." |
| 21:30 | 16 e 17. PoC e próximos passos | 6 semanas com um evento deles; três decisões | "Podemos marcar a reunião de escopo ainda esta semana?" |
| 22:30 | 18. Encerramento | Deixar na tela e abrir para perguntas | |

**Se o tempo apertar:** pule o slide 4 (mensagem) e o 10 (composição do valor), e fale da composição em uma frase no 9. Nunca pule o 2, o 12 nem o 17.

**Ordem da demo (9 minutos):**
1. **Painel do evento:** 7.612 avisos analisados, R$ 88,6 mi reclamados, 54% no fast track (R$ 8,9 mi liberados), 3.487 com o regulador, 1.142 suspeitos (R$ 23 mi reclamados) e R$ 4,8 mi de ajuste por evidência sugerido pela IA.
2. **Fila do regulador:** prioridade por suspeita, valor e espera, com o motivo de cada caso estar fora do fast track. Clicar em **Assumir próximo**.
3. **Detalhe:** parecer com motivos e cláusulas ao lado da apólice, do clima da estação do INMET, do preço contra a tabela e do prestador. CPF mascarado.
4. **Reanalisar com IA:** nova análise em segundos, com trace.
5. **Decidir:** registrar uma decisão divergindo da IA.
6. **IA sob supervisão:** concordância e matriz IA × regulador.
7. **Genie da diretoria** (link no cabeçalho): "Quais municípios concentram mais sinistros suspeitos?" e "Quanto a IA sugeriu ajustar por evidência?".

**Plano B (login ou rede falhando):** diga "enquanto o login conecta, vou mostrar o resultado", vá para o slide 8 e conte o caminho de um sinistro, do arquivo à decisão, pelo `evidencias/08-rastreio-ponta-a-ponta.md`.

## 2. Números para decorar

| Número | O que é | Fonte |
|---|---|---|
| 8 mil avisos, 9.705 PDFs | Evento sintético de granizo e vendaval em SC, sobre o clima real do INMET e da Defesa Civil | `evidencias/00b-geracao-dados.md` |
| 6.812 avisos | Os 9 lotes de teste, nunca vistos no treino | `evidencias/04c-teste-final.md` |
| 54,9% | Fast track nos lotes de teste (3.737 avisos, R$ 8,0 mi sem regulador) | idem |
| 11 de 954 | Suspeitos que passaram pelo fast track (R$ 23 mil) | idem |
| 15 × 33 | Suspeitos elegíveis liberados: modelo contra regra fixa | idem |
| 0,997 × 0,962 | AUC do modelo de suspeita contra a regra fixa | idem |
| 99,4% e 99,6% | Recomendações da IA iguais ao gabarito; valores a ±10% | idem |
| 66,4% → 95,1% | Acerto do prompt v1 para o v2, com os juízes do MLflow | `evidencias/05-avaliacao-genai.md` |
| 16 de 16 | Perguntas de referência da diretoria certas no Genie | `evidencias/06-genie.md` |
| ~26 min | Pipeline do evento inteiro até a silver (8 mil avisos e 9.705 PDFs lidos e cruzados), sem o parecer em lote | `docs/decisoes-e-tradeoffs.md` (D-023) |
| ~21 por minuto | Vazão do parecer no modelo pago por token: o gargalo medido | idem |
| US$ 0,007 | Custo por sinistro (PDFs, pipeline e parecer), preço de lista | `evidencias/09-custo-real.md` |
| ~US$ 52 | Custo de processamento de um evento de 8 mil avisos | idem |
| US$ 0,02 | Custo estimado de uma reanálise no app (modelo maior, pela contagem de tokens) | idem (D-022) |
| R$ 2,4 mi | Ganho de referência por evento (R$ 1,0 mi de *leakage* + R$ 1,4 mi de regulação) | `docs/negocio/02-ganhos-kpis-e-personas.md` |
| R$ 7,8 mi | Ganho de referência por ano (3 eventos + R$ 0,6 mi de renovação) | idem |
| 6 semanas | Duração proposta da PoC | slide 16 |

**Premissas de referência (nossas, a calibrar na PoC):** 8 mil avisos por evento, ticket médio de R$ 12 mil (R$ 96 mi avisados), 3 eventos por ano, prêmio de R$ 1.500, 30% de fast track, R$ 600 de custo de regulação por caso, 1 p.p. de *leakage* evitado e +5 p.p. de renovação.

## 3. Perguntas da diretora de sinistros

**"E se a IA errar e pagarmos fraude?"**
- Negócio: fora do fast track, a IA não paga nada; ela recomenda e o regulador decide. No teste, dos 954 suspeitos só 11 passaram pelo fast track (R$ 23 mil), contra R$ 8 milhões liberados sem regulador. É um risco pequeno, conhecido e auditável por amostragem.
- Detalhe: o fast track exige todas as condições ao mesmo tempo: valor até R$ 5 mil, cobertura válida, evidência climática forte (estação do INMET ou ocorrência da Defesa Civil), score de suspeita baixo, parecer de pagamento integral e nenhum alerta bloqueante (documento ilegível ou ausente, orçamento divergente, preço acima da tabela, dano anterior no laudo, apólice fora de vigência). Qualquer dado faltante bloqueia (D-023, D-028).

**"O regulador vai confiar? Ele vai resistir?"**
- A IA não substitui o regulador: tira dele a leitura de PDF e a fila por ordem de chegada. Ele vê os motivos, as cláusulas e as evidências, e pode divergir. A concordância é medida todo dia na tela de supervisão, e as divergências viram aprendizado para o modelo.
- Na PoC, um grupo pequeno de reguladores usa em paralelo ao processo atual, sem mudar nada da operação.

**"Os dados são sintéticos. Como sei que vale para nós?"**
- Concordo, é a pergunta certa. O clima e os municípios são reais (INMET, Defesa Civil, IBGE); os avisos e os padrões de fraude foram simulados por nós, e é por isso que o acerto é tão alto. Com dados reais, ele vai cair. Por isso a proposta é uma PoC com um evento que vocês já viveram, usando as decisões já tomadas pelos reguladores como gabarito.

**"Quanto custa? Quando se paga?"**
- O processamento custa cerca de US$ 0,007 por sinistro, uns US$ 52 para um evento de 8 mil avisos, medidos no faturamento a preço de lista. O ganho de referência é de R$ 2,4 milhões por evento. O custo da plataforma não é o que decide; o investimento real é o projeto e a mudança de processo, e a PoC dimensiona os dois.
- Se apertar: o custo fixo é o SQL Warehouse do painel e do Genie enquanto estiver ligado; o banco e o endpoint desligam sozinhos fora do evento.

**"De onde vem o R$ 2,4 milhões? Isso não é otimista?"**
- São premissas nossas, moderadas, e eu mostro a conta: 1 ponto percentual de *leakage* sobre R$ 96 milhões avisados (R$ 1,0 mi) e 2.400 casos no fast track a R$ 600 (R$ 1,4 mi). Usei 30% de fast track, e não os 55% medidos. O primeiro entregável da PoC é refazer essa conta com os números de vocês.

**"Quanto tempo até ver valor?"**
- Seis semanas para a decisão, com resultado medido num evento de vocês. Como a arquitetura já existe, o trabalho da PoC é ligar os dados reais e calibrar o modelo, e não construir do zero.

**"E o prazo da SUSEP?"**
- A espera pesa 20% na prioridade da fila (com 45% de suspeita e 35% de valor), então o caso antigo sobe. Uma regra explícita para o prazo da SUSEP é um ajuste da PoC. E o fast track tira metade dos casos da fila. O tempo até a indenização de ponta a ponta depende do fluxo de pagamento de vocês, e é um dos KPIs da PoC.

**"Vamos demitir reguladores?"**
- O ganho é capacidade elástica no pico: menos hora extra e menos regulação terceirizada no evento, e o regulador concentrado nos casos com valor ou suspeita. A decisão de quadro é de vocês; a solução não depende dela.

**"Por que a Databricks, e não um sistema de sinistros com IA embutida?"**
- Os dados de sinistro, apólice e clima já precisam estar juntos para a diretoria, a atuária e a subscrição. Aqui é uma plataforma só, governada, onde os mesmos dados alimentam a regulação, o painel, o Genie e, depois, a precificação por região. E a IA fica sob o controle de vocês: o modelo, o prompt e a avaliação são de vocês, e não uma caixa-preta.

**"E se a fraude se adaptar?"**
- O modelo é retreinado com as decisões dos reguladores, que voltam ao lakehouse. A tela de supervisão mostra quando a IA começa a divergir. Hoje o laço fecha até essa tela; o retreino automático é o próximo passo, e entra no escopo da PoC.

## 4. Perguntas do arquiteto de TI

**"Como integra com o nosso sistema de sinistros?"**
- Hoje, no protótipo, a entrada são arquivos num Volume com Auto Loader; em produção, o Lakeflow Connect lê do banco do sistema de sinistros por CDC, ou recebemos arquivos ou eventos. Saída: a tabela de decisões no Unity Catalog ou o Postgres do Lakebase, que o sistema de sinistros consulta por API. Nada exige trocar o sistema atual.

**"E a LGPD e a segurança?"**
- As colunas com dado pessoal têm tag no Unity Catalog. O CPF aparece mascarado numa visão dinâmica da gold. O Genie lê a gold, e o app tem permissão mínima: leitura da gold e da entrada do parecer, escrita só no schema `operacao` do Lakebase. Nenhum dos dois vê o CPF aberto. Auditoria e lineage ficam no catálogo, e cada parecer grava o modelo, o prompt e a versão usados. A reanálise do app passa pelo AI Gateway, com trace.
- O app roda com um service principal de permissão mínima, e isso foi provado no deploy: o build falhou com `INSUFFICIENT_PERMISSIONS` antes do grant e passou depois.
- Limite honesto: no protótipo as consultas do app usam o service principal, sem a identidade do usuário (OBO). O caminho é o escopo `sql` do AppKit com consultas `.obo.sql` e grupos por persona (D-027).

**"E a qualidade do dado?"**
- O pipeline tem expectations. Documento ilegível, extração com falha, cobertura ausente ou parecer inválido viram flag e bloqueiam o fast track: toda falha leva o caso ao regulador (D-012). A saída do modelo de linguagem é JSON validado em código, com nova tentativa.

**"Aguenta o pico?"**
- Tudo é serverless e incremental: a chegada do arquivo dispara o job. O evento inteiro chegou à silver (PDFs lidos e cruzamentos feitos) em cerca de 26 minutos; o parecer em lote vem depois. O gargalo medido é a vazão do modelo pago por token, cerca de 21 pareceres por minuto. Em produção, isso se resolve com throughput provisionado, dimensionado na PoC. Se o parecer em lote passa do tempo, o job agenda a própria continuação.
- Limite honesto: na execução registrada, 7.612 dos 8.000 avisos (95,2%) tinham parecer no prazo; os 388 restantes entram na próxima execução e, até lá, não aparecem na fila.

**"Por que Lakebase, e não uma tabela Delta para a fila?"**
- A fila precisa de transação, chave primária e lock com latência de milissegundos: dois reguladores não podem pegar o mesmo caso, e o clique duplo não pode gravar duas decisões. Isso é OLTP. No teste, 6 pedidos simultâneos de dois reguladores entregaram 6 casos distintos. A gold chega ao Postgres por synced table, e as decisões voltam ao lakehouse pelo Lakehouse Sync. Testado com dois reguladores ao mesmo tempo (`evidencias/03-lakebase.md`).

**"Como vocês controlam o modelo de linguagem? E alucinação?"**
- O modelo recomenda, e o valor sai de código (franquia, limite e tabela de preços). O prompt é versionado e só vai para produção se passar no portão de avaliação do MLflow, com métricas de código e juízes (`Correctness` e `Guidelines`): do v1 para o v2, o acerto subiu de 66,4% para 95,1%. Cada parecer guarda o modelo e a versão do prompt; a reanálise do app tem trace e passa pelo AI Gateway.

**"E prompt injection? O segurado pode escrever qualquer coisa no aviso."**
- Risco conhecido e registrado: o texto do aviso e do laudo entra no prompt sem delimitação de dado não confiável. A mitigação é que o modelo sozinho não libera pagamento: o fast track é decidido por regras determinísticas, e um parecer fora do esperado manda o caso ao regulador. O próximo passo é delimitar a entrada e reavaliar o prompt pelo mesmo portão (D-028).

**"E se o modelo de linguagem mudar ou ficar mais caro?"**
- Prompt e modelo passam pelo mesmo portão de avaliação. Já fizemos essa troca com evidência: para o lote, o Haiku 5.5 empatou com o Sonnet na recomendação (95,1%) a cerca de US$ 0,002 por parecer; no app ficou o Sonnet, melhor no texto que o regulador lê (D-023).

**"Como o modelo de suspeita é mantido? Drift? Retreino?"**
- Treinado num histórico de 2025, registrado no Unity Catalog com o alias `champion` e um portão de promoção contra a regra fixa. As decisões dos reguladores voltam como rótulo. O retreino automático é o próximo passo (D-027), e a PoC define a cadência.

**"Como isso é implantado? Ambientes, CI/CD?"**
- Por Declarative Automation Bundles (pipeline, jobs, experimentos e o app), com nomes de catálogo e schema vindos da configuração, sem nada fixo no código (D-016). O que o bundle ainda não cobre (Lakebase, Genie, grants) está em scripts idempotentes. São 228 testes `pytest` e 11 `vitest`.

**"E lock-in?"**
- Os dados ficam em Delta no storage de vocês, o Lakebase é Postgres, o modelo de suspeita é LightGBM no MLflow e o modelo de linguagem é trocável pelo portão de avaliação. Tudo pode ser lido de fora.

**"Por que o parecer em lote não usa `ai_query`?"**
- Por vazão: o endpoint pequeno com scale-to-zero atendia poucas chamadas simultâneas, então o lote chama o modelo direto, com o mesmo código do endpoint. Com throughput provisionado, volta para `ai_query` (D-023, D-027).

## 5. Como trocar de altitude no meio da resposta

- **Do técnico para o negócio:** termine a resposta técnica com uma frase para a diretora. Exemplo: "Isso quer dizer que o pico não gera retrabalho: um caso, um regulador."
- **Do negócio para o técnico:** "A diretora perguntou do risco; arquiteto, a parte que te interessa é que o fast track é regra determinística, fora do modelo."
- **Pergunta técnica profunda demais para a sala:** dê a resposta em duas frases e proponha o detalhe numa sessão técnica: "Posso mostrar o código e o teste disso numa conversa à parte."
- **Não sei a resposta:** "Não medi isso no protótipo. É uma das perguntas que a PoC responde, e anoto aqui como critério."

## 6. Armadilhas a evitar

- **Tour de funcionalidades.** Cada tela da demo termina com o que ela significa para um KPI.
- **Prometer os números do sintético.** O 99,4% e os 55% são de dados simulados; o compromisso é medir na PoC.
- **Esconder limitações.** Dizer antes que perguntem: dados sintéticos, retreino como próximo passo, cobertura do parecer em lote de 95,2% na execução registrada, consultas do app sem OBO, risco de prompt injection mitigado por regra.
- **Arquitetura cedo demais.** A parte técnica começa no slide 13, depois do valor.
- **Terminar sem pedido.** Fechar sempre com a data da reunião de escopo.

# Regulação inteligente de sinistros em eventos climáticos

Exportação em texto do deck (`deck/index.html`): o conteúdo de cada slide e as speaker notes.
Gerado por `scripts/exportar_deck_md.py`. O PDF do deck está em `deck/deck-sinistros-clima.pdf`.

## Slide 1

Sinistros climáticos pagos em dias, com a IA sob controle
Diretoria de sinistros e arquitetura de TI
Novembro de 2026

**Speaker notes:**

Abertura (30 s). Obrigado pelo tempo de vocês. Estou com a diretora de sinistros, que responde pelo resultado do evento, e com o arquiteto, que vai ter que conviver com o que a gente construir. Enquadramento: vou falar de um momento específico da operação de vocês: os dias depois de uma enchente ou de um granizo, quando chegam milhares de avisos de uma vez. Em 15 minutos eu mostro o problema, uma demonstração funcionando com um evento simulado e o que propomos como próximo passo. Deixo o detalhe técnico para o fim, para o arquiteto, e a gente abre para perguntas a qualquer momento.

## Slide 2

Resumo executivo
Pagar rápido quem tem direito e segurar quem não tem, testado em 6.812 avisos de um evento
01
Metade dos avisos sai sem fila
54,9% foram liberados no fast track. Entre os 3.737 liberados, só 11 eram suspeitos (R$ 23 mil).
02
O regulador recebe o caso já analisado
A IA lê os PDFs, cruza com a apólice e com o clima real e sugere o parecer: 99,4% das recomendações certas.
03
Ganho de referência de R$ 2,4 milhões por evento
Pagamento indevido evitado e custo de regulação, a calibrar na PoC. O processamento custa cerca de US$ 0,007 por sinistro.
04
Recomendação: PoC de 6 semanas com um evento histórico de vocês
Medir o tempo até a indenização, o pagamento indevido evitado e a concordância dos reguladores com a IA.

**Speaker notes:**

Tell (1 min): a história inteira antes do detalhe. Se vocês guardarem um slide, é este. Primeiro: metade dos avisos de um evento pode sair sem fila, e no nosso teste só 11 de quase mil suspeitos passaram por esse caminho, somando R$ 23 mil. Segundo: o regulador deixa de ler PDF por PDF e recebe o caso já analisado, com o parecer da IA ao lado das evidências. Terceiro: numa seguradora do porte de vocês, a nossa referência é de R$ 2,4 milhões por evento, número que a gente quer calibrar com os dados de vocês, e não prometer. Quarto, o pedido: uma PoC de seis semanas com um evento que vocês já viveram. Para a diretora: "Quanto do avisado no último evento foi pago sem precisar? E em quantos dias o segurado simples recebeu?" (deixar ela responder; é o gancho da PoC).

## Slide 3

No pico de um evento, três problemas chegam juntos
Milhares de avisos em poucos dias, na mesma região
O segurado espera semanas
Cerca de 30 dias na nossa referência: fila por ordem de chegada e PDF lido um a um. Gera reclamação e perde a renovação.
Paga-se o que não devia
Na pressa passam orçamento inflado, dano anterior, causa sem cobertura e aviso fora do evento.
Custo e prazo estouram
Hora extra, regulador terceirizado e o prazo de 30 dias da SUSEP, sem saber quanto o evento já custou.

**Speaker notes:**

Tell: o problema (1 min 30). Depois de um granizo ou de uma enchente, a operação de regulação recebe em uma semana o que costuma receber em meses. Três coisas acontecem ao mesmo tempo. Um: o segurado, que acabou de perder o telhado ou o estoque, espera semanas (a nossa referência é de cerca de 30 dias), porque a fila é por ordem de chegada e cada caso depende de alguém ler os documentos. Dois: na pressa, passa o que não devia passar, como o orçamento inflado, o dano antigo declarado como novo ou a causa que a apólice não cobre. Três: o custo de regulação explode e o prazo da SUSEP aperta, e a diretoria não sabe em tempo real quanto o evento já custou para reservar e acionar o resseguro. Pergunta de descoberta: "Qual desses três doeu mais no último evento de vocês?" Use a resposta para dar peso ao KPI certo nos próximos slides.

## Slide 4

No pior dia do segurado, a seguradora paga em dias quem tem direito e segura quem não tem.
A proposta Com a IA lendo e recomendando, e o regulador decidindo

**Speaker notes:**

Pausa. Leia a frase e espere um segundo. Ponte: é isso que a gente propõe: as duas coisas ao mesmo tempo. Velocidade para quem tem direito e rigor para quem não tem, sem tirar a decisão das mãos do regulador. Tudo o que vou mostrar serve a essa frase.

## Slide 5

As metas, nos KPIs da diretoria de sinistros
Hoje e meta: referência nossa, a calibrar na PoC
KPI | Hoje | Meta | Medido no protótipo
Tempo até indenizar | ~30 dias | ~7 dias | não medido (o pagamento fica fora)
Casos no fast track | ~0% | ~30% | 54,9%
Pagamento indevido | base | −1 p.p. | 11 de 954 suspeitos passaram
Custo de regulação | base | −30% | não medido (3.737 sem regulador)
Acerto da IA | não medido | medido todo dia | 99,4% das recomendações
Medido: evento sintético sobre o clima real de SC, nos 9 lotes nunca vistos no treino.

**Speaker notes:**

Tell: como vamos medir o sucesso (1 min). Antes da demo, quero combinar a régua. São os KPIs que a diretoria de sinistros já acompanha. As colunas "hoje" e "meta" são premissas nossas, de uma seguradora média, e a PoC existe para trocar essas premissas pelos números de vocês. A última coluna é o que o protótipo mediu num evento simulado de 8 mil avisos, em lotes que o modelo nunca viu. Destaque: a meta de fast track é 30%, e o protótipo chegou a 55%; mesmo assim, no cálculo de valor eu uso os 30%, para não prometer o que ainda não medimos com dados reais. Se a diretora perguntar do prazo: o protótipo não paga, ele libera; o tempo até o crédito depende do fluxo de pagamento de vocês, e é isso que a PoC mede de ponta a ponta.

## Slide 6

Cada aviso é analisado assim que chega
A IA lê e recomenda, o código calcula, o regulador decide
1
O aviso chega
Aviso, fotos, orçamento e laudo em PDF entram assim que o segurado registra.
2
A IA lê e cruza
Documentos contra a apólice, o clima do INMET e da Defesa Civil e a tabela de preços.
3
Fast track ou fila
O caso simples sai sem fila. O resto entra por suspeita, valor e espera.
4
O regulador decide
Parecer e evidências lado a lado. Cada decisão mede a IA.
Regra de ouro
A IA não calcula valor e não libera nada fora do fast track.

**Speaker notes:**

Tell: o que muda (1 min). O processo que vocês conhecem continua, só que cada aviso chega ao regulador já trabalhado. Passo 1: o aviso e os documentos entram como entram hoje. Passo 2: a IA lê os PDFs e confronta o pedido com a apólice, com o clima que de fato aconteceu naquele município e naquele dia, com a tabela de preços e com o histórico do prestador. Passo 3: o caso simples, de valor baixo, com cobertura e evidência climática forte, sai sem fila; o resto entra numa fila ordenada por suspeita, valor e espera, e não mais por ordem de chegada. Passo 4: o regulador decide, com o parecer da IA ao lado das evidências, e cada decisão dele vira medida de qualidade da IA. Regra de ouro: a IA não calcula valor e não paga nada fora do fast track.

## Slide 7

Demonstração: um dia de evento, do painel à decisão
Granizo e vendaval em Santa Catarina, 8 mil avisos sintéticos
Painel do evento, fila do regulador, parecer da IA, decisão, supervisão da IA e as perguntas da diretoria no Genie.
https://sinistros-clima-dev-7474657549414280.aws.databricksapps.com
Abrir numa aba nova

**Speaker notes:**

Tell antes do show (20 s): "Vou mostrar um evento de granizo e vendaval em Santa Catarina, com 8 mil avisos sintéticos sobre o clima real do INMET e da Defesa Civil. Prestem atenção em dois momentos: quanto saiu sem fila e como o regulador decide com a IA do lado."
Show (9 min), na ordem:
1. Painel do evento: 7.612 avisos analisados, R$ 88,6 mi reclamados, 54% no fast track (R$ 8,9 mi liberados), 3.487 com o regulador, 1.142 suspeitos (R$ 23 mi reclamados) e R$ 4,8 mi de ajuste por evidência sugerido pela IA. Frase: "Metade dos casos simples já saiu sem fila; o regulador cuida do resto."
2. Fila do regulador: ordem por prioridade e o motivo de cada caso estar fora do fast track; clicar em Assumir próximo. Frase: "Assumir trava o caso: no teste com dois reguladores ao mesmo tempo, nenhum caso saiu repetido."
3. Detalhe: parecer com motivos e cláusulas ao lado da apólice, do clima da estação do INMET, do preço contra a tabela e do prestador; CPF mascarado. Frase: "O valor sai de cálculo, não do modelo de linguagem."
4. Reanalisar com IA: nova análise em segundos, auditada.
5. Decidir: registrar uma decisão divergindo da IA. Frase: "A decisão é do regulador; a divergência vira aprendizado."
6. IA sob supervisão: concordância e a matriz IA contra regulador. Frase: "É assim que a diretoria confia: medindo a IA todo dia."
7. Genie da diretoria (link no cabeçalho): "Quais municípios concentram mais sinistros suspeitos?" e "Quanto a IA sugeriu ajustar por evidência?". Frase: "O mesmo número do painel, em português, sem pedir relatório para a TI."
Plano B: se o login ou a rede falhar, siga para os resultados medidos (próximo slide) e conte o caminho de um sinistro, do arquivo à decisão, pelo evidencias/08-rastreio-ponta-a-ponta.md.
Tell depois do show (30 s): "O que vocês viram: o caso simples pago sem fila, o regulador só onde há valor ou suspeita, e a IA medida contra ele. Agora os números."

## Slide 8

Metade saiu sem fila e quase nenhum suspeito passou
6.812 avisos em lotes que o modelo nunca viu
54,9%
dos avisos liberados no fast track
meta de referência: 30%
11
suspeitos passaram, de 954
1,2% dos suspeitos, R$ 23 mil
99,4%
das recomendações da IA certas
99,6% dos valores a ±10%
15 × 33
suspeitos liberados: modelo × regra
AUC de 0,997 contra 0,962
16 de 16
perguntas certas no Genie
mesmas métricas do painel
US$ 0,007
por sinistro processado
~US$ 52 por evento

**Speaker notes:**

Tell: o que os números dizem (1 min 30). Estes números vêm de um teste honesto: o modelo foi treinado num histórico de 2025 e avaliado em nove lotes do evento que ele nunca tinha visto. Para a diretora, três números: metade dos avisos saiu sem fila; dos 954 suspeitos, só 11 passaram pelo fast track, somando R$ 23 mil; e a IA acertou 99,4% das recomendações. Para o arquiteto: o modelo de suspeita bate a regra fixa que muita seguradora usa hoje, com AUC de 0,997 contra 0,962, e entre os casos elegíveis ao fast track deixa passar 15 suspeitos, contra 33 da regra. O Genie acertou as 16 perguntas de referência da diretoria. Ressalva que eu faço antes que perguntem: os dados são sintéticos, com padrões de fraude que nós mesmos plantamos. Por isso a acurácia é alta; com dados reais ela vai cair, e é exatamente isso que a PoC mede.

## Slide 9

R$ 2,4 mi
de ganho de referência por evento de 8 mil avisos
Cerca de R$ 7,8 mi por ano com 3 eventos. Premissas nossas, a calibrar na PoC com os dados da seguradora.

**Speaker notes:**

Tell: o valor (30 s). Deixe o número na tela um instante. Numa seguradora média, com 8 mil avisos por evento e ticket médio de R$ 12 mil, a nossa referência é de R$ 2,4 milhões por evento, e cerca de R$ 7,8 milhões por ano com três eventos relevantes. Eu chamo de referência de propósito: é uma conta com premissas nossas, e o primeiro entregável da PoC é refazer essa conta com os números de vocês. Se a diretora perguntar quando se paga: o custo de processamento de um evento inteiro é de dezenas de dólares; o investimento real é o projeto e a mudança de processo, que a PoC dimensiona.

## Slide 10

O ganho vem de pagar certo e de regular menos casos simples
Referência: 8 mil avisos, ticket de R$ 12 mil, 30% no fast track
R$ 1,0 mi
por evento em pagamento indevido evitado: 1 p.p. dos R$ 96 mi avisados
R$ 1,4 mi
por evento em custo de regulação: 2.400 casos no fast track a ~R$ 600
R$ 0,6 mi
por ano em prêmio preservado: +5 p.p. de renovação dos segurados afetados
Todos os valores são premissas nossas, nenhum informado por cliente. Fonte: docs/negocio/02-ganhos-kpis-e-personas.md.

**Speaker notes:**

Como a conta fecha (1 min). Três fontes. Primeira, a maior em risco: pagamento indevido. Se o cruzamento com a apólice e com o clima evitar um ponto percentual do valor avisado, são cerca de R$ 1 milhão por evento. No protótipo, a IA sugeriu R$ 4,8 milhões de ajuste por evidência, mas eu não uso esse número: o dado é sintético e a fraude foi plantada por nós. Segunda: custo de regulação. Com 30% dos casos no fast track, e não os 55% que medimos, são 2.400 sinistros que não passam por um regulador, a cerca de R$ 600 cada. Terceira, anual: segurado pago rápido renova mais. Cinco pontos de retenção dão cerca de R$ 600 mil por ano. Ponto para a diretora: eu escolhi premissas moderadas; a PoC troca cada uma por um número de vocês.

## Slide 11

Processar um sinistro custa menos de um centavo de dólar
Faturamento do workspace a preço de lista: referência, a calibrar na PoC
0,007
US$ por sinistro: leitura dos PDFs, pipeline e parecer em lote
~52
US$ por evento de 8 mil avisos, ou ~US$ 160 por ano com 3 eventos
0,02
US$ por reanálise no app, estimado pelos tokens
Fora do evento, o Lakebase e o endpoint escalam a zero. O SQL Warehouse do painel e do Genie conta enquanto estiver ligado.

**Speaker notes:**

Custo (1 min), para os dois. Medimos o custo real no faturamento do workspace, a preço de lista: cerca de US$ 0,0047 por aviso no pipeline, já com a leitura dos PDFs (US$ 0,0034 por PDF), e US$ 0,002 por parecer em lote. Somando, cerca de US$ 0,007 por sinistro, ou uns US$ 52 para um evento inteiro de 8 mil avisos. A reanálise que o regulador pede no app usa um modelo maior; pela contagem de tokens, estimamos cerca de US$ 0,02 por clique, ainda a confirmar no faturamento. O custo fixo é o SQL Warehouse do painel e do Genie enquanto estiver ligado; o banco e o endpoint desligam sozinhos fora do evento. Isso é referência: o volume de PDFs por aviso e o tamanho dos documentos de vocês mudam a conta, e a PoC mede com os dados reais. Num cenário de mais páginas por documento, o custo por sinistro pode chegar a alguns centavos, ainda pequeno diante de R$ 600 de regulação por caso. Mensagem para a diretora: o custo da plataforma não é o que decide este projeto; o que decide é o processo e o valor que ele protege.

## Slide 12

A IA trabalha sob o controle do regulador
Cada papel tem um dono, e cada uso da IA é avaliado e auditado
A IA lê, cruza e recomenda
Pagar, pagar parcial, recusar ou investigar, com motivos e cláusulas citadas, ao lado das evidências.
O código calcula o valor
Franquia, limite e tabela de preços entram em regra testada. O modelo de linguagem não define quanto pagar.
O regulador decide e mede a IA
Fora do fast track, toda decisão é humana. A concordância com a IA aparece todo dia na tela de supervisão.

**Speaker notes:**

Responde à objeção antes dela (1 min): "e se a IA errar?" A gente separou os papéis. A IA lê os documentos, cruza e recomenda, sempre mostrando o porquê. O valor nunca sai do modelo de linguagem: sai de um cálculo com franquia, limite e tabela de preços, coberto por testes. E o regulador decide tudo o que não é fast track. O fast track só libera quando tudo bate: valor até R$ 5 mil, cobertura válida, evidência climática forte, score de suspeita baixo, parecer de pagamento integral e nenhum alerta bloqueante (documento ilegível ou ausente, orçamento divergente, preço acima da tabela, dano anterior no laudo, apólice fora de vigência). Qualquer dado faltante manda o caso para o regulador. Para o arquiteto: o prompt é versionado e só vai para produção se passar no portão de avaliação do MLflow (66% para 95% de acerto entre a versão 1 e a 2), e cada parecer grava o modelo, o prompt e a versão usados; a reanálise do app passa pelo AI Gateway, com trace.

## Slide 13

Por dentro da solução
Do arquivo que chega à decisão do regulador, numa plataforma só
Integração, governança, escala e custo

**Speaker notes:**

Troca de altitude. "Agora quero falar com o arquiteto, que vai ter que operar isso. São dois slides; diretora, o ponto para você é que tudo isso roda numa plataforma só, com um catálogo só, o que reduz o risco e o custo de integração."

## Slide 14

Cada camada entrega à próxima, sob o mesmo catálogo
Tudo serverless; pipeline, jobs e app por bundle, o resto por scripts
1. Lakeflow
Auto Loader e AI Functions leem avisos e PDFs
2. ML e GenAI
Score de suspeita e parecer avaliado
3. Gold
Fast track, prioridade e métricas
4. Lakebase
Fila e decisões com transação
5. App e Genie
Regulador e diretoria
6. As decisões voltam ao lakehouse pelo Lakehouse Sync e medem a IA
Concordância e divergências viram rótulo para o retreino
Unity Catalog: permissões, tags de LGPD, lineage, metric views, modelos e prompts

**Speaker notes:**

Para o arquiteto (1 min 30), da esquerda para a direita. 1. O Lakeflow, com Auto Loader, ingere avisos, PDFs, apólices e os dados públicos de clima; o ai_parse_document e o ai_extract leem os PDFs dentro do próprio pipeline, sem um serviço de OCR à parte. Os 8 mil avisos e 9.705 PDFs do evento chegaram à silver, já lidos e cruzados, em cerca de 26 minutos; o parecer em lote vem depois, no ritmo do modelo de linguagem. 2. O modelo de suspeita (LightGBM, registrado no Unity Catalog com o alias champion) e o parecer do modelo de linguagem, com prompt versionado e avaliado. 3. A gold junta tudo e aplica as regras de fast track e prioridade, com MERGE idempotente. 4. Uma synced table leva a gold ao Lakebase, o Postgres gerenciado, porque fila e decisão precisam de transação e lock, o que um warehouse não dá. 5. O app (AppKit) e o Genie leem as mesmas metric views, então o número do painel é o número do Genie. 6. As decisões voltam ao lakehouse pelo Lakehouse Sync, como histórico, e medem a IA. Tudo isso sob o Unity Catalog. Prova: o rastreio de um sinistro, do arquivo à decisão, está em texto no repositório.

## Slide 15

Como integra, protege o dado e aguenta o pico
As três perguntas da arquitetura
Integração
No protótipo, arquivos num Volume. Em produção, CDC do sistema de sinistros e volta pela tabela de decisões ou pelo Postgres.
Segurança e LGPD
Dado pessoal com tag e CPF mascarado. App e Genie nunca veem o CPF aberto, com auditoria e lineage.
Escala no pico
Serverless e incremental: a chegada do arquivo dispara o job. O gargalo medido é o modelo de linguagem, e a saída é capacidade reservada.

**Speaker notes:**

Integração (proposta): o protótipo recebe arquivos num Volume; em produção, o Lakeflow Connect lê do sistema de sinistros por CDC. A volta é pela tabela de decisões no Unity Catalog ou direto no Postgres do Lakebase, por API. Segurança e LGPD: as colunas pessoais têm tag; o CPF é mascarado numa visão da gold, e só um grupo autorizado vê o número completo; o app roda com um service principal de permissão mínima (leitura da gold e da entrada do parecer, escrita só no schema operacao do Lakebase), e isso foi provado no deploy, quando o build falhou antes da permissão e passou depois. Escala: tudo serverless; a chegada do lote dispara o job. O que medimos como limite foi a vazão do modelo de linguagem pago por token, cerca de 21 pareceres por minuto; em produção, isso se resolve com throughput provisionado, dimensionado na PoC. Um parecer inválido nunca libera o fast track: o caso vai para o regulador. E, se o parecer em lote passar do tempo, o próprio job agenda a continuação e retoma os pendentes.

## Slide 16

PoC em 6 semanas, com um evento que vocês já viveram
Critério de sucesso combinado antes de começar
Semana 1
Dados
Um evento histórico: avisos, PDFs, apólices e as decisões já tomadas.
Semanas 2 e 3
Pipeline e modelo
Ingestão, cruzamentos e o modelo treinado com o histórico de vocês.
Semanas 4 e 5
Piloto
Reguladores usam a fila e o parecer em paralelo ao processo atual.
Semana 6
Decisão
Tempo até a indenização, pagamento indevido, concordância e custo medidos.

**Speaker notes:**

Tell: o próximo passo (1 min). A proposta é provar com dados de vocês, sem mexer na operação. Semana 1: escolhemos juntos um evento recente e reunimos os avisos, os PDFs, as apólices e, o mais importante, as decisões que os reguladores já tomaram, que viram o gabarito. Semanas 2 e 3: a mesma arquitetura que vocês viram, agora com o histórico real, em ambiente de vocês e governado. Semanas 4 e 5: um grupo pequeno de reguladores usa a fila e o parecer em paralelo, sem pagar nada pelo sistema novo. Semana 6: a gente mede os quatro KPIs contra a linha de base e vocês decidem. Risco baixo: nada é pago pelo protótipo, e a meta de sucesso é combinada no começo.

## Slide 17

Três decisões para começar na próxima semana
Próximos passos
1
Escolher o evento
A diretoria indica um evento recente e o volume de avisos dele.
2
Nomear o time
Um gerente de regulação, um arquiteto de TI e o acesso de leitura aos dados.
3
Combinar as metas
O fast track, o pagamento indevido e o prazo que fazem a PoC valer a pena.
Proposta: reunião de escopo da PoC nesta semana.
Da nossa parte: arquitetura de soluções e o time de especialistas em GenAI da Databricks.

**Speaker notes:**

O pedido (30 s). Para sair daqui com um próximo passo concreto: preciso de três decisões. Diretora: qual evento a gente usa? Arquiteto: quem do seu time acompanha e como liberamos acesso de leitura aos dados? E juntos: qual número faria vocês dizerem que valeu a pena? Feche perguntando: "Podemos marcar a reunião de escopo ainda esta semana?" Depois, silêncio e espere a resposta.

## Slide 18

Obrigado
Apresentação Arquitetura de soluções, Databricks
Repositório github.com/gilsonreisf/fe-bar-sinistros-clima
Próximo passo Reunião de escopo da PoC

**Speaker notes:**

Deixe este slide na tela enquanto responde às perguntas. As respostas preparadas estão no apêndice (slides 20 e 21) e no arquivo deck/faq-roleplay.md.

## Slide 19

Apêndice
Perguntas, decisões e de onde vêm os números

**Speaker notes:**

Slides de apoio para as perguntas. Não apresentar em sequência: pular direto para o slide da pergunta.

## Slide 20

As perguntas da diretoria de sinistros
E se a IA errar e pagarmos fraude?
Fora do fast track a IA não paga nada. No teste, 11 suspeitos (R$ 23 mil) passaram, contra 3.737 casos liberados sem regulador.
O regulador vai confiar?
Ele vê motivos, cláusulas e evidências, decide e pode divergir. A concordância é medida todo dia.
Os dados são sintéticos. Vale para nós?
O clima é real e a fraude foi plantada. Por isso a PoC usa um evento de vocês e as decisões já tomadas.
Quanto custa e quando se paga?
Cerca de US$ 0,007 por sinistro processado. O ganho de referência é R$ 2,4 mi por evento, a calibrar.

**Speaker notes:**

Fraude: o fast track exige todas as condições ao mesmo tempo (valor até R$ 5 mil, cobertura válida, evidência climática forte, score de suspeita baixo, parecer de pagamento integral e nenhum alerta bloqueante (documento ilegível ou ausente, orçamento divergente, preço acima da tabela, dano anterior no laudo, apólice fora de vigência)), e qualquer dado faltante bloqueia. O risco residual é pequeno e conhecido: R$ 23 mil em suspeitos, contra R$ 8 milhões liberados sem regulador, e pode ser auditado depois por amostragem. Confiança: o regulador é quem decide; a tela de supervisão mostra onde a IA e ele divergem, e essas divergências viram rótulo para o retreino. Dados sintéticos: o clima é do INMET e da Defesa Civil, os municípios são do IBGE; os avisos e a fraude são simulados, e por isso o acerto é alto. A PoC mede com o histórico de vocês. Custo e retorno: o custo da plataforma por evento é de dezenas de dólares; o retorno vem do processo e é a primeira coisa que a PoC recalcula.

## Slide 21

As perguntas da arquitetura de TI
E a LGPD?
Tag nas colunas pessoais e CPF mascarado na gold. App e Genie não veem o CPF aberto. Auditoria e lineage no catálogo.
E a qualidade do dado?
Expectations no pipeline. PDF ilegível, cobertura ausente ou parecer inválido bloqueiam o fast track.
E se o modelo de linguagem mudar?
Prompt e modelo passam pelo mesmo portão de avaliação. Trocamos o modelo do lote com evidência medida.
Dois reguladores no mesmo caso?
Assumir trava o caso no Lakebase: no teste simultâneo, nenhum repetido. O clique duplo grava uma decisão só.

**Speaker notes:**

LGPD: as colunas com dado pessoal têm tag no Unity Catalog; o CPF aparece mascarado numa visão dinâmica da gold, o Genie lê a gold, e o app tem permissão mínima (leitura da gold e da entrada do parecer, escrita só no schema operacao do Lakebase). A máscara ficou na visão, e não na tabela do pipeline, para não quebrar os cruzamentos. Qualidade: o pipeline tem expectations; um documento ilegível ou uma extração com falha vira flag e manda o caso ao regulador. Troca de modelo: comparamos Haiku e Sonnet no mesmo dataset; para o lote ficou o Haiku 5.5, que empatou na recomendação (95,1%) a cerca de US$ 0,002 por parecer; no app ficou o Sonnet, melhor no texto que o regulador lê. Concorrência: no teste, 6 pedidos simultâneos de dois reguladores entregaram 6 casos distintos, e o mesmo id de decisão não grava duas vezes. Se perguntarem de integração ou pico, volte ao slide 15.

## Slide 22

As decisões de arquitetura e o que ficou de fora
Registro completo em docs/decisoes-e-tradeoffs.md
Decisão | Escolha | Descartado | Por quê
Fila e decisões | Lakebase | Tabela no warehouse | Transação e lock em milissegundos
Valor do parecer | Calculado em código | Valor do modelo | Regra testada e auditável
Modelo do lote | Haiku 5.5 | Sonnet 5.5 | Mesmo acerto, custo menor
Métricas | Metric views | SQL em cada tela | Painel e Genie com o mesmo número
Máscara do CPF | Visão dinâmica na gold | Máscara na tabela | Não quebra os cruzamentos

**Speaker notes:**

Use quando o arquiteto perguntar "por que assim?". Fila e decisões: o warehouse é ótimo para análise, mas a fila precisa de transação, chave e lock; por isso o Lakebase. Valor: o modelo de linguagem recomenda, e o valor sai de uma regra testada (D-022). Modelo do lote: Haiku e Sonnet empataram em 95,1% de recomendações certas; o Sonnet ficou no app, onde o texto é lido (D-023). Métricas: definidas uma vez em metric views e usadas pelo app e pelo Genie (D-010, D-025). CPF: a máscara na visão de consumo, e não na tabela do pipeline, para os cruzamentos seguirem funcionando (D-025). Desvios conhecidos: parecer em lote chamando o modelo direto, e não pelo ai_query, por vazão; consultas do app pelo service principal, sem identidade do usuário (D-027).

## Slide 23

De onde vêm os números deste deck
1
Teste final nos lotes nunca vistos: evidencias/04c-teste-final.md
2
Custo medido no faturamento: evidencias/09-custo-real.md
3
Genie e rastreio: evidencias/06-genie.md e 08-rastreio-ponta-a-ponta.md
4
Ganhos de referência: docs/negocio/02-ganhos-kpis-e-personas.md
Dados sintéticos sobre fontes públicas (INMET, Defesa Civil de SC e IBGE).

**Speaker notes:**

Todos os números medidos vêm de evidências em texto, versionadas no repositório e geradas por script. Os ganhos em reais são premissas nossas, a calibrar na PoC.

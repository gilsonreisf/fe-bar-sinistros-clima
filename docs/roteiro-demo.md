# Roteiro da demo (tell → show → tell, ~15 min)

**Público:** diretor(a) de sinistros (negócio) e arquiteto(a) de TI (técnica).
**Mensagem única:** no pior dia do segurado, a seguradora paga em dias quem tem direito e segura quem não tem, com a IA sob controle do regulador.

> Números da demo: evento sintético de 8 mil avisos sobre clima real de SC (INMET e Defesa Civil). Ganhos em reais são **referência, a calibrar na PoC** (`docs/negocio/02-ganhos-kpis-e-personas.md`).

## 1. Tell: o problema (2 min)

- Depois de uma enchente ou de um granizo, chegam milhares de avisos em poucos dias. A fila é por ordem de chegada, o regulador lê PDF por PDF, e o segurado espera cerca de 30 dias.
- No pico passam pagamentos indevidos (dano anterior, orçamento inflado, causa sem cobertura) e o prazo da SUSEP aperta.
- **Pergunta para o diretor:** "Quanto do avisado no último evento foi pago sem precisar? E em quantos dias o segurado simples recebeu?"

## 2. Show: o evento acontecendo (9 min)

| # | Tela | O que mostrar | Frase |
|---|---|---|---|
| 1 | **Painel do evento** (app) | Avisos recebidos, exposição, **~55% no fast track**, fila, suspeitos e ajuste sugerido pela IA | "Metade dos casos simples já saiu sem fila; o regulador cuida do resto." |
| 2 | **Fila do regulador** | Ordem por prioridade (suspeita, valor e espera) e o motivo de cada caso estar fora do fast track; clicar em **Assumir próximo** | "Dois reguladores nunca pegam o mesmo caso; isso é transação no Lakebase." |
| 3 | **Detalhe** | Parecer da IA com motivos e cláusulas, ao lado das evidências: cobertura, clima da estação INMET, preço contra a tabela, prestador. CPF mascarado | "A IA lê os PDFs e cruza com a apólice e com o clima; o valor sai de cálculo, não do LLM." |
| 4 | **Reanalisar com IA** | Nova análise em ~5 s, com trace | "Cada chamada fica auditada no AI Gateway e no MLflow." |
| 5 | **Decidir** | Registrar a decisão, divergindo da IA num caso | "A decisão é do regulador; a divergência vira aprendizado." |
| 6 | **IA sob supervisão** | Concordância IA × regulador e a matriz de divergências | "É assim que o diretor confia: medindo a IA todo dia." |
| 7 | **Genie da diretoria** (link no cabeçalho) | Perguntar: "Quais municípios concentram mais sinistros suspeitos?" e "Quanto de pagamento indevido a IA sugeriu evitar?" | "O mesmo número do painel, em português, sem pedir relatório para a TI." |
| 8 | **Bastidores** (para o arquiteto) | Lineage no UC do JSON até a decisão; pipeline; modelo `champion`; avaliação v1 × v2 do prompt | "Uma plataforma, um catálogo, um lineage." |

**Caso para mostrar no detalhe:** um suspeito de alta prioridade da fila (ex.: causa sem cobertura ou orçamento inflado) e um legítimo complexo. O rastreio completo de um caso está em `evidencias/08-rastreio-ponta-a-ponta.md`.

## 3. Tell: o valor e o próximo passo (3 min)

- **Resultado nos lotes nunca vistos** (`evidencias/04c-teste-final.md`):
  - o modelo bate a regra (AUC 0,99 contra 0,95) e deixa passar menos suspeitos no fast track;
  - o parecer acerta ~98% das recomendações e ~99,7% dos valores (±10%).
- **Custo medido:** cerca de US$ 0,006 por sinistro processado (pipeline + parecer), referência a calibrar na PoC (`evidencias/09-custo-real.md`).
- **Proposta de PoC (4 a 6 semanas):** um evento histórico do cliente, com o sistema de sinistros e os PDFs reais, medindo o tempo até a indenização, o *leakage* evitado e a concordância com os reguladores.

## Objeções preparadas

| Persona | Objeção | Resposta |
|---|---|---|
| Diretor(a) | "E se a IA errar e pagarmos fraude?" | A IA não paga fora do fast track. O fast track exige valor baixo, cobertura válida, evidência climática forte, score baixo e parecer integral; qualquer dado faltante bloqueia. Nos lotes de teste, ficaram 9 suspeitos de R$ 19 mil no fast track, contra o custo de regular 1.347 casos à mão. |
| Diretor(a) | "O regulador vai confiar?" | Ele vê os motivos, as cláusulas e as evidências; decide e diverge quando quer; a concordância é medida na tela de supervisão. |
| Diretor(a) | "Quanto custa?" | Cerca de US$ 0,006 por sinistro no processamento medido, com o endpoint e o banco escalando a zero fora do evento. A PoC mede com o volume real. |
| Arquiteto(a) | "LGPD?" | Colunas pessoais marcadas com tag; CPF mascarado na camada de consumo; o app e o Genie leem só o gold; auditoria e lineage no UC. |
| Arquiteto(a) | "Integra com o nosso sistema de sinistros?" | Entrada por arquivo ou CDC (Lakeflow Connect) e saída pela tabela de decisões no UC ou pelo Postgres do Lakebase, por API. |
| Arquiteto(a) | "Aguenta o pico?" | Pipeline e app são serverless. O gargalo medido é a vazão do LLM pay-per-token (~21 por minuto); em produção, throughput provisionado. |
| Arquiteto(a) | "E se o modelo de LLM mudar?" | O prompt e o modelo passam pelo mesmo portão de avaliação; trocamos o Sonnet pelo Haiku no lote com evidência (D-023). |

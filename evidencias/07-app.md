# App da regulação: publicação e testes

Registrado em 2026-11-21 (D-026). Código em `app/`; o bundle do app é `app/databricks.yml`.

## Publicação

- O app `sinistros-clima-dev` foi publicado com `databricks bundle deploy -t dev` + `databricks bundle run -t dev app`. Estado: **RUNNING** ("App has status: App is running").
- Recursos declarados no bundle: SQL Warehouse (`CAN_USE`), Lakebase `projects/sinistros-clima/branches/production` (`CAN_CONNECT_AND_CREATE`) e o endpoint `sinistros-clima-parecer-dev` (`CAN_QUERY`).
- **Build remoto com a identidade do app:** o AppKit descreve as 8 consultas no warehouse durante o build. No 1º deploy, as 8 falharam com `INSUFFICIENT_PERMISSIONS` (sem USE CATALOG). Depois de `scripts/permissoes_app.py`, as 8 passaram. É a prova de que o app só lê o que recebeu.
- **Fato medido:** recriar uma visão ou metric view com `CREATE OR REPLACE` apaga os grants dados objeto a objeto, e o job recria as visões do gold a cada execução. Por isso o app recebe SELECT no schema `gold` (a camada de consumo, com o CPF mascarado), e não visão a visão. Ele não lê nenhuma tabela da silver com dado pessoal: a junção da metric view roda com os direitos do dono, e o build passou sem esse acesso.
- **Verificação na partida do servidor** (log do app, identidade do app no Postgres):
  `[verificacao] Lakebase ok: {"fila":"3417","decisoes":"19"}`
  O service principal lê a synced table do gold e o schema `operacao`.

## Testes de interface (as 4 telas)

Rodados com `npm run dev`, contra os mesmos recursos (warehouse, Lakebase e endpoint), porque o app publicado exige login com MFA.

| Tela | Teste | Resultado |
|---|---|---|
| Painel do evento | KPIs da metric view `sinistros_metrics`, gráfico por lote, recomendações e municípios | 4.017 avisos analisados no momento, R$ 46,7 mi de exposição, 54,3% no fast track, 568 suspeitos, R$ 7,3 mi de ajuste sugerido pela IA |
| Fila do regulador | Lista do Lakebase por prioridade, com os motivos de bloqueio do fast track | 50 casos listados; topo com score de 0,999 e motivos "valor acima do teto", "sem cobertura" e "score suspeita" |
| Assumir próximo | Clique no botão | Abriu o detalhe do caso de maior prioridade; atribuição gravada como `em_analise` |
| Decisão só de quem assumiu (D-028) | Caso aberto pela fila, sem atribuição, e chamadas diretas à API | O detalhe mostra "Assumir este caso" no lugar do formulário. Pela API: decisão sem atribuição → 409 "Assuma o caso antes de decidir"; depois de assumir, recusa com valor → 409 "Uma recusa não tem valor aprovado"; decisão válida → gravada; o mesmo `id_decisao` de novo → "Decisão já registrada"; uma segunda decisão para o sinistro → 409 "Este sinistro já foi decidido" |
| Detalhe | Parecer, evidências e CPF | Parecer "Recusar" (CG-2.1, causa sem cobertura) ao lado das evidências; CPF exibido como `***.798.***-**` |
| Reanalisar com IA | Clique no botão | Nova análise pelo endpoint (Sonnet) em poucos segundos, com trace `tr-…` e gravada em `operacao.reanalises` |
| Decisão | Duplo clique em "Registrar decisão" | **Uma** decisão gravada ("concordou com a IA"); atribuição passou a `decidido`, na mesma instrução |
| IA sob supervisão | KPIs e tabelas da metric view `regulacao_metrics` | 13 decisões, 61,5% de concordância, matriz IA × regulador e as versões em produção (Haiku 5.5, prompt v2, modelo v3). As decisões são quase todas de reguladores fictícios do teste automatizado (dimensão "Origem da decisão") |

Os números do painel acima são do teste de interface, quando o gold ainda tinha 4.017 sinistros. Depois da revisão (D-028), as medidas viraram "Encaminhados ao regulador" e "Ajuste por evidência sugerido pela IA", e o app foi publicado de novo.

Durante os testes foram achados e corrigidos três defeitos:
- a DataTable descartava colunas com acento, e as tabelas foram trocadas por um componente próprio;
- o booleano vinha como texto e o badge mostrava "fast track" num caso da fila;
- o título do gráfico prometia "mais da metade" e o lote 1 ficou abaixo disso.

## Testes automatizados

- `npx vitest run`: 11 testes, todos passando.
  - **Contrato das rotas:** a decisão é validada (lista de decisões, valor ≥ 0, motivo e UUID), o `id_aviso` tem formato fixo (nada de SQL na URL) e a resposta do endpoint é validada.
  - **SQL do Lakebase:** é parametrizado; "assumir" trava só o candidato tentado; só quem está com o caso decide, numa instrução só; o motivo de uma decisão não gravada é explicado ao regulador.
  - **Formatação pt-BR:** inclui o booleano em texto.
- `tsc` (servidor e cliente) e `eslint`: sem erros. `appkit lint`: sem violações.
- `uv run pytest`: 228 testes do projeto, incluindo as permissões mínimas do app (`testes/test_permissoes_app.py`).

## Concorrência e idempotência no Lakebase

Estão em `evidencias/03-lakebase.md`: dois reguladores assumindo ao mesmo tempo, sem repetição, e o clique duplo sem duplicata. As decisões voltam ao UC pelo Lakehouse Sync.

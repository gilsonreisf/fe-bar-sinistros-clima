/* ============================================================================
 * DECISÕES E TRADE-OFFS  —  as escolhas de arquitetura e o que foi descartado.
 * Usage: off-tables (table.db).
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>As decisões de arquitetura e o que ficou de fora</h2>
      <p class="slide-sub">Registro completo em docs/decisoes-e-tradeoffs.md</p>
      <table class="db">
        <thead>
          <tr><th>Decisão</th><th>Escolha</th><th>Descartado</th><th>Por quê</th></tr>
        </thead>
        <tbody>
          <tr><td>Fila e decisões</td><td>Lakebase</td><td>Tabela no warehouse</td><td>Transação e lock em milissegundos</td></tr>
          <tr><td>Valor do parecer</td><td>Calculado em código</td><td>Valor do modelo</td><td>Regra testada e auditável</td></tr>
          <tr><td>Modelo do lote</td><td>Haiku 5.5</td><td>Sonnet 5.5</td><td>Mesmo acerto, custo menor</td></tr>
          <tr><td>Métricas</td><td>Metric views</td><td>SQL em cada tela</td><td>Painel e Genie com o mesmo número</td></tr>
          <tr><td>Máscara do CPF</td><td>Visão dinâmica na gold</td><td>Máscara na tabela</td><td>Não quebra os cruzamentos</td></tr>
        </tbody>
      </table>
    </div>
  </div>
  <div class="notes">Use quando o arquiteto perguntar "por que assim?". Fila e decisões: o warehouse é ótimo para análise, mas a fila precisa de transação, chave e lock; por isso o Lakebase. Valor: o modelo de linguagem recomenda, e o valor sai de uma regra testada (D-022). Modelo do lote: Haiku e Sonnet empataram em 95,1% de recomendações certas; o Sonnet ficou no app, onde o texto é lido (D-023). Métricas: definidas uma vez em metric views e usadas pelo app e pelo Genie (D-010, D-025). CPF: a máscara na visão de consumo, e não na tabela do pipeline, para os cruzamentos seguirem funcionando (D-025). <b>Desvios conhecidos:</b> parecer em lote chamando o modelo direto, e não pelo ai_query, por vazão; consultas do app pelo service principal, sem identidade do usuário (D-027).</div>
</div>
`);

/* ============================================================================
 * KPIS  —  hoje, meta e o que o protótipo mediu, nos KPIs da diretoria.
 * Usage: off-tables (table.db) + nota de legenda.
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>As metas, nos KPIs da diretoria de sinistros</h2>
      <p class="slide-sub">Hoje e meta: referência nossa, a calibrar na PoC</p>
      <table class="db">
        <thead>
          <tr><th>KPI</th><th>Hoje</th><th>Meta</th><th>Medido no protótipo</th></tr>
        </thead>
        <tbody>
          <tr><td>Tempo até indenizar</td><td>~30 dias</td><td>~7 dias</td><td>não medido (o pagamento fica fora)</td></tr>
          <tr><td>Casos no fast track</td><td>~0%</td><td>~30%</td><td>54,9%</td></tr>
          <tr><td>Pagamento indevido</td><td>base</td><td>−1 p.p.</td><td>11 de 954 suspeitos passaram</td></tr>
          <tr><td>Custo de regulação</td><td>base</td><td>−30%</td><td>não medido (3.737 sem regulador)</td></tr>
          <tr><td>Acerto da IA</td><td>não medido</td><td>medido todo dia</td><td>99,4% das recomendações</td></tr>
        </tbody>
      </table>
      <p class="cap-note">Medido: evento sintético sobre o clima real de SC, nos 9 lotes nunca vistos no treino.</p>
    </div>
  </div>
  <div class="notes"><b>Tell: como vamos medir o sucesso (1 min).</b> Antes da demo, quero combinar a régua. São os KPIs que a diretoria de sinistros já acompanha. As colunas "hoje" e "meta" são premissas nossas, de uma seguradora média, e a PoC existe para trocar essas premissas pelos números de vocês. A última coluna é o que o protótipo mediu num evento simulado de 8 mil avisos, em lotes que o modelo nunca viu. Destaque: a meta de fast track é 30%, e o protótipo chegou a 55%; mesmo assim, no cálculo de valor eu uso os 30%, para não prometer o que ainda não medimos com dados reais. <b>Se a diretora perguntar do prazo:</b> o protótipo não paga, ele libera; o tempo até o crédito depende do fluxo de pagamento de vocês, e é isso que a PoC mede de ponta a ponta.</div>
</div>
`);

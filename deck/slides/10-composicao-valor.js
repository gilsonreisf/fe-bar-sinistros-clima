/* ============================================================================
 * COMPOSIÇÃO DO VALOR  —  as três fontes do ganho de referência.
 * Usage: 39-roi; números estáticos (vírgula decimal).
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>O ganho vem de pagar certo e de regular menos casos simples</h2>
      <p class="slide-sub">Referência: 8 mil avisos, ticket de R$ 12 mil, 30% no fast track</p>
      <div class="roi-row">
        <div class="roi-item">
          <div class="big">R$ 1,0 mi</div>
          <div class="label">por evento em pagamento indevido evitado: 1 p.p. dos R$ 96 mi avisados</div>
        </div>
        <div class="roi-item">
          <div class="big">R$ 1,4 mi</div>
          <div class="label">por evento em custo de regulação: 2.400 casos no fast track a ~R$ 600</div>
        </div>
        <div class="roi-item">
          <div class="big">R$ 0,6 mi</div>
          <div class="label">por ano em prêmio preservado: +5 p.p. de renovação dos segurados afetados</div>
        </div>
      </div>
      <p class="cap-note">Todos os valores são premissas nossas, nenhum informado por cliente. Fonte: docs/negocio/02-ganhos-kpis-e-personas.md.</p>
    </div>
  </div>
  <div class="notes"><b>Como a conta fecha (1 min).</b> Três fontes. Primeira, a maior em risco: pagamento indevido. Se o cruzamento com a apólice e com o clima evitar um ponto percentual do valor avisado, são cerca de R$ 1 milhão por evento. No protótipo, a IA sugeriu R$ 4,8 milhões de ajuste por evidência, mas eu não uso esse número: o dado é sintético e a fraude foi plantada por nós. Segunda: custo de regulação. Com 30% dos casos no fast track, e não os 55% que medimos, são 2.400 sinistros que não passam por um regulador, a cerca de R$ 600 cada. Terceira, anual: segurado pago rápido renova mais. Cinco pontos de retenção dão cerca de R$ 600 mil por ano. <b>Ponto para a diretora:</b> eu escolhi premissas moderadas; a PoC troca cada uma por um número de vocês.</div>
</div>
`);

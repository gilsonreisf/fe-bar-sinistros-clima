/* ============================================================================
 * RESULTADOS MEDIDOS  —  seis números do teste final nos lotes nunca vistos.
 * Usage: 43-statcards; números estáticos (vírgula decimal), tendência como contexto.
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>Metade saiu sem fila e quase nenhum suspeito passou</h2>
      <p class="slide-sub">6.812 avisos em lotes que o modelo nunca viu</p>
      <div class="statgrid">
        <div class="statcard">
          <div class="big">54,9%</div>
          <div class="label">dos avisos liberados no fast track</div>
          <div class="trend up"><span class="arrow"><svg class="gl" data-glyph="↑" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13.5V2.5M4.5 6L8 2.5 11.5 6"/></svg></span> meta de referência: 30%</div>
        </div>
        <div class="statcard">
          <div class="big">11</div>
          <div class="label">suspeitos passaram, de 954</div>
          <div class="trend down"><span class="arrow"><svg class="gl" data-glyph="↓" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5v11M4.5 10L8 13.5 11.5 10"/></svg></span> 1,2% dos suspeitos, R$ 23 mil</div>
        </div>
        <div class="statcard">
          <div class="big">99,4%</div>
          <div class="label">das recomendações da IA certas</div>
          <div class="trend up"><span class="arrow"><svg class="gl" data-glyph="↑" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13.5V2.5M4.5 6L8 2.5 11.5 6"/></svg></span> 99,6% dos valores a ±10%</div>
        </div>
        <div class="statcard">
          <div class="big">15 × 33</div>
          <div class="label">suspeitos liberados: modelo × regra</div>
          <div class="trend down"><span class="arrow"><svg class="gl" data-glyph="↓" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5v11M4.5 10L8 13.5 11.5 10"/></svg></span> AUC de 0,997 contra 0,962</div>
        </div>
        <div class="statcard">
          <div class="big">16 de 16</div>
          <div class="label">perguntas certas no Genie</div>
          <div class="trend up"><span class="arrow"><svg class="gl" data-glyph="↑" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13.5V2.5M4.5 6L8 2.5 11.5 6"/></svg></span> mesmas métricas do painel</div>
        </div>
        <div class="statcard">
          <div class="big">US$ 0,007</div>
          <div class="label">por sinistro processado</div>
          <div class="trend down"><span class="arrow"><svg class="gl" data-glyph="↓" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5v11M4.5 10L8 13.5 11.5 10"/></svg></span> ~US$ 52 por evento</div>
        </div>
      </div>
    </div>
  </div>
  <div class="notes"><b>Tell: o que os números dizem (1 min 30).</b> Estes números vêm de um teste honesto: o modelo foi treinado num histórico de 2025 e avaliado em nove lotes do evento que ele nunca tinha visto. Para a diretora, três números: metade dos avisos saiu sem fila; dos 954 suspeitos, só 11 passaram pelo fast track, somando R$ 23 mil; e a IA acertou 99,4% das recomendações. Para o arquiteto: o modelo de suspeita bate a regra fixa que muita seguradora usa hoje, com AUC de 0,997 contra 0,962, e entre os casos elegíveis ao fast track deixa passar 15 suspeitos, contra 33 da regra. O Genie acertou as 16 perguntas de referência da diretoria. <b>Ressalva que eu faço antes que perguntem:</b> os dados são sintéticos, com padrões de fraude que nós mesmos plantamos. Por isso a acurácia é alta; com dados reais ela vai cair, e é exatamente isso que a PoC mede.</div>
</div>
`);

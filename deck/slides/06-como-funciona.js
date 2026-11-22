/* ============================================================================
 * COMO FUNCIONA  —  o caminho de um aviso, em quatro passos de negócio.
 * Usage: off-workflow (quatro .wf-step com setas).
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>Cada aviso é analisado assim que chega</h2>
      <p class="slide-sub">A IA lê e recomenda, o código calcula, o regulador decide</p>
      <div class="workflow" style="flex:0 0 300px">
        <div class="wf-step"><div class="no">1</div><h3>O aviso chega</h3><p>Aviso, fotos, orçamento e laudo em PDF entram assim que o segurado registra.</p></div>
        <div class="wf-arrow"><svg class="gl" data-glyph="→" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 8h10.5M9 4.5L12.5 8 9 11.5"/></svg></div>
        <div class="wf-step"><div class="no">2</div><h3>A IA lê e cruza</h3><p>Documentos contra a apólice, o clima do INMET e da Defesa Civil e a tabela de preços.</p></div>
        <div class="wf-arrow"><svg class="gl" data-glyph="→" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 8h10.5M9 4.5L12.5 8 9 11.5"/></svg></div>
        <div class="wf-step"><div class="no">3</div><h3>Fast track ou fila</h3><p>O caso simples sai sem fila. O resto entra por suspeita, valor e espera.</p></div>
        <div class="wf-arrow"><svg class="gl" data-glyph="→" viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 8h10.5M9 4.5L12.5 8 9 11.5"/></svg></div>
        <div class="wf-step"><div class="no">4</div><h3>O regulador decide</h3><p>Parecer e evidências lado a lado. Cada decisão mede a IA.</p></div>
      </div>
      <div class="insight light" style="margin-top:28px"><div class="ih">Regra de ouro</div><div class="it">A IA não calcula valor e não libera nada fora do fast track.</div></div>
    </div>
  </div>
  <div class="notes"><b>Tell: o que muda (1 min).</b> O processo que vocês conhecem continua, só que cada aviso chega ao regulador já trabalhado. Passo 1: o aviso e os documentos entram como entram hoje. Passo 2: a IA lê os PDFs e confronta o pedido com a apólice, com o clima que de fato aconteceu naquele município e naquele dia, com a tabela de preços e com o histórico do prestador. Passo 3: o caso simples, de valor baixo, com cobertura e evidência climática forte, sai sem fila; o resto entra numa fila ordenada por suspeita, valor e espera, e não mais por ordem de chegada. Passo 4: o regulador decide, com o parecer da IA ao lado das evidências, e cada decisão dele vira medida de qualidade da IA. <b>Regra de ouro:</b> a IA não calcula valor e não paga nada fora do fast track.</div>
</div>
`);

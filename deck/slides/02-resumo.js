/* ============================================================================
 * RESUMO EXECUTIVO  —  a história inteira em um slide, fechando na recomendação.
 * Usage: 54-exec-summary; quatro itens, o último é a recomendação.
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>Resumo executivo</h2>
      <p class="slide-sub">Pagar rápido quem tem direito e segurar quem não tem, testado em 6.812 avisos de um evento</p>
      <div class="exsum">
        <div class="item"><div class="n">01</div><div><div class="eh">Metade dos avisos sai sem fila</div><div class="ed">54,9% foram liberados no fast track. Entre os 3.737 liberados, só 11 eram suspeitos (R$ 23 mil).</div></div></div>
        <div class="item"><div class="n">02</div><div><div class="eh">O regulador recebe o caso já analisado</div><div class="ed">A IA lê os PDFs, cruza com a apólice e com o clima real e sugere o parecer: 99,4% das recomendações certas.</div></div></div>
        <div class="item"><div class="n">03</div><div><div class="eh">Ganho de referência de R$ 2,4 milhões por evento</div><div class="ed">Pagamento indevido evitado e custo de regulação, a calibrar na PoC. O processamento custa cerca de US$ 0,007 por sinistro.</div></div></div>
        <div class="item"><div class="n">04</div><div><div class="eh">Recomendação: PoC de 6 semanas com um evento histórico de vocês</div><div class="ed">Medir o tempo até a indenização, o pagamento indevido evitado e a concordância dos reguladores com a IA.</div></div></div>
      </div>
    </div>
  </div>
  <div class="notes"><b>Tell (1 min): a história inteira antes do detalhe.</b> Se vocês guardarem um slide, é este. Primeiro: metade dos avisos de um evento pode sair sem fila, e no nosso teste só 11 de quase mil suspeitos passaram por esse caminho, somando R$ 23 mil. Segundo: o regulador deixa de ler PDF por PDF e recebe o caso já analisado, com o parecer da IA ao lado das evidências. Terceiro: numa seguradora do porte de vocês, a nossa referência é de R$ 2,4 milhões por evento, número que a gente quer calibrar com os dados de vocês, e não prometer. Quarto, o pedido: uma PoC de seis semanas com um evento que vocês já viveram. <b>Para a diretora:</b> "Quanto do avisado no último evento foi pago sem precisar? E em quantos dias o segurado simples recebeu?" (deixar ela responder; é o gancho da PoC).</div>
</div>
`);

/* ============================================================================
 * PROBLEMA  —  as três dores que chegam juntas no pico de um evento climático.
 * Usage: 36-problem; três cartões com ícone inline.
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>No pico de um evento, três problemas chegam juntos</h2>
      <p class="slide-sub">Milhares de avisos em poucos dias, na mesma região</p>
      <div class="problem-cards">
        <div class="problem-card">
          <div class="ico"><svg role="img" aria-label="Relógio" viewBox="-5 -5 34 34" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="stroke:var(--db-orange)"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></div>
          <h3>O segurado espera semanas</h3>
          <p>Cerca de 30 dias na nossa referência: fila por ordem de chegada e PDF lido um a um. Gera reclamação e perde a renovação.</p>
        </div>
        <div class="problem-card">
          <div class="ico"><svg role="img" aria-label="Dinheiro" viewBox="-5 -5 34 34" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="stroke:var(--db-orange)"><circle cx="12" cy="12" r="9"/><path d="M14.5 9.2c-.6-.8-1.6-1.2-2.6-1.2-1.5 0-2.7.9-2.7 2.1 0 2.8 5.6 1.5 5.6 4.3 0 1.2-1.2 2.1-2.9 2.1-1.1 0-2.1-.4-2.7-1.2"/><path d="M12 6.3v11.4"/></svg></div>
          <h3>Paga-se o que não devia</h3>
          <p>Na pressa passam orçamento inflado, dano anterior, causa sem cobertura e aviso fora do evento.</p>
        </div>
        <div class="problem-card">
          <div class="ico"><svg role="img" aria-label="Gráfico em alta" viewBox="-5 -5 34 34" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="stroke:var(--db-orange)"><path d="M3 20h18"/><path d="M5 16l5-5 4 3 6-7"/><path d="M15 7h5v5"/></svg></div>
          <h3>Custo e prazo estouram</h3>
          <p>Hora extra, regulador terceirizado e o prazo de 30 dias da SUSEP, sem saber quanto o evento já custou.</p>
        </div>
      </div>
    </div>
  </div>
  <div class="notes"><b>Tell: o problema (1 min 30).</b> Depois de um granizo ou de uma enchente, a operação de regulação recebe em uma semana o que costuma receber em meses. Três coisas acontecem ao mesmo tempo. Um: o segurado, que acabou de perder o telhado ou o estoque, espera semanas (a nossa referência é de cerca de 30 dias), porque a fila é por ordem de chegada e cada caso depende de alguém ler os documentos. Dois: na pressa, passa o que não devia passar, como o orçamento inflado, o dano antigo declarado como novo ou a causa que a apólice não cobre. Três: o custo de regulação explode e o prazo da SUSEP aperta, e a diretoria não sabe em tempo real quanto o evento já custou para reservar e acionar o resseguro. <b>Pergunta de descoberta:</b> "Qual desses três doeu mais no último evento de vocês?" Use a resposta para dar peso ao KPI certo nos próximos slides.</div>
</div>
`);

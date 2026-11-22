/* ============================================================================
 * FAQ TÉCNICO  —  as quatro perguntas da arquitetura de TI.
 * Usage: 100-faq (2 x 2).
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>As perguntas da arquitetura de TI</h2>
      <div class="cardset c2 faq-grid">
        <div class="faq-card">
          <h3>E a LGPD?</h3>
          <p>Tag nas colunas pessoais e CPF mascarado na gold. App e Genie não veem o CPF aberto. Auditoria e lineage no catálogo.</p>
        </div>
        <div class="faq-card">
          <h3>E a qualidade do dado?</h3>
          <p>Expectations no pipeline. PDF ilegível, cobertura ausente ou parecer inválido bloqueiam o fast track.</p>
        </div>
        <div class="faq-card">
          <h3>E se o modelo de linguagem mudar?</h3>
          <p>Prompt e modelo passam pelo mesmo portão de avaliação. Trocamos o modelo do lote com evidência medida.</p>
        </div>
        <div class="faq-card">
          <h3>Dois reguladores no mesmo caso?</h3>
          <p>Assumir trava o caso no Lakebase: no teste simultâneo, nenhum repetido. O clique duplo grava uma decisão só.</p>
        </div>
      </div>
    </div>
  </div>
  <div class="notes"><b>LGPD:</b> as colunas com dado pessoal têm tag no Unity Catalog; o CPF aparece mascarado numa visão dinâmica da gold, o Genie lê a gold, e o app tem permissão mínima (leitura da gold e da entrada do parecer, escrita só no schema operacao do Lakebase). A máscara ficou na visão, e não na tabela do pipeline, para não quebrar os cruzamentos. <b>Qualidade:</b> o pipeline tem expectations; um documento ilegível ou uma extração com falha vira flag e manda o caso ao regulador. <b>Troca de modelo:</b> comparamos Haiku e Sonnet no mesmo dataset; para o lote ficou o Haiku 5.5, que empatou na recomendação (95,1%) a cerca de US$ 0,002 por parecer; no app ficou o Sonnet, melhor no texto que o regulador lê. <b>Concorrência:</b> no teste, 6 pedidos simultâneos de dois reguladores entregaram 6 casos distintos, e o mesmo id de decisão não grava duas vezes. <b>Se perguntarem de integração ou pico,</b> volte ao slide 15.</div>
</div>
`);

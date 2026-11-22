/* ============================================================================
 * PRONTO PARA A TI  —  integração, segurança e escala, com o ícone de cada produto.
 * Usage: off-three-col-icon.
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>Como integra, protege o dado e aguenta o pico</h2>
      <p class="slide-sub">As três perguntas da arquitetura</p>
      <div class="cols c3">
        <div>
          <img class="icon-spot icon-line" src="resources/official/icons/lakeflow-connect-icon-full-color.svg" alt="Lakeflow Connect">
          <h3>Integração</h3>
          <p>No protótipo, arquivos num Volume. Em produção, CDC do sistema de sinistros e volta pela tabela de decisões ou pelo Postgres.</p>
        </div>
        <div>
          <img class="icon-spot icon-line" src="resources/official/icons/unity-catalog-icon-full-color.svg" alt="Unity Catalog">
          <h3>Segurança e LGPD</h3>
          <p>Dado pessoal com tag e CPF mascarado. App e Genie nunca veem o CPF aberto, com auditoria e lineage.</p>
        </div>
        <div>
          <img class="icon-spot icon-line" src="resources/official/icons/lakeflow-jobs-icon-full-color.svg" alt="Lakeflow Jobs">
          <h3>Escala no pico</h3>
          <p>Serverless e incremental: a chegada do arquivo dispara o job. O gargalo medido é o modelo de linguagem, e a saída é capacidade reservada.</p>
        </div>
      </div>
    </div>
  </div>
  <div class="notes"><b>Integração (proposta):</b> o protótipo recebe arquivos num Volume; em produção, o Lakeflow Connect lê do sistema de sinistros por CDC. A volta é pela tabela de decisões no Unity Catalog ou direto no Postgres do Lakebase, por API. <b>Segurança e LGPD:</b> as colunas pessoais têm tag; o CPF é mascarado numa visão da gold, e só um grupo autorizado vê o número completo; o app roda com um service principal de permissão mínima (leitura da gold e da entrada do parecer, escrita só no schema operacao do Lakebase), e isso foi provado no deploy, quando o build falhou antes da permissão e passou depois. <b>Escala:</b> tudo serverless; a chegada do lote dispara o job. O que medimos como limite foi a vazão do modelo de linguagem pago por token, cerca de 21 pareceres por minuto; em produção, isso se resolve com throughput provisionado, dimensionado na PoC. Um parecer inválido nunca libera o fast track: o caso vai para o regulador. E, se o parecer em lote passar do tempo, o próprio job agenda a continuação e retoma os pendentes.</div>
</div>
`);

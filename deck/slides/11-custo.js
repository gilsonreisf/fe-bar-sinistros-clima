/* ============================================================================
 * CUSTO MEDIDO  —  custo por unidade e por evento, do system.billing.
 * Usage: 07-metrics-static + nota da premissa.
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>Processar um sinistro custa menos de um centavo de dólar</h2>
      <p class="slide-sub">Faturamento do workspace a preço de lista: referência, a calibrar na PoC</p>
      <div class="metrics-row">
        <div class="metric"><div class="big">0,007</div><div class="lbl">US$ por sinistro: leitura dos PDFs, pipeline e parecer em lote</div></div>
        <div class="metric"><div class="big">~52</div><div class="lbl">US$ por evento de 8 mil avisos, ou ~US$ 160 por ano com 3 eventos</div></div>
        <div class="metric"><div class="big">0,02</div><div class="lbl">US$ por reanálise no app, estimado pelos tokens</div></div>
      </div>
      <p class="cap-note">Fora do evento, o Lakebase e o endpoint escalam a zero. O SQL Warehouse do painel e do Genie conta enquanto estiver ligado.</p>
    </div>
  </div>
  <div class="notes"><b>Custo (1 min), para os dois.</b> Medimos o custo real no faturamento do workspace, a preço de lista: cerca de US$ 0,0047 por aviso no pipeline, já com a leitura dos PDFs (US$ 0,0034 por PDF), e US$ 0,002 por parecer em lote. Somando, cerca de US$ 0,007 por sinistro, ou uns US$ 52 para um evento inteiro de 8 mil avisos. A reanálise que o regulador pede no app usa um modelo maior; pela contagem de tokens, estimamos cerca de US$ 0,02 por clique, ainda a confirmar no faturamento. O custo fixo é o SQL Warehouse do painel e do Genie enquanto estiver ligado; o banco e o endpoint desligam sozinhos fora do evento. Isso é referência: o volume de PDFs por aviso e o tamanho dos documentos de vocês mudam a conta, e a PoC mede com os dados reais. Num cenário de mais páginas por documento, o custo por sinistro pode chegar a alguns centavos, ainda pequeno diante de R$ 600 de regulação por caso. <b>Mensagem para a diretora:</b> o custo da plataforma não é o que decide este projeto; o que decide é o processo e o valor que ele protege.</div>
</div>
`);

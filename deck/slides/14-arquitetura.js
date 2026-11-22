/* ============================================================================
 * ARQUITETURA  —  as camadas integradas, do Lakeflow ao app, sob o Unity Catalog.
 * Usage: 29-architecture (arch-grid em três linhas).
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>Cada camada entrega à próxima, sob o mesmo catálogo</h2>
      <p class="slide-sub">Tudo serverless; pipeline, jobs e app por bundle, o resto por scripts</p>
      <div class="arch-grid">
        <div class="arch-row" style="grid-template-columns:repeat(5,1fr)">
          <div class="arch-box"><img src="resources/official/icons/lakeflow-icon-full-color.svg" alt="">1. Lakeflow<small>Auto Loader e AI Functions leem avisos e PDFs</small></div>
          <div class="arch-box"><img src="resources/official/icons/mosaic-ai-icon-full-color.svg" alt="">2. ML e GenAI<small>Score de suspeita e parecer avaliado</small></div>
          <div class="arch-box"><img src="resources/official/icons/primary-icon-orange-delta-lake.svg" alt="">3. Gold<small>Fast track, prioridade e métricas</small></div>
          <div class="arch-box"><img src="resources/official/icons/lakebase-icon-full-color.svg" alt="">4. Lakebase<small>Fila e decisões com transação</small></div>
          <div class="arch-box"><img src="resources/official/icons/apps-icon-full-color.svg" alt="">5. App e Genie<small>Regulador e diretoria</small></div>
        </div>
        <div class="arch-row" style="grid-template-columns:1fr">
          <div class="arch-box">6. As decisões voltam ao lakehouse pelo Lakehouse Sync e medem a IA<small>Concordância e divergências viram rótulo para o retreino</small></div>
        </div>
        <div class="arch-row" style="grid-template-columns:1fr">
          <div class="arch-box head"><img src="resources/official/icons/unity-catalog-icon-full-color.svg" alt="" style="display:inline-block;height:26px;margin:0 12px 0 0;vertical-align:middle">Unity Catalog: permissões, tags de LGPD, lineage, metric views, modelos e prompts</div>
        </div>
      </div>
    </div>
  </div>
  <div class="notes"><b>Para o arquiteto (1 min 30), da esquerda para a direita.</b> 1. O Lakeflow, com Auto Loader, ingere avisos, PDFs, apólices e os dados públicos de clima; o ai_parse_document e o ai_extract leem os PDFs dentro do próprio pipeline, sem um serviço de OCR à parte. Os 8 mil avisos e 9.705 PDFs do evento chegaram à silver, já lidos e cruzados, em cerca de 26 minutos; o parecer em lote vem depois, no ritmo do modelo de linguagem. 2. O modelo de suspeita (LightGBM, registrado no Unity Catalog com o alias champion) e o parecer do modelo de linguagem, com prompt versionado e avaliado. 3. A gold junta tudo e aplica as regras de fast track e prioridade, com MERGE idempotente. 4. Uma synced table leva a gold ao Lakebase, o Postgres gerenciado, porque fila e decisão precisam de transação e lock, o que um warehouse não dá. 5. O app (AppKit) e o Genie leem as mesmas metric views, então o número do painel é o número do Genie. 6. As decisões voltam ao lakehouse pelo Lakehouse Sync, como histórico, e medem a IA. Tudo isso sob o Unity Catalog. <b>Prova:</b> o rastreio de um sinistro, do arquivo à decisão, está em texto no repositório.</div>
</div>
`);

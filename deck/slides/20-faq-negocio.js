/* ============================================================================
 * FAQ DE NEGÓCIO  —  as quatro perguntas da diretoria de sinistros.
 * Usage: 100-faq (2 x 2).
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>As perguntas da diretoria de sinistros</h2>
      <div class="cardset c2 faq-grid">
        <div class="faq-card">
          <h3>E se a IA errar e pagarmos fraude?</h3>
          <p>Fora do fast track a IA não paga nada. No teste, 11 suspeitos (R$ 23 mil) passaram, contra 3.737 casos liberados sem regulador.</p>
        </div>
        <div class="faq-card">
          <h3>O regulador vai confiar?</h3>
          <p>Ele vê motivos, cláusulas e evidências, decide e pode divergir. A concordância é medida todo dia.</p>
        </div>
        <div class="faq-card">
          <h3>Os dados são sintéticos. Vale para nós?</h3>
          <p>O clima é real e a fraude foi plantada. Por isso a PoC usa um evento de vocês e as decisões já tomadas.</p>
        </div>
        <div class="faq-card">
          <h3>Quanto custa e quando se paga?</h3>
          <p>Cerca de US$ 0,007 por sinistro processado. O ganho de referência é R$ 2,4 mi por evento, a calibrar.</p>
        </div>
      </div>
    </div>
  </div>
  <div class="notes"><b>Fraude:</b> o fast track exige todas as condições ao mesmo tempo (valor até R$ 5 mil, cobertura válida, evidência climática forte, score de suspeita baixo, parecer de pagamento integral e nenhum alerta bloqueante (documento ilegível ou ausente, orçamento divergente, preço acima da tabela, dano anterior no laudo, apólice fora de vigência)), e qualquer dado faltante bloqueia. O risco residual é pequeno e conhecido: R$ 23 mil em suspeitos, contra R$ 8 milhões liberados sem regulador, e pode ser auditado depois por amostragem. <b>Confiança:</b> o regulador é quem decide; a tela de supervisão mostra onde a IA e ele divergem, e essas divergências viram rótulo para o retreino. <b>Dados sintéticos:</b> o clima é do INMET e da Defesa Civil, os municípios são do IBGE; os avisos e a fraude são simulados, e por isso o acerto é alto. A PoC mede com o histórico de vocês. <b>Custo e retorno:</b> o custo da plataforma por evento é de dezenas de dólares; o retorno vem do processo e é a primeira coisa que a PoC recalcula.</div>
</div>
`);

/* ============================================================================
 * CONFIANÇA  —  a divisão de papéis entre a IA, o código e o regulador.
 * Usage: 21-cards-static; três cartões.
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide">
    <div class="pad">
      <h2>A IA trabalha sob o controle do regulador</h2>
      <p class="slide-sub">Cada papel tem um dono, e cada uso da IA é avaliado e auditado</p>
      <div class="cardset">
        <div class="cardo">
          <h3>A IA lê, cruza e recomenda</h3>
          <p>Pagar, pagar parcial, recusar ou investigar, com motivos e cláusulas citadas, ao lado das evidências.</p>
        </div>
        <div class="cardo">
          <h3>O código calcula o valor</h3>
          <p>Franquia, limite e tabela de preços entram em regra testada. O modelo de linguagem não define quanto pagar.</p>
        </div>
        <div class="cardo">
          <h3>O regulador decide e mede a IA</h3>
          <p>Fora do fast track, toda decisão é humana. A concordância com a IA aparece todo dia na tela de supervisão.</p>
        </div>
      </div>
    </div>
  </div>
  <div class="notes"><b>Responde à objeção antes dela (1 min): "e se a IA errar?"</b> A gente separou os papéis. A IA lê os documentos, cruza e recomenda, sempre mostrando o porquê. O valor nunca sai do modelo de linguagem: sai de um cálculo com franquia, limite e tabela de preços, coberto por testes. E o regulador decide tudo o que não é fast track. O fast track só libera quando tudo bate: valor até R$ 5 mil, cobertura válida, evidência climática forte, score de suspeita baixo, parecer de pagamento integral e nenhum alerta bloqueante (documento ilegível ou ausente, orçamento divergente, preço acima da tabela, dano anterior no laudo, apólice fora de vigência). Qualquer dado faltante manda o caso para o regulador. <b>Para o arquiteto:</b> o prompt é versionado e só vai para produção se passar no portão de avaliação do MLflow (66% para 95% de acerto entre a versão 1 e a 2), e cada parecer grava o modelo, o prompt e a versão usados; a reanálise do app passa pelo AI Gateway, com trace.</div>
</div>
`);

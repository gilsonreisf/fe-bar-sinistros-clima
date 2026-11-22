/* ============================================================================
 * DEMONSTRAÇÃO  —  abre o app publicado numa aba nova (o workspace bloqueia iframe).
 * Usage: 33-demo-single com data-demo-mode="popup"; o roteiro da demo está nas notas.
 * ============================================================================ */
DECK.slide(`
<div class="slide-wrap">
  <div class="slide demo" data-demo-url="https://sinistros-clima-dev-7474657549414280.aws.databricksapps.com" data-demo-mode="popup">
    <div class="pad">
      <div class="demo-poster">
        <h2>Demonstração: um dia de evento, do painel à decisão</h2>
        <p class="slide-sub">Granizo e vendaval em Santa Catarina, 8 mil avisos sintéticos</p>
        <p>Painel do evento, fila do regulador, parecer da IA, decisão, supervisão da IA e as perguntas da diretoria no Genie.</p>
        <div class="demo-url">https://sinistros-clima-dev-7474657549414280.aws.databricksapps.com</div>
        <button class="demo-launch"><svg class="gl" data-glyph="▶" viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3.2l8 4.8-8 4.8z" style="fill:currentColor;stroke:none"/></svg>Abrir o app da regulação</button>
        <a class="demo-pop" href="https://sinistros-clima-dev-7474657549414280.aws.databricksapps.com" target="_blank" rel="noopener">Abrir numa aba nova</a>
      </div>
    </div>
  </div>
  <div class="notes"><b>Tell antes do show (20 s):</b> "Vou mostrar um evento de granizo e vendaval em Santa Catarina, com 8 mil avisos sintéticos sobre o clima real do INMET e da Defesa Civil. Prestem atenção em dois momentos: quanto saiu sem fila e como o regulador decide com a IA do lado."<br><br><b>Show (9 min), na ordem:</b><br>1. <b>Painel do evento:</b> 7.612 avisos analisados, R$ 88,6 mi reclamados, 54% no fast track (R$ 8,9 mi liberados), 3.487 com o regulador, 1.142 suspeitos (R$ 23 mi reclamados) e R$ 4,8 mi de ajuste por evidência sugerido pela IA. Frase: "Metade dos casos simples já saiu sem fila; o regulador cuida do resto."<br>2. <b>Fila do regulador:</b> ordem por prioridade e o motivo de cada caso estar fora do fast track; clicar em Assumir próximo. Frase: "Assumir trava o caso: no teste com dois reguladores ao mesmo tempo, nenhum caso saiu repetido."<br>3. <b>Detalhe:</b> parecer com motivos e cláusulas ao lado da apólice, do clima da estação do INMET, do preço contra a tabela e do prestador; CPF mascarado. Frase: "O valor sai de cálculo, não do modelo de linguagem."<br>4. <b>Reanalisar com IA:</b> nova análise em segundos, auditada.<br>5. <b>Decidir:</b> registrar uma decisão divergindo da IA. Frase: "A decisão é do regulador; a divergência vira aprendizado."<br>6. <b>IA sob supervisão:</b> concordância e a matriz IA contra regulador. Frase: "É assim que a diretoria confia: medindo a IA todo dia."<br>7. <b>Genie da diretoria</b> (link no cabeçalho): "Quais municípios concentram mais sinistros suspeitos?" e "Quanto a IA sugeriu ajustar por evidência?". Frase: "O mesmo número do painel, em português, sem pedir relatório para a TI."<br><br><b>Plano B:</b> se o login ou a rede falhar, siga para os resultados medidos (próximo slide) e conte o caminho de um sinistro, do arquivo à decisão, pelo evidencias/08-rastreio-ponta-a-ponta.md.<br><b>Tell depois do show (30 s):</b> "O que vocês viram: o caso simples pago sem fila, o regulador só onde há valor ou suspeita, e a IA medida contra ele. Agora os números."</div>
</div>
`);

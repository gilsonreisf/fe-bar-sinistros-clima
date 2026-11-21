-- Metric views da fase 7 (D-025): as métricas de negócio ficam definidas uma única vez no Unity Catalog e são usadas pelo
-- Genie da diretoria, pelo app e por quem consulta em SQL. Idempotente (CREATE OR REPLACE).

-- 1. Sinistros do evento: volume, exposição, fast track, suspeita e o que a IA recomendou.
CREATE OR REPLACE VIEW ${catalogo}.${schema_gold}.sinistros_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: ${catalogo}.${schema_gold}.sinistros_analisados
comment: "Sinistros do evento climático analisados (score de suspeita, parecer prévio por IA, fast track e prioridade). Uma linha por aviso."
joins:
  - name: dim_aviso
    source: ${catalogo}.${schema_silver}.sinistros_enriquecidos
    using:
      - id_aviso
dimensions:
  - name: Lote
    expr: lote
    comment: "Lote de chegada dos avisos (1 a 10); cada lote cobre parte dos dias do evento."
  - name: Data do aviso
    expr: data_aviso
    synonyms: ["data de abertura", "dia do aviso"]
  - name: Município
    expr: municipio
    synonyms: ["cidade", "local"]
  - name: Causa declarada
    expr: causa_declarada
    comment: "Causa informada pelo segurado: alagamento, vendaval, granizo etc."
    synonyms: ["causa", "tipo de evento"]
  - name: Ramo
    expr: dim_aviso.ramo
    comment: "Ramo do seguro: residencial ou empresarial."
  - name: Canal
    expr: dim_aviso.canal
    synonyms: ["canal de abertura"]
  - name: Força da evidência climática
    expr: dim_aviso.forca_evidencia_climatica
    comment: "forte, fraca ou contraria (o clima medido contradiz a causa), conforme INMET e Defesa Civil."
    synonyms: ["evidência climática", "confirmação do evento"]
  - name: Recomendação da IA
    expr: recomendacao_ia
    comment: "pagar_integral, pagar_parcial, recusar ou investigar (parecer prévio; a decisão final é do regulador)."
    synonyms: ["parecer", "recomendação"]
  - name: Fast track
    expr: "CASE WHEN fast_track THEN 'sim' ELSE 'não' END"
    comment: "sim quando o sinistro foi liberado sem fila (valor baixo, cobertura válida, evidência forte, baixa suspeita)."
    synonyms: ["liberação automática", "pagamento rápido"]
  - name: Faixa de valor
    expr: "CASE WHEN valor_reclamado <= 5000 THEN '1. até R$ 5 mil' WHEN valor_reclamado <= 20000 THEN '2. R$ 5 a 20 mil' WHEN valor_reclamado <= 50000 THEN '3. R$ 20 a 50 mil' ELSE '4. acima de R$ 50 mil' END"
  - name: Faixa de suspeita
    expr: "CASE WHEN score_suspeita IS NULL THEN 'sem score' WHEN score_suspeita >= 0.5 THEN 'alta' WHEN score_suspeita >= 0.2 THEN 'média' ELSE 'baixa' END"
    comment: "baixa (< 0,2, pode ir ao fast track), média (0,2 a 0,5) e alta (>= 0,5)."
    synonyms: ["risco de fraude", "suspeita"]
measures:
  - name: Avisos
    expr: COUNT(1)
    comment: "Quantidade de avisos de sinistro."
    synonyms: ["sinistros", "quantidade de sinistros", "volume"]
  - name: Valor reclamado
    expr: SUM(valor_reclamado)
    comment: "Soma do valor pedido pelos segurados (exposição do evento)."
    synonyms: ["exposição", "valor pedido"]
    format:
      type: currency
      currency_code: BRL
  - name: Valor sugerido pela IA
    expr: SUM(valor_sugerido)
    comment: "Soma do valor que o parecer prévio sugere pagar (franquia, LMI e itens válidos calculados em código)."
    format:
      type: currency
      currency_code: BRL
  - name: Ajuste por evidência sugerido pela IA
    expr: "SUM(CASE WHEN recomendacao_ia IN ('pagar_parcial', 'recusar') AND dim_aviso.cobertura_valida THEN greatest(greatest(least(valor_reclamado, dim_aviso.lmi) - coalesce(dim_aviso.franquia, 0), 0) - coalesce(valor_sugerido, 0), 0) ELSE 0 END)"
    comment: "Nos sinistros com cobertura válida, quanto o parecer sugere abaixo do valor contratual devido (reclamado limitado ao LMI, menos a franquia) por evidência: orçamento acima da tabela, itens não cobertos, dano anterior ou falta de evento climático. Franquia, LMI e recusa por falta de cobertura não entram. É sugestão: a decisão é do regulador."
    synonyms: ["ajuste sugerido", "redução sugerida pela IA", "valor contestado pela IA"]
    format:
      type: currency
      currency_code: BRL
  - name: Sinistros no fast track
    expr: COUNT(1) FILTER (WHERE fast_track)
    synonyms: ["liberados automaticamente"]
  - name: Percentual de fast track
    expr: COUNT(1) FILTER (WHERE fast_track) / COUNT(1)
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
  - name: Valor liberado no fast track
    expr: SUM(valor_sugerido) FILTER (WHERE fast_track)
    format:
      type: currency
      currency_code: BRL
  - name: Score médio de suspeita
    expr: AVG(score_suspeita)
  - name: Sinistros suspeitos
    expr: COUNT(1) FILTER (WHERE score_suspeita >= 0.2)
    comment: "Score de suspeita >= 0,2 (fora do fast track, prioridade maior na fila)."
    synonyms: ["suspeitos", "possíveis fraudes"]
  - name: Valor reclamado suspeito
    expr: SUM(valor_reclamado) FILTER (WHERE score_suspeita >= 0.2)
    format:
      type: currency
      currency_code: BRL
  - name: Encaminhados ao regulador
    expr: COUNT(1) FILTER (WHERE NOT fast_track)
    comment: "Sinistros fora do fast track, que passam pelo regulador. Quantos já foram decididos está em regulacao_metrics."
    synonyms: ["fora do fast track", "enviados ao regulador", "fila"]
  - name: Recusas por falta de cobertura
    expr: COUNT(1) FILTER (WHERE recomendacao_ia = 'recusar' AND NOT coalesce(dim_aviso.cobertura_valida, false))
    comment: "Pareceres de recusa porque a apólice não cobre a causa (ou não existe); não é ajuste por evidência."
  - name: Valor reclamado sem cobertura
    expr: SUM(valor_reclamado) FILTER (WHERE NOT coalesce(dim_aviso.cobertura_valida, false))
    format:
      type: currency
      currency_code: BRL
  - name: Pareceres pendentes
    expr: COUNT(1) FILTER (WHERE status_parecer <> 'ok')
    comment: "Avisos sem parecer prévio válido ainda (o job tenta de novo, até 3 vezes)."
$$;

-- 2. Regulação sob supervisão: o regulador decide, e a decisão fica ao lado da recomendação da IA (laço de retorno).
CREATE OR REPLACE VIEW ${catalogo}.${schema_gold}.regulacao_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
source: ${catalogo}.${schema_operacional}.lb_decisoes_regulador_history
filter: _pg_change_type = 'insert'
comment: "Decisões dos reguladores registradas no app (Lakebase, de volta ao UC pelo Lakehouse Sync), comparadas com a recomendação da IA."
dimensions:
  - name: Regulador
    expr: regulador
  - name: Decisão do regulador
    expr: decisao
    synonyms: ["decisão final"]
  - name: Recomendação da IA
    expr: recomendacao_ia
  - name: Data da decisão
    expr: CAST(criado_em AS DATE)
  - name: Versão do prompt
    expr: versao_prompt
  - name: Versão do modelo
    expr: versao_modelo
measures:
  - name: Decisões
    expr: COUNT(1)
    synonyms: ["sinistros regulados", "decisões do regulador"]
  - name: Concordância com a IA
    expr: COUNT(1) FILTER (WHERE concordou_com_ia) / COUNT(1)
    comment: "Parcela das decisões iguais à recomendação da IA."
    synonyms: ["taxa de concordância", "acerto da IA"]
    format:
      type: percentage
      decimal_places:
        type: max
        places: 1
  - name: Divergências da IA
    expr: COUNT(1) FILTER (WHERE NOT concordou_com_ia)
    comment: "Decisões diferentes da recomendação da IA: insumo do retreino (próximo passo, D-024)."
  - name: Valor aprovado
    expr: SUM(valor_aprovado)
    format:
      type: currency
      currency_code: BRL
  - name: Valor sugerido pela IA
    expr: SUM(valor_sugerido_ia)
    format:
      type: currency
      currency_code: BRL
$$;

-- Conferência: as mesmas métricas, consultadas com MEASURE().
SELECT `Fast track`, MEASURE(`Avisos`) AS avisos, MEASURE(`Valor reclamado`) AS valor_reclamado,
  MEASURE(`Percentual de fast track`) AS pct_fast_track, MEASURE(`Ajuste por evidência sugerido pela IA`) AS ajuste_ia
FROM ${catalogo}.${schema_gold}.sinistros_metrics GROUP BY ALL ORDER BY 1;

SELECT `Faixa de suspeita`, MEASURE(`Avisos`) AS avisos, MEASURE(`Valor reclamado suspeito`) AS valor_suspeito
FROM ${catalogo}.${schema_gold}.sinistros_metrics GROUP BY ALL ORDER BY 1;

SELECT `Recomendação da IA`, MEASURE(`Decisões`) AS decisoes, MEASURE(`Concordância com a IA`) AS concordancia
FROM ${catalogo}.${schema_gold}.regulacao_metrics GROUP BY ALL ORDER BY 1;

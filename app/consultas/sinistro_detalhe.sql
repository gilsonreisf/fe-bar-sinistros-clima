-- Detalhe de um sinistro para o regulador: aviso, apólice, clima, documentos e a análise (CPF mascarado na visão).
-- @param id_aviso STRING = AV-2026-000001
SELECT id_aviso, data_ocorrencia, data_aviso, municipio, causa_declarada, descricao, valor_reclamado, canal,
  ramo, cpf_segurado, cobertura_valida, lmi, franquia, dias_desde_contratacao, dentro_vigencia,
  forca_evidencia_climatica, fonte_evidencia, distancia_estacao_km, registro_defesa_civil, chuva_mm, rajada_max_ms,
  granizo_provavel, valor_orcamento, desvio_preco_pct, menciona_dano_anterior, participacao_prestador_30d,
  to_json(flags_documento) AS flags_documento, to_json(alertas_qualidade) AS alertas_qualidade,
  score_suspeita, fatores_suspeita, versao_modelo, recomendacao_ia, valor_sugerido, to_json(motivos) AS motivos,
  to_json(clausulas) AS clausulas, to_json(itens_excluidos) AS itens_excluidos, confianca, status_parecer,
  versao_prompt, llm, trace_id, fast_track, to_json(bloqueios_fast_track) AS bloqueios_fast_track, prioridade
FROM ${catalogo}.${schema_gold}.sinistro_detalhe
WHERE id_aviso = :id_aviso

-- Saúde do parecer em lote: versões em produção e pareceres pendentes ou inválidos.
SELECT llm, versao_prompt, versao_modelo, status_parecer, count(*) AS avisos, round(avg(confianca), 3) AS confianca_media
FROM ${catalogo}.${schema_gold}.sinistros_analisados
GROUP BY ALL ORDER BY avisos DESC

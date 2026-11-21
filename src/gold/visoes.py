"""Gold: a tabela de sinistros analisados (score + parecer + fast track + prioridade) e as visões da fila, dos KPIs e
do detalhe. Nomes vêm dos parâmetros (D-016). A tabela nasce com Change Data Feed para as synced tables do Lakebase.
"""
from __future__ import annotations

ESQUEMA_GOLD = [
    ("id_aviso", "STRING"), ("lote", "INT"), ("data_aviso", "DATE"), ("municipio", "STRING"),
    ("causa_declarada", "STRING"), ("valor_reclamado", "DOUBLE"),
    ("score_suspeita", "DOUBLE"), ("fatores_suspeita", "STRING"), ("versao_modelo", "STRING"),
    ("recomendacao_ia", "STRING"), ("valor_sugerido", "DOUBLE"), ("motivos", "ARRAY<STRING>"),
    ("clausulas", "ARRAY<STRING>"), ("itens_excluidos", "ARRAY<STRING>"), ("confianca", "DOUBLE"),
    ("status_parecer", "STRING"), ("tentativas_parecer", "INT"), ("versao_prompt", "STRING"), ("llm", "STRING"),
    ("trace_id", "STRING"), ("erros_parecer", "ARRAY<STRING>"),
    ("fast_track", "BOOLEAN"), ("bloqueios_fast_track", "ARRAY<STRING>"), ("prioridade", "DOUBLE"),
    ("analisado_em", "TIMESTAMP"),
]
COLUNAS_GOLD = [c for c, _ in ESQUEMA_GOLD]


def esquema_spark() -> str:
    return ", ".join(f"{c} {t}" for c, t in ESQUEMA_GOLD)


GRUPO_CPF_COMPLETO = "regulacao_sinistros"  # grupo da conta que vê o CPF completo (LGPD: mínimo necessário)


def ddl_gold(catalogo: str, schema_silver: str, schema_gold: str, grupo_cpf: str = GRUPO_CPF_COMPLETO) -> list[str]:
    """O 1º comando cria a tabela; os demais (função de máscara e visões) são recriados a cada execução."""
    s, g = f"{catalogo}.{schema_silver}", f"{catalogo}.{schema_gold}"
    colunas = ",\n  ".join(f"{c} {t}" + (" NOT NULL" if c == "id_aviso" else "") for c, t in ESQUEMA_GOLD)
    return [
        f"""CREATE TABLE IF NOT EXISTS {g}.sinistros_analisados (
  {colunas}
) COMMENT 'Sinistro analisado: score de suspeita, parecer prévio por IA, fast track (com motivos de bloqueio) e prioridade.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')""",
        f"""CREATE OR REPLACE FUNCTION {g}.mascarar_cpf(cpf STRING) RETURNS STRING
COMMENT 'LGPD: CPF completo só para o grupo {grupo_cpf}; os demais veem só os 3 dígitos do meio.'
RETURN CASE WHEN cpf IS NULL THEN NULL WHEN is_account_group_member('{grupo_cpf}') THEN cpf
  ELSE concat('***.', substr(regexp_replace(cpf, '[^0-9]', ''), 4, 3), '.***-**') END""",
        f"""CREATE OR REPLACE VIEW {g}.fila_regulacao
COMMENT 'Fila do regulador: sinistros fora do fast track, do mais prioritário para o menos.'
AS SELECT row_number() OVER (ORDER BY a.prioridade DESC, a.data_aviso, a.id_aviso) AS posicao_fila,
  a.id_aviso, a.lote, a.data_aviso, a.municipio, a.causa_declarada, a.valor_reclamado, a.score_suspeita,
  a.fatores_suspeita, a.recomendacao_ia, a.valor_sugerido, a.confianca, a.status_parecer, a.prioridade,
  a.bloqueios_fast_track, s.forca_evidencia_climatica, s.fonte_evidencia, s.cobertura_valida
FROM {g}.sinistros_analisados a
JOIN {s}.sinistros_enriquecidos s ON s.id_aviso = a.id_aviso
WHERE NOT a.fast_track""",
        f"""CREATE OR REPLACE VIEW {g}.kpis_evento
COMMENT 'KPIs do evento por lote e no total (lote nulo): volume, exposição, fast track, recomendações e valor ajustado pela IA.'
AS SELECT lote, count(*) AS avisos, round(sum(valor_reclamado), 2) AS valor_reclamado,
  sum(CAST(fast_track AS INT)) AS fast_track, round(avg(CAST(fast_track AS DOUBLE)), 4) AS pct_fast_track,
  round(sum(CASE WHEN fast_track THEN valor_sugerido ELSE 0 END), 2) AS valor_pago_fast_track,
  sum(CASE WHEN recomendacao_ia = 'pagar_integral' THEN 1 ELSE 0 END) AS rec_pagar_integral,
  sum(CASE WHEN recomendacao_ia = 'pagar_parcial' THEN 1 ELSE 0 END) AS rec_pagar_parcial,
  sum(CASE WHEN recomendacao_ia = 'recusar' THEN 1 ELSE 0 END) AS rec_recusar,
  sum(CASE WHEN recomendacao_ia = 'investigar' THEN 1 ELSE 0 END) AS rec_investigar,
  round(sum(CASE WHEN recomendacao_ia = 'pagar_parcial' THEN valor_reclamado - valor_sugerido ELSE 0 END), 2)
    AS valor_ajustado_pagamento_parcial,
  sum(CASE WHEN status_parecer <> 'ok' THEN 1 ELSE 0 END) AS pareceres_pendentes,
  round(avg(score_suspeita), 4) AS score_medio
FROM {g}.sinistros_analisados
GROUP BY GROUPING SETS ((lote), ())""",
        f"""CREATE OR REPLACE VIEW {g}.sinistro_detalhe
COMMENT 'Detalhe do sinistro para o app: aviso enriquecido (silver) + análise (gold), com o CPF mascarado (LGPD).'
AS SELECT s.* EXCEPT (cpf_segurado), {g}.mascarar_cpf(s.cpf_segurado) AS cpf_segurado, a.score_suspeita, a.fatores_suspeita, a.versao_modelo, a.recomendacao_ia, a.valor_sugerido, a.motivos,
  a.clausulas, a.itens_excluidos, a.confianca, a.status_parecer, a.versao_prompt, a.llm, a.trace_id, a.fast_track,
  a.bloqueios_fast_track, a.prioridade, a.analisado_em
FROM {s}.sinistros_enriquecidos s
JOIN {g}.sinistros_analisados a ON a.id_aviso = s.id_aviso""",
        f"SET TAG ON COLUMN {g}.sinistro_detalhe.cpf_segurado classificacao_lgpd = dado_pessoal",  # visão: SET TAG ON
    ]

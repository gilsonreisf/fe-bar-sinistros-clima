"""Fast track e prioridade da fila do regulador (spec 6.3, D-020 e D-023), em pandas puro.

Fast track = pagar rápido sem regulador, só para o caso simples, limpo e confirmado. Qualquer dado faltante bloqueia:
na dúvida, o sinistro vai para o regulador (spec 10.3). Os motivos de bloqueio ficam registrados por sinistro.
"""
from __future__ import annotations

import math

import pandas as pd

from regras.features import LIMIAR_FAST_TRACK, TETO_FAST_TRACK_RS

# D-020: alertas de qualidade e flags de documento que bloqueiam; sem_estacao_no_raio é só informativo. Orçamento
# ausente, divergente do pedido ou acima da tabela também bloqueiam (revisão das fases 4 a 8, #5): o fast track não
# depende só do LLM para pegar o pedido maior que o documento.
BLOQUEANTES = ("apolice_inexistente", "fora_vigencia", "datas_incoerentes", "valor_invalido", "causa_desconhecida",
               "documento_ilegivel", "extracao_falhou", "preco_nao_conferido", "documento_ausente", "sem_orcamento",
               "valor_divergente", "preco_acima_referencia")
PESOS_PRIORIDADE = {"suspeita": 0.45, "valor": 0.35, "espera": 0.20}
VALOR_REFERENCIA_RS = 50000.0  # valor normalizado = valor ÷ R$ 50 mil, com teto em 1
ESPERA_REFERENCIA_DIAS = 15.0  # espera normalizada = dias desde o aviso ÷ 15, com teto em 1


def _nulo(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA


def _lista(v) -> list:
    """Lista do Spark (list, tuple ou array do numpy); nulo ou NaN vira lista vazia."""
    if hasattr(v, "tolist"):
        return list(v.tolist())
    return list(v) if isinstance(v, (list, tuple)) else []


def _bloqueios(s: dict) -> list[str]:
    motivos = []
    valor, score = s.get("valor_reclamado"), s.get("score_suspeita")
    if _nulo(valor) or float(valor) > TETO_FAST_TRACK_RS:
        motivos.append("valor_acima_do_teto")
    cobertura = s.get("cobertura_valida")
    if _nulo(cobertura) or not bool(cobertura):
        motivos.append("sem_cobertura")
    if s.get("forca_evidencia_climatica") != "forte":
        motivos.append("evidencia_nao_forte")
    if _nulo(score) or float(score) >= LIMIAR_FAST_TRACK:
        motivos.append("score_suspeita")
    if s.get("recomendacao_ia") != "pagar_integral":
        motivos.append("recomendacao_nao_integral")
    if s.get("status_parecer") != "ok":
        motivos.append("parecer_nao_ok")
    dano = s.get("menciona_dano_anterior")
    if not _nulo(dano) and bool(dano):
        motivos.append("dano_anterior")
    presentes = set(_lista(s.get("alertas_qualidade"))) | set(_lista(s.get("flags_documento")))
    motivos += [b for b in BLOQUEANTES if b in presentes]
    return motivos


def avaliar_fast_track(df: pd.DataFrame) -> pd.DataFrame:
    bloqueios = [_bloqueios(s) for s in df.to_dict("records")]
    return pd.DataFrame({"fast_track": [not b for b in bloqueios], "bloqueios_fast_track": bloqueios}, index=df.index)


def prioridade(df: pd.DataFrame, pesos: dict[str, float] = PESOS_PRIORIDADE, hoje: pd.Timestamp | None = None) -> pd.Series:
    """0 a 1: suspeita, valor e espera ponderados. Dado faltante conta como o pior caso do componente (vai antes).

    `hoje` é o relógio do evento: o job passa a data do último aviso recebido e reaplica a prioridade a cada execução,
    para a espera crescer com o evento (revisão das fases 4 a 8, #4)."""
    if set(pesos) != {"suspeita", "valor", "espera"} or abs(sum(pesos.values()) - 1) > 1e-9:
        raise ValueError(f"os pesos precisam ter suspeita, valor e espera e somar 1: {pesos}")
    hoje = pd.Timestamp.now().normalize() if hoje is None else hoje
    suspeita = pd.to_numeric(df["score_suspeita"], errors="coerce").clip(0, 1).fillna(1.0)
    valor = (pd.to_numeric(df["valor_reclamado"], errors="coerce") / VALOR_REFERENCIA_RS).clip(0, 1).fillna(0.0)
    dias = (hoje - pd.to_datetime(df["data_aviso"], errors="coerce")).dt.days
    espera = (dias / ESPERA_REFERENCIA_DIAS).clip(0, 1).fillna(0.0)
    return (pesos["suspeita"] * suspeita + pesos["valor"] * valor + pesos["espera"] * espera).round(4)

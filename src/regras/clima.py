"""Regras climáticas compartilhadas pelo gerador sintético e pelo pipeline.

Valores de referência (calibráveis) definidos na spec, seção 4.3, e regra de duas fontes (D-015).
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd

LIMIAR_CHUVA_HORA_MM = 10.0
LIMIAR_RAJADA_MS = 15.0
LIMIAR_QUEDA_TEMP_C = 4.0
LIMIAR_CHUVA_DIA_ALAGAMENTO_MM = 50.0
RAIO_ESTACAO_KM = 30.0
JANELA_DIAS = 1  # D-1 a D+1

VARIAVEIS_POR_CAUSA: dict[str, tuple[str, ...]] = {
    "granizo": ("chuva_max_hora_mm", "rajada_max_ms"),
    "vendaval": ("rajada_max_ms",),
    "alagamento": ("chuva_mm",),
    "danos_eletricos": ("chuva_max_hora_mm", "rajada_max_ms"),
}


def _tem(valor) -> bool:
    return valor is not None and not (isinstance(valor, float) and math.isnan(valor)) and valor is not pd.NA


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def sinal_por_causa(causa: str, valores: dict[str, float | None]) -> bool | None:
    """True: há sinal compatível com a causa. False: há dado e nenhum sinal. None: falta dado ou o sinal é parcial.

    Sinal parcial (só parte das variáveis da causa acima do limiar) é inconclusivo, nunca contrário: a spec 4.3 só
    admite 'contraria' quando a estação válida não mostra nenhum sinal.
    """
    chuva_dia = valores.get("chuva_mm")
    chuva_hora = valores.get("chuva_max_hora_mm")
    rajada = valores.get("rajada_max_ms")
    if causa == "vendaval":
        return None if not _tem(rajada) else bool(rajada >= LIMIAR_RAJADA_MS)
    if causa == "alagamento":
        return None if not _tem(chuva_dia) else bool(chuva_dia >= LIMIAR_CHUVA_DIA_ALAGAMENTO_MM)
    if causa == "granizo":
        # O INMET não mede granizo: o sinal compatível é tempestade severa (chuva intensa e rajada forte no período).
        # O indicador horário `granizo_provavel` (com queda de temperatura) é mais estrito e fica como detalhe (D-018).
        if not (_tem(chuva_hora) and _tem(rajada)):
            return None
        acima = (chuva_hora >= LIMIAR_CHUVA_HORA_MM, rajada >= LIMIAR_RAJADA_MS)
        if all(acima):
            return True
        return None if any(acima) else False
    if causa == "danos_eletricos":
        medidos = [(v, lim) for v, lim in ((chuva_hora, LIMIAR_CHUVA_HORA_MM), (rajada, LIMIAR_RAJADA_MS)) if _tem(v)]
        if any(v >= lim for v, lim in medidos):
            return True
        return False if len(medidos) == 2 else None
    raise ValueError(f"causa desconhecida: {causa}")


def classificar_evidencia(sinal_inmet: bool | None, distancia_km: float | None, registro_defesa_civil: bool) -> tuple[str, str]:
    """Regra de duas fontes (D-015). Devolve (forca, fonte)."""
    perto = _tem(distancia_km) and distancia_km <= RAIO_ESTACAO_KM
    inmet_confirma = perto and sinal_inmet is True
    if registro_defesa_civil and inmet_confirma:
        return "forte", "ambas"
    if registro_defesa_civil:
        return "forte", "defesa_civil"
    if inmet_confirma:
        return "forte", "inmet"
    if perto and sinal_inmet is False:
        return "contraria", "inmet"
    return "fraca", "nenhuma"


def indexar_clima_por_data(clima_diario: pd.DataFrame) -> dict[date, pd.DataFrame]:
    return {d: g for d, g in clima_diario.groupby("data")}


def janela_clima(indice: dict[date, pd.DataFrame], data: date) -> pd.DataFrame:
    partes = [indice[d] for d in (data + timedelta(days=k) for k in range(-JANELA_DIAS, JANELA_DIAS + 1)) if d in indice]
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=["codigo_estacao", "data"])


def evidencia_inmet(lat: float, lon: float, causa: str, janela: pd.DataFrame, estacoes: pd.DataFrame) -> dict:
    """Para cada variável da causa, usa a estação VÁLIDA mais próxima na janela (máximo do período).

    Variáveis cuja estação válida mais próxima está a mais de RAIO_ESTACAO_KM contam como ausentes.
    `distancia_km` é a maior distância entre as variáveis dentro do raio; se nenhuma estiver no raio,
    é a menor distância encontrada (apenas para registro).
    """
    dist = {e.codigo_estacao: haversine_km(lat, lon, e.lat, e.lon) for e in estacoes.itertuples()}
    valores: dict[str, float | None] = {}
    usadas: dict[str, str] = {}
    for var in VARIAVEIS_POR_CAUSA[causa]:
        if var not in janela.columns:
            valores[var] = None
            continue
        por_estacao = janela.dropna(subset=[var]).groupby("codigo_estacao")[var].max()
        por_estacao = por_estacao[por_estacao.index.isin(list(dist))]
        if por_estacao.empty:
            valores[var] = None
            continue
        codigo = min(por_estacao.index, key=lambda c: dist[c])
        valores[var] = float(por_estacao[codigo])
        usadas[var] = codigo
    no_raio = {v: (valores[v] if v in usadas and dist[usadas[v]] <= RAIO_ESTACAO_KM else None) for v in valores}
    dist_no_raio = [dist[usadas[v]] for v in usadas if dist[usadas[v]] <= RAIO_ESTACAO_KM]
    todas = [dist[c] for c in usadas.values()]
    distancia = max(dist_no_raio) if dist_no_raio else (min(todas) if todas else None)
    return {"valores": valores, "estacoes": usadas, "distancia_km": distancia, "sinal": sinal_por_causa(causa, no_raio)}

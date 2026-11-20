"""Regras do aviso de sinistro usadas pelo pipeline (camada silver), em pandas puro.

`calcular_evidencia_grupo` roda dentro do pipeline via `applyInPandas`, um grupo por aviso, e nos testes locais,
que conferem o resultado contra o gabarito do gerador (paridade). Nada aqui lê o gabarito.
"""
from __future__ import annotations

import pandas as pd

from regras.clima import classificar_evidencia, clima_no_local, evidencia_inmet

COLUNAS_CLIMA = ["chuva_mm", "chuva_max_hora_mm", "rajada_max_ms", "queda_temp_max_c", "granizo_provavel"]
ESQUEMA_EVIDENCIA = ("id_aviso STRING, forca_evidencia_climatica STRING, fonte_evidencia STRING, distancia_estacao_km DOUBLE, "
                     "registro_defesa_civil BOOLEAN, chuva_mm DOUBLE, chuva_max_hora_mm DOUBLE, rajada_max_ms DOUBLE, "
                     "granizo_provavel BOOLEAN")


def calcular_evidencia_grupo(grupo: pd.DataFrame) -> pd.DataFrame:
    """Evidência climática de UM aviso (regra de duas fontes, D-015 e D-018).

    O grupo traz o aviso repetido em cada linha de clima das estações na janela D−1 a D+1. Sem clima na janela, vem
    uma única linha com `codigo_estacao` nulo, e o resultado é 'fraca' (ou 'forte' pela Defesa Civil).
    """
    a = grupo.iloc[0]
    janela = grupo[grupo["codigo_estacao"].notna()]
    # O grupo também traz lat/lon do aviso: as coordenadas da estação são só lat_estacao/lon_estacao.
    estacoes = (janela[["codigo_estacao", "lat_estacao", "lon_estacao"]].drop_duplicates("codigo_estacao")
                .rename(columns={"lat_estacao": "lat", "lon_estacao": "lon"}))
    janela = janela[["codigo_estacao", "data", *COLUNAS_CLIMA]]
    lat, lon = float(a["lat"]), float(a["lon"])
    ev = evidencia_inmet(lat, lon, a["causa_declarada"], janela, estacoes)
    dc = bool(a["registro_defesa_civil"]) if pd.notna(a["registro_defesa_civil"]) else False
    forca, fonte = classificar_evidencia(ev["sinal"], ev["distancia_km"], dc)
    return pd.DataFrame([{
        "id_aviso": a["id_aviso"], "forca_evidencia_climatica": forca, "fonte_evidencia": fonte,
        "distancia_estacao_km": ev["distancia_km"], "registro_defesa_civil": dc,
        **clima_no_local(lat, lon, janela, estacoes),
    }])

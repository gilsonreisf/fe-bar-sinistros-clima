from datetime import date

import numpy as np
import pandas as pd
import pytest

from regras.clima import (
    classificar_evidencia, evidencia_inmet, haversine_km, indexar_clima_por_data, janela_clima, sinal_por_causa,
)


def test_haversine_florianopolis_chapeco_aprox_405km():
    assert haversine_km(-27.5954, -48.5480, -27.1004, -52.6152) == pytest.approx(405, abs=20)


@pytest.mark.parametrize("causa,valores,esperado", [
    ("vendaval", {"rajada_max_ms": 16.0}, True),
    ("vendaval", {"rajada_max_ms": 9.0}, False),
    ("vendaval", {"rajada_max_ms": None}, None),
    ("granizo", {"chuva_max_hora_mm": 12.0, "rajada_max_ms": 15.0}, True),
    ("granizo", {"chuva_max_hora_mm": 12.0, "rajada_max_ms": 10.0}, None),  # sinal parcial: inconclusivo (revisão #5)
    ("granizo", {"chuva_max_hora_mm": 1.0, "rajada_max_ms": 16.0}, None),
    ("granizo", {"chuva_max_hora_mm": 1.0, "rajada_max_ms": 5.0}, False),
    ("granizo", {"chuva_max_hora_mm": 12.0, "rajada_max_ms": None}, None),
    ("alagamento", {"chuva_mm": 55.0}, True),
    ("alagamento", {"chuva_mm": 20.0}, False),
    ("danos_eletricos", {"chuva_max_hora_mm": None, "rajada_max_ms": 20.0}, True),
    ("danos_eletricos", {"chuva_max_hora_mm": None, "rajada_max_ms": 5.0}, None),
    ("danos_eletricos", {"chuva_max_hora_mm": 1.0, "rajada_max_ms": 5.0}, False),
])
def test_sinal_por_causa(causa, valores, esperado):
    assert sinal_por_causa(causa, valores) is esperado


@pytest.mark.parametrize("sinal,dist,dc,esperado", [
    (True, 10.0, True, ("forte", "ambas")),
    (None, None, True, ("forte", "defesa_civil")),
    (False, 10.0, True, ("forte", "defesa_civil")),
    (True, 10.0, False, ("forte", "inmet")),
    (False, 10.0, False, ("contraria", "inmet")),
    (True, 45.0, False, ("fraca", "nenhuma")),
    (False, 45.0, False, ("fraca", "nenhuma")),
    (None, 10.0, False, ("fraca", "nenhuma")),
])
def test_classificar_evidencia(sinal, dist, dc, esperado):
    assert classificar_evidencia(sinal, dist, dc) == esperado


@pytest.fixture
def estacoes():
    return pd.DataFrame([
        {"codigo_estacao": "A001", "nome": "PERTO", "lat": -27.0, "lon": -52.0},
        {"codigo_estacao": "A002", "nome": "LONGE", "lat": -28.0, "lon": -50.0},
    ])


def _clima(linhas):
    base = {"chuva_mm": np.nan, "chuva_max_hora_mm": np.nan, "rajada_max_ms": np.nan, "queda_temp_max_c": np.nan, "granizo_provavel": pd.NA}
    return pd.DataFrame([{**base, **l} for l in linhas])


def test_evidencia_usa_estacao_valida_mais_proxima_por_variavel(estacoes):
    clima = _clima([
        {"codigo_estacao": "A001", "data": date(2026, 9, 28), "chuva_max_hora_mm": 14.0},  # A001 sem rajada
        {"codigo_estacao": "A002", "data": date(2026, 9, 28), "rajada_max_ms": 20.0, "chuva_max_hora_mm": 3.0},
    ])
    janela = janela_clima(indexar_clima_por_data(clima), date(2026, 9, 28))
    ev = evidencia_inmet(-27.05, -52.0, "granizo", janela, estacoes)
    assert ev["estacoes"] == {"chuva_max_hora_mm": "A001", "rajada_max_ms": "A002"}
    assert ev["valores"]["rajada_max_ms"] == 20.0


def test_variavel_fora_do_raio_e_fraca(estacoes):
    """Foco de revisão 2: a rajada só existe em uma estação a mais de 30 km; o resultado não pode ser 'contraria'."""
    clima = _clima([
        {"codigo_estacao": "A001", "data": date(2026, 9, 28), "chuva_max_hora_mm": 1.0},
        {"codigo_estacao": "A002", "data": date(2026, 9, 28), "rajada_max_ms": 5.0},
    ])
    janela = janela_clima(indexar_clima_por_data(clima), date(2026, 9, 28))
    ev = evidencia_inmet(-27.05, -52.0, "granizo", janela, estacoes)
    assert ev["sinal"] is None
    assert classificar_evidencia(ev["sinal"], ev["distancia_km"], False) == ("fraca", "nenhuma")


def test_janela_inclui_d_menos_1_e_d_mais_1(estacoes):
    clima = _clima([
        {"codigo_estacao": "A001", "data": date(2026, 9, 27), "rajada_max_ms": 18.0},
        {"codigo_estacao": "A001", "data": date(2026, 9, 30), "rajada_max_ms": 30.0},  # fora da janela
    ])
    janela = janela_clima(indexar_clima_por_data(clima), date(2026, 9, 28))
    ev = evidencia_inmet(-27.05, -52.0, "vendaval", janela, estacoes)
    assert ev["valores"]["rajada_max_ms"] == 18.0
    assert ev["sinal"] is True
    assert ev["distancia_km"] < 30


def test_sinal_parcial_e_fraca_nao_contraria(estacoes):
    """Revisão #5 (spec 4.3): 'contraria' exige estação válida SEM NENHUM sinal; sinal parcial vira 'fraca'."""
    clima = _clima([{"codigo_estacao": "A001", "data": date(2026, 9, 28), "chuva_max_hora_mm": 14.0, "rajada_max_ms": 9.0}])
    janela = janela_clima(indexar_clima_por_data(clima), date(2026, 9, 28))
    ev = evidencia_inmet(-27.05, -52.0, "granizo", janela, estacoes)
    assert classificar_evidencia(ev["sinal"], ev["distancia_km"], False) == ("fraca", "nenhuma")

from datetime import date, timedelta

import pandas as pd
import pytest

from regras.clima import JANELA_DIAS, clima_no_local, registro_defesa_civil
from regras.sinistro import ESQUEMA_EVIDENCIA, calcular_evidencia_grupo


def _grupo_como_pipeline(ctx, aviso: dict) -> pd.DataFrame:
    """Reproduz o formato do grupo montado pelo pipeline (silver.evidencia_climatica): o aviso repetido em cada
    linha de clima das estações na janela D−1 a D+1, ou uma linha com codigo_estacao nulo se não houver clima."""
    data = date.fromisoformat(aviso["data_ocorrencia"])
    c = ctx.clima_diario
    jan = c[(c["data"] >= data - timedelta(days=JANELA_DIAS)) & (c["data"] <= data + timedelta(days=JANELA_DIAS))]
    est = ctx.estacoes.rename(columns={"lat": "lat_estacao", "lon": "lon_estacao"})[["codigo_estacao", "lat_estacao", "lon_estacao"]]
    jan = jan.merge(est, on="codigo_estacao")
    dc = registro_defesa_civil(ctx.defesa_civil, int(aviso["codigo_ibge"]), data) if ctx.defesa_civil is not None else False
    base = {k: aviso[k] for k in ("id_aviso", "codigo_ibge", "lat", "lon", "causa_declarada")}
    base |= {"data_ocorrencia": data, "registro_defesa_civil": dc}
    if jan.empty:
        return pd.DataFrame([base | {"codigo_estacao": None, "data": None, "lat_estacao": None, "lon_estacao": None,
                                     "chuva_mm": None, "chuva_max_hora_mm": None, "rajada_max_ms": None,
                                     "queda_temp_max_c": None, "granizo_provavel": None}])
    return jan.assign(**base)


def test_evidencia_do_pipeline_bate_com_o_gabarito(evento, mundo):
    """Foco de revisão 2: paridade exata entre a evidência do pipeline e a do gerador."""
    r, _, _ = evento
    ctx, _ = mundo
    gab = r.gabarito.set_index("id_aviso")
    for aviso in r.avisos.to_dict("records"):
        out = calcular_evidencia_grupo(_grupo_como_pipeline(ctx, aviso)).iloc[0]
        g = gab.loc[aviso["id_aviso"]]
        assert (out.forca_evidencia_climatica, out.fonte_evidencia) == (g.forca_evidencia_esperada, g.fonte_evidencia_esperada), aviso["id_aviso"]


def test_grupo_sem_estacao_e_fraca_ou_defesa_civil():
    """Foco de revisão 1: estação fora do ar não pode derrubar o pipeline nem virar 'contraria'."""
    linha = {"id_aviso": "AV-X", "codigo_ibge": 1, "lat": -27.0, "lon": -50.0, "data_ocorrencia": date(2026, 9, 28),
             "causa_declarada": "granizo", "codigo_estacao": None, "data": None, "lat_estacao": None, "lon_estacao": None,
             "chuva_mm": None, "chuva_max_hora_mm": None, "rajada_max_ms": None, "queda_temp_max_c": None,
             "granizo_provavel": None}
    sem_dc = calcular_evidencia_grupo(pd.DataFrame([linha | {"registro_defesa_civil": False}])).iloc[0]
    com_dc = calcular_evidencia_grupo(pd.DataFrame([linha | {"registro_defesa_civil": True}])).iloc[0]
    assert (sem_dc.forca_evidencia_climatica, sem_dc.fonte_evidencia) == ("fraca", "nenhuma")
    assert (com_dc.forca_evidencia_climatica, com_dc.fonte_evidencia) == ("forte", "defesa_civil")
    assert sem_dc.chuva_mm is None and sem_dc.distancia_estacao_km is None


def test_colunas_seguem_o_esquema_do_pipeline():
    linha = {"id_aviso": "AV-X", "codigo_ibge": 1, "lat": -27.0, "lon": -50.0, "data_ocorrencia": date(2026, 9, 28),
             "causa_declarada": "vendaval", "registro_defesa_civil": None, "codigo_estacao": "S", "data": date(2026, 9, 28),
             "lat_estacao": -27.01, "lon_estacao": -50.0, "chuva_mm": 3.0, "chuva_max_hora_mm": 1.0, "rajada_max_ms": 20.0,
             "queda_temp_max_c": 1.0, "granizo_provavel": False}
    out = calcular_evidencia_grupo(pd.DataFrame([linha]))
    assert list(out.columns) == [c.split()[0] for c in ESQUEMA_EVIDENCIA.split(", ")]
    assert out.iloc[0].forca_evidencia_climatica == "forte" and out.iloc[0].rajada_max_ms == 20.0


def test_clima_no_local_ignora_estacao_fora_do_raio():
    estacoes = pd.DataFrame([{"codigo_estacao": "LONGE", "lat": -28.0, "lon": -50.0}])
    janela = pd.DataFrame([{"codigo_estacao": "LONGE", "data": date(2026, 9, 28), "chuva_mm": 80.0,
                            "chuva_max_hora_mm": 20.0, "rajada_max_ms": 25.0, "granizo_provavel": True}])
    assert clima_no_local(-27.0, -50.0, janela, estacoes) == {
        "chuva_mm": None, "chuva_max_hora_mm": None, "rajada_max_ms": None, "granizo_provavel": None}


def test_distancia_usa_a_coordenada_da_estacao_e_nao_a_do_aviso():
    """Bug achado no lote 1: o grupo tem lat/lon do aviso; a estação não pode herdar essas coordenadas."""
    base = {"id_aviso": "AV-X", "codigo_ibge": 1, "lat": -27.0, "lon": -50.0, "data_ocorrencia": date(2026, 9, 28),
            "causa_declarada": "vendaval", "registro_defesa_civil": False, "data": date(2026, 9, 28),
            "chuva_mm": 1.0, "chuva_max_hora_mm": 0.5, "queda_temp_max_c": 0.0, "granizo_provavel": False}
    grupo = pd.DataFrame([
        base | {"codigo_estacao": "PERTO_SEM_SINAL", "lat_estacao": -27.2, "lon_estacao": -50.0, "rajada_max_ms": 5.0},   # ~22 km
        base | {"codigo_estacao": "LONGE_COM_SINAL", "lat_estacao": -28.0, "lon_estacao": -50.0, "rajada_max_ms": 25.0},  # ~111 km
    ])
    out = calcular_evidencia_grupo(grupo).iloc[0]
    assert out.distancia_estacao_km == pytest.approx(22.2, abs=0.5)
    assert out.forca_evidencia_climatica == "contraria" and out.rajada_max_ms == 5.0

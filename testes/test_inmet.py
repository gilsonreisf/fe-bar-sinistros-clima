import io
import zipfile
from datetime import date

import numpy as np

from dados_sinteticos.inmet import agregar_diario, ler_estacao_csv, ler_zip_uf

CAB = (
    "REGIAO:;S\nUF:;SC\nESTACAO:;TESTE\nCODIGO (WMO):;A999\nLATITUDE:;-27,10\nLONGITUDE:;-52,60\n"
    "ALTITUDE:;679\nDATA DE FUNDACAO:;01/01/08\n"
    "Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
    "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);VENTO, RAJADA MAXIMA (m/s);\n"
)


def _csv(linhas):
    return CAB + "\n".join(f"{d};{h:02d}00 UTC;{p};900;{t};{r};" for d, h, p, t, r in linhas) + "\n"


def test_le_metadados_e_numeros_com_virgula():
    est, h = ler_estacao_csv(_csv([("2026/09/28", 0, ",2", "25,5", "10,4")]))
    assert est == {"codigo_estacao": "A999", "nome": "TESTE", "uf": "SC", "lat": -27.10, "lon": -52.60}
    assert h.loc[0, "data"] == date(2026, 9, 28)
    assert h.loc[0, "hora_utc"] == 0
    assert h.loc[0, "chuva_mm"] == 0.2 and h.loc[0, "temp_c"] == 25.5 and h.loc[0, "rajada_ms"] == 10.4


def test_valores_ausentes_viram_nan():
    """Foco de revisão 1: vazio e -9999 são ausência, não zero."""
    _, h = ler_estacao_csv(_csv([("2026/09/28", 0, "", "-9999", ""), ("2026/09/28", 1, "-9999", "", "-9999")]))
    assert h[["chuva_mm", "temp_c", "rajada_ms"]].isna().all().all()


def test_agregado_diario_respeita_minimo_de_horas_validas():
    linhas = [("2026/09/28", hh, "1,0", "20", "5") for hh in range(24)]          # dia completo
    linhas += [("2026/09/29", hh, "1,0" if hh < 5 else "", "20", "") for hh in range(24)]  # 5 h de chuva, sem rajada
    _, h = ler_estacao_csv(_csv(linhas))
    d = agregar_diario(h).set_index("data")
    assert d.loc[date(2026, 9, 28), "chuva_mm"] == 24.0
    assert d.loc[date(2026, 9, 28), "rajada_max_ms"] == 5.0
    assert np.isnan(d.loc[date(2026, 9, 29), "chuva_mm"])
    assert np.isnan(d.loc[date(2026, 9, 29), "rajada_max_ms"])


def test_granizo_provavel_exige_chuva_rajada_e_queda_de_temperatura():
    linhas = [("2026/09/28", hh, "0", "25", "5") for hh in range(24)]
    linhas[15] = ("2026/09/28", 15, "12,0", "25", "16")
    linhas[16] = ("2026/09/28", 16, "3,0", "20", "8")  # queda de 5 °C em 1 h
    _, h = ler_estacao_csv(_csv(linhas))
    d = agregar_diario(h)
    assert bool(d.loc[0, "granizo_provavel"]) is True
    assert d.loc[0, "chuva_max_hora_mm"] == 12.0


def test_le_somente_estacoes_da_uf_no_zip(tmp_path):
    caminho = tmp_path / "2026.zip"
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("INMET_S_SC_A999_TESTE_01-01-2026_A_31-10-2026.CSV", _csv([("2026/09/28", 0, "1", "20", "5")]).encode("latin-1"))
        z.writestr("INMET_S_RS_A801_PORTO ALEGRE_01-01-2026_A_31-10-2026.CSV", _csv([("2026/09/28", 0, "1", "20", "5")]).encode("latin-1"))
    est, h = ler_zip_uf(caminho, "SC")
    assert list(est["codigo_estacao"]) == ["A999"]
    assert len(h) == 1

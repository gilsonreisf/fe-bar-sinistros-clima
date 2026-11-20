from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from dados_sinteticos.publicos import carregar_defesa_civil, registro_defesa_civil

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def municipios():
    nomes = pd.read_csv(RAIZ / "dados/publicos/defesa_civil_sc_2026.csv")["municipio"].unique()
    return pd.DataFrame({"codigo_ibge": range(1, len(nomes) + 1), "municipio": nomes, "lat": -27.0, "lon": -50.0})


def test_defesa_civil_carrega_com_pesos_e_codigos(municipios):
    dc = carregar_defesa_civil(RAIZ / "dados/publicos/defesa_civil_sc_2026.csv", municipios)
    assert dc["peso"].sum() == pytest.approx(1.0)
    assert dc["codigo_ibge"].notna().all()
    seara = dc[dc["municipio"] == "Seara"].iloc[0]
    zortea = dc[dc["municipio"] == "Zortéa"].iloc[0]
    assert seara["peso"] > zortea["peso"] > 0  # sem número publicado recebe peso mínimo


def test_municipio_inexistente_falha(municipios):
    with pytest.raises(ValueError, match="não encontrados"):
        carregar_defesa_civil(RAIZ / "dados/publicos/defesa_civil_sc_2026.csv", municipios[municipios["municipio"] != "Seara"])


def test_registro_considera_janela_de_um_dia(municipios):
    dc = carregar_defesa_civil(RAIZ / "dados/publicos/defesa_civil_sc_2026.csv", municipios)
    seara = int(dc[dc["municipio"] == "Seara"]["codigo_ibge"].iloc[0])
    assert registro_defesa_civil(dc, seara, date(2026, 9, 26))      # D-1 do início
    assert registro_defesa_civil(dc, seara, date(2026, 9, 30))      # D+1 do fim
    assert not registro_defesa_civil(dc, seara, date(2026, 9, 25))
    assert not registro_defesa_civil(dc, seara, date(2026, 8, 29))  # Seara não está no episódio 1

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from dados_sinteticos.cadastros import gerar_corretores, gerar_prestadores, nova_faker
from dados_sinteticos.precos import gerar_tabela_precos
from dados_sinteticos.sinistros import ContextoGeracao


@pytest.fixture
def mundo():
    """Uma estação (S) com dados completos; o município PERTO fica a ~6 km dela e o LONGE a ~110 km.
    Há sinal severo em 10 a 12/08; nos demais dias de agosto, nenhum sinal. A Defesa Civil registra LONGE de 20 a 22/08."""
    municipios = pd.DataFrame({"codigo_ibge": [1, 2], "municipio": ["PERTO", "LONGE"],
                               "lat": [-27.05, -28.0], "lon": [-52.0, -52.0]})
    estacoes = pd.DataFrame([{"codigo_estacao": "S", "nome": "S", "uf": "SC", "lat": -27.0, "lon": -52.0}])
    linhas = []
    for k in range(31):
        d = date(2026, 8, 1) + timedelta(days=k)
        severo = date(2026, 8, 10) <= d <= date(2026, 8, 12)
        linhas.append({"codigo_estacao": "S", "data": d, "horas_chuva": 24, "chuva_mm": 80.0 if severo else 2.0,
                       "chuva_max_hora_mm": 15.0 if severo else 0.5, "horas_rajada": 24,
                       "rajada_max_ms": 20.0 if severo else 6.0, "queda_temp_max_c": 5.0 if severo else 1.0,
                       "granizo_provavel": severo})
    clima = pd.DataFrame(linhas)
    clima["granizo_provavel"] = clima["granizo_provavel"].astype("boolean")
    dc = pd.DataFrame([{"episodio": "e", "data_inicio": date(2026, 8, 20), "data_fim": date(2026, 8, 22), "municipio": "LONGE",
                        "codigo_ibge": 2, "lat": -28.0, "lon": -52.0, "moradias_atingidas": 100, "fonte_url": "x", "peso": 1.0}])
    fk = nova_faker(7)
    ctx = ContextoGeracao(rng=np.random.default_rng(7), fk=fk, municipios=municipios, estacoes=estacoes,
                          clima_diario=clima, precos=gerar_tabela_precos(), prestadores=gerar_prestadores(fk, 50),
                          janela=(date(2026, 8, 1), date(2026, 8, 31)), defesa_civil=dc)
    return ctx, gerar_corretores(fk, 5)

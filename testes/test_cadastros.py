from datetime import date

import numpy as np
import pandas as pd
import pytest

from dados_sinteticos import config
from dados_sinteticos.cadastros import (
    criar_apolice_avulsa, gerar_apolices, gerar_corretores, gerar_segurados, nova_faker, pesos_carteira,
)


def _cpf_valido(cpf: str) -> bool:
    d = [int(c) for c in cpf if c.isdigit()]
    if len(d) != 11:
        return False
    for n in (9, 10):
        soma = sum(d[i] * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != d[n]:
            return False
    return True


@pytest.fixture
def base():
    rng = np.random.default_rng(1)
    fk = nova_faker(1)
    municipios = pd.DataFrame({"codigo_ibge": [1, 2], "municipio": ["A", "B"], "lat": [-27.0, -26.0], "lon": [-52.0, -49.0]})
    dc = pd.DataFrame({"codigo_ibge": [2], "peso": [1.0]})
    return rng, fk, municipios, dc


def test_pesos_carteira_somam_1_e_concentram_na_defesa_civil(base):
    _, _, municipios, dc = base
    p = pesos_carteira(municipios, dc, 0.4)
    assert p.sum() == pytest.approx(1.0)
    assert p.loc[2] == pytest.approx(0.2 + 0.6)


def test_segurados_tem_cpf_valido_e_municipio(base):
    rng, fk, municipios, dc = base
    s = gerar_segurados(fk, rng, municipios, pesos_carteira(municipios, dc, 0.4), 200)
    assert len(s) == 200 and s["id_segurado"].is_unique
    assert s["cpf"].map(_cpf_valido).all()
    assert set(s["codigo_ibge"]) <= {1, 2}


def test_apolices_vigencia_um_ano_e_incendio_sempre(base):
    rng, fk, municipios, dc = base
    s = gerar_segurados(fk, rng, municipios, pesos_carteira(municipios, dc, 0.4), 100)
    ap, cob = gerar_apolices(rng, s, gerar_corretores(fk, 5), 120, date(2025, 10, 1), date(2026, 7, 31))
    assert len(ap) == 120 and ap["id_apolice"].is_unique
    assert (ap["ramo"] == "empresarial").sum() == 20
    dias = (pd.to_datetime(ap["fim_vigencia"]) - pd.to_datetime(ap["inicio_vigencia"])).dt.days
    assert (dias == 365).all()
    assert set(cob.loc[cob["cobertura"] == "incendio", "id_apolice"]) == set(ap["id_apolice"])


def test_apolice_avulsa_forca_e_exclui_coberturas(base):
    rng, fk, municipios, _ = base
    seg = {"id_segurado": "SG-1", "codigo_ibge": 1, "municipio": "A", "lat": -27.0, "lon": -52.0}
    ap, cobs = criar_apolice_avulsa(rng, seg, "AP-X", date(2026, 9, 20), gerar_corretores(fk, 2),
                                    forcar=frozenset({"incendio", "alagamento"}), excluir=frozenset({"vendaval_granizo"}))
    tipos = {c["cobertura"] for c in cobs}
    assert {"incendio", "alagamento"} <= tipos and "vendaval_granizo" not in tipos
    assert ap["inicio_vigencia"] == "2026-09-20" and ap["fim_vigencia"] == "2027-09-20"


def test_pesos_carteira_usam_populacao_quando_disponivel(base):
    """Revisão #2 (spec 4.2): a parte não concentrada da carteira segue a população do IBGE."""
    _, _, municipios, dc = base
    p = pesos_carteira(municipios.assign(populacao=[300, 100]), dc, 0.4)
    assert p.loc[1] == pytest.approx(0.4 * 0.75)
    assert p.loc[2] == pytest.approx(0.4 * 0.25 + 0.6)

from collections import Counter
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from dados_sinteticos import config
from dados_sinteticos.cadastros import gerar_apolices, gerar_segurados, pesos_carteira
from dados_sinteticos.precos import gerar_tabela_precos
from dados_sinteticos.sinistros import gabarito, gerar_evento, gerar_historico, gerar_itens, sortear_padroes


def test_sortear_padroes_respeita_proporcoes_exatas():
    c = Counter(sortear_padroes(np.random.default_rng(1), 1000))
    assert c["legitimo_simples"] == 600 and c["orcamento_inflado"] == 40 and c["prestador_concentrado"] == 10
    assert sum(c.values()) == 1000


def test_itens_inflados_ficam_acima_da_referencia():
    itens = gerar_itens(np.random.default_rng(2), "granizo", 8000, gerar_tabela_precos(), fator_preco=config.FATOR_PRECO_INFLADO)
    assert all(i["valor_unitario"] >= 1.4 * i["preco_referencia"] - 0.01 for i in itens)


@pytest.mark.parametrize("padrao,decisao", [("sem_cobertura", "recusar"), ("sem_evento_climatico", "investigar"),
                                            ("orcamento_inflado", "pagar_parcial"), ("legitimo_simples", "pagar_integral")])
def test_gabarito_por_padrao(padrao, decisao):
    itens = [{"valor_total": 3000.0, "quantidade": 10, "preco_referencia": 200.0, "preexistente": False}]
    d, valor, motivo = gabarito(padrao, itens, franquia=1000.0, lmi=50_000.0)
    assert d == decisao and motivo
    if padrao == "orcamento_inflado":
        assert valor == 1000.0  # 10 × 200 − 1000 de franquia
    if padrao == "legitimo_simples":
        assert valor == 2000.0


def test_gabarito_limita_ao_lmi():
    d, valor, _ = gabarito("legitimo_complexo", [{"valor_total": 90_000.0, "quantidade": 1, "preco_referencia": 90_000.0,
                                                  "preexistente": False}], franquia=1000.0, lmi=50_000.0)
    assert (d, valor) == ("pagar_parcial", 50_000.0)


@pytest.fixture
def evento(mundo):
    ctx, corretores = mundo
    pesos = pesos_carteira(ctx.municipios, ctx.defesa_civil, 0.4)
    seg = gerar_segurados(ctx.fk, ctx.rng, ctx.municipios, pesos, 300)
    ap, cob = gerar_apolices(ctx.rng, seg, corretores, 350, date(2025, 10, 1), date(2026, 7, 31))
    return gerar_evento(ctx, seg, ap, cob, corretores, n=200, n_lotes=4), ap, cob


def test_evento_volumes_lotes_e_ids(evento):
    r, _, _ = evento
    assert len(r.avisos) == 200 and r.avisos["id_aviso"].is_unique
    assert sorted(r.avisos["lote"].unique()) == [1, 2, 3, 4]
    assert (r.avisos.sort_values("id_aviso")["data_aviso"].is_monotonic_increasing)
    assert set(r.gabarito["id_aviso"]) == set(r.avisos["id_aviso"])


def test_apolices_unicas_e_vigentes(evento):
    """Foco de revisão 3."""
    r, ap, _ = evento
    todas = pd.concat([ap, r.apolices_extra], ignore_index=True).set_index("id_apolice")
    assert r.avisos["id_apolice"].is_unique
    for a in r.avisos.itertuples():
        p = todas.loc[a.id_apolice]
        assert p.inicio_vigencia <= a.data_ocorrencia <= p.fim_vigencia


def test_padroes_tem_as_caracteristicas_esperadas(evento):
    r, ap, cob = evento
    av = r.avisos.set_index("id_aviso")
    gab = r.gabarito.set_index("id_aviso")
    todas_cob = pd.concat([cob, r.coberturas_extra], ignore_index=True)
    todas_ap = pd.concat([ap, r.apolices_extra], ignore_index=True).set_index("id_apolice")
    for id_aviso, g in gab.iterrows():
        a = av.loc[id_aviso]
        coberturas = set(todas_cob.loc[todas_cob["id_apolice"] == a.id_apolice, "cobertura"])
        if g.padrao == "sem_cobertura":
            assert config.CAUSA_COBERTURA[a.causa_declarada] not in coberturas
        elif g.padrao != "sem_evento_climatico":
            assert config.CAUSA_COBERTURA[a.causa_declarada] in coberturas
        if g.padrao == "apolice_recente":
            dias = (date.fromisoformat(a.data_ocorrencia) - date.fromisoformat(todas_ap.loc[a.id_apolice].inicio_vigencia)).days
            assert 1 <= dias <= 10
        if g.padrao == "prestador_concentrado":
            assert a.id_prestador in config.PRESTADORES_CONCENTRADOS
        if g.padrao == "dano_preexistente":
            assert "anterior ao evento" in a["_texto_laudo"]
            assert any(d.endswith("_laudo.pdf") for d in a.documentos)


def test_evidencia_esperada_por_padrao(evento):
    r, _, _ = evento
    g = r.gabarito
    sem_evento = g[g["padrao"] == "sem_evento_climatico"]
    assert (sem_evento["forca_evidencia_esperada"] == "contraria").mean() >= 0.8
    legit = g[g["padrao"].str.startswith("legitimo")]
    assert (legit["forca_evidencia_esperada"] == "forte").mean() >= 0.9


def test_historico_tem_rotulos_e_snapshot_da_apolice(mundo):
    ctx, _ = mundo
    hist, itens = gerar_historico(ctx, 150)
    assert len(hist) == 150 and hist["id_sinistro"].is_unique
    assert set(hist["decisao_final"]) <= {"pagar_integral", "pagar_parcial", "recusar", "investigar"}
    assert (hist.loc[hist["motivo_decisao"] == "sem_cobertura", "cobertura_contratada"] == False).all()  # noqa: E712
    assert (hist.loc[hist["motivo_decisao"] == "regular", "cobertura_contratada"] == True).all()  # noqa: E712
    assert set(itens["id_sinistro"]) <= set(hist["id_sinistro"])


def test_historico_regular_nunca_tem_evidencia_contraria():
    """Revisão #3: sinistro legítimo pago não pode nascer em local e data com evidência climática contrária."""
    from dados_sinteticos.cadastros import gerar_prestadores, nova_faker
    from dados_sinteticos.sinistros import ContextoGeracao

    municipios = pd.DataFrame({"codigo_ibge": [1, 2, 3], "municipio": ["PERTO_S", "PERTO_T", "LONGE"],
                               "lat": [-27.05, -26.05, -29.5], "lon": [-52.0, -50.0, -52.0]})
    estacoes = pd.DataFrame([{"codigo_estacao": "S", "nome": "S", "uf": "SC", "lat": -27.0, "lon": -52.0},
                             {"codigo_estacao": "T", "nome": "T", "uf": "SC", "lat": -26.0, "lon": -50.0}])
    linhas = []
    for k in range(31):
        d = date(2025, 8, 1) + timedelta(days=k)
        for est in ("S", "T"):  # só S tem sinal (10 a 12/08); T nunca tem
            severo = est == "S" and date(2025, 8, 10) <= d <= date(2025, 8, 12)
            linhas.append({"codigo_estacao": est, "data": d, "horas_chuva": 24, "chuva_mm": 80.0 if severo else 2.0,
                           "chuva_max_hora_mm": 15.0 if severo else 0.5, "horas_rajada": 24,
                           "rajada_max_ms": 20.0 if severo else 6.0, "queda_temp_max_c": 5.0 if severo else 1.0,
                           "granizo_provavel": severo})
    clima = pd.DataFrame(linhas)
    clima["granizo_provavel"] = clima["granizo_provavel"].astype("boolean")
    fk = nova_faker(11)
    ctx = ContextoGeracao(rng=np.random.default_rng(11), fk=fk, municipios=municipios, estacoes=estacoes,
                          clima_diario=clima, precos=gerar_tabela_precos(), prestadores=gerar_prestadores(fk, 20),
                          janela=(date(2025, 8, 1), date(2025, 8, 31)))
    hist, _ = gerar_historico(ctx, 300)
    regulares = hist[hist["motivo_decisao"] == "regular"]
    forcas = [ctx.evidencia(r.codigo_ibge, r.lat, r.lon, date.fromisoformat(r.data_ocorrencia), r.causa_declarada)[0]
              for r in regulares.itertuples()]
    assert len(forcas) > 100 and "contraria" not in forcas

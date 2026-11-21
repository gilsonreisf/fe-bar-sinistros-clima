import numpy as np
import pandas as pd
import pytest

from ml.treino import (LIMIAR_FAST_TRACK, contribuicoes, decidir_promocao, dividir_temporal, metricas, por_padrao,
                       treinar)
from regras.features import montar_features


def test_dividir_temporal_corta_por_data_aviso():
    df = pd.DataFrame({"data_aviso": pd.to_datetime(["2025-09-30", "2025-10-01", "2025-12-31"]).date})
    treino, teste = dividir_temporal(df)
    assert len(treino) == 1 and len(teste) == 2


def test_dividir_temporal_falha_se_um_lado_ficar_vazio():
    with pytest.raises(ValueError):
        dividir_temporal(pd.DataFrame({"data_aviso": pd.to_datetime(["2025-01-02"]).date}))


def test_metricas_topo_e_limiar():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0] * 10)
    score = np.where(y == 1, 0.9, 0.1)
    score[0] = 0.15  # um suspeito escaparia do bloqueio do fast track
    m = metricas(y, score)
    assert m["precisao_top10"] == 1.0 and m["recall_top10"] == pytest.approx(10 / 20)
    assert m["suspeitos_abaixo_limiar"] == pytest.approx(1 / 20) and m["legitimos_abaixo_limiar"] == 1.0
    assert 0.97 < m["auc"] <= 1.0 and m["n"] == 100 and m["n_suspeitos"] == 20


def test_metricas_com_prefixo():
    assert "teste_auc" in metricas(np.array([0, 1]), np.array([0.1, 0.9]), prefixo="teste_")


def test_por_padrao():
    t = por_padrao(pd.Series(["a", "a", "b"]), np.array([0.1, 0.9, 0.5]))
    a = t.set_index("padrao").loc["a"]
    assert a.n == 2 and a.pct_acima_limiar == 50.0 and LIMIAR_FAST_TRACK == 0.2


@pytest.mark.parametrize("novo, atual, esperado", [(0.9, None, "champion"), (0.91, 0.90, "champion"),
                                                     (0.90, 0.90, "challenger"), (0.80, 0.90, "challenger")])
def test_decidir_promocao(novo, atual, esperado):
    assert decidir_promocao(novo, atual) == esperado


def test_champion_com_outro_contrato_de_features_nao_e_comparavel():
    """Se a definição das features mudou, o AUC do champion no teste novo não é comparável: a versão nova assume."""
    assert decidir_promocao(0.80, 0.99, contrato_igual=False) == "champion"


def _dados(n=400, seed=0):
    rng = np.random.default_rng(seed)
    suspeito = rng.random(n) < 0.2
    df = pd.DataFrame({
        "valor_reclamado": rng.uniform(1000, 30000, n), "lmi": 100000.0,
        "desvio_preco_pct": np.where(suspeito, rng.uniform(0.4, 1.2, n), rng.uniform(-0.1, 0.15, n)),
        "dias_desde_contratacao": rng.integers(30, 330, n), "forca_evidencia_climatica": "forte",
        "cobertura_valida": True, "menciona_dano_anterior": False, "participacao_prestador_30d": 0.0005,
        "causa_declarada": "granizo", "ramo": "residencial"})
    return df, suspeito.astype(int)


def test_treinar_separa_sinal_claro_e_contribuicoes_somam_o_logito():
    df, y = _dados()
    X = montar_features(df)
    modelo = treinar(X, y)
    m = metricas(y, modelo.predict_proba(X)[:, 1])
    assert m["auc"] > 0.95
    c = contribuicoes(modelo.booster_, X)
    assert list(c.columns) == list(X.columns) + ["base"]
    logito = modelo.booster_.predict(X, raw_score=True)
    assert np.allclose(c.sum(axis=1).to_numpy(), logito)

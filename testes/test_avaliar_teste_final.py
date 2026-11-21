import numpy as np
import pandas as pd

from avaliar_teste_final import renderizar_teste_final, resumo_teste_final


def _df():
    rng = np.random.default_rng(0)
    n = 60
    padrao = ["legitimo_simples"] * 40 + ["orcamento_inflado"] * 10 + ["prestador_concentrado"] * 10
    suspeito = np.array([p != "legitimo_simples" for p in padrao])
    return pd.DataFrame({
        "id_aviso": [f"A{i}" for i in range(n)], "lote": [2] * 30 + [5] * 30, "padrao": padrao,
        "decisao_esperada": ["pagar_integral"] * 40 + ["pagar_parcial"] * 10 + ["investigar"] * 10,
        "valor_devido": 1000.0, "valor_sugerido": 1000.0, "valor_reclamado": 3000.0,
        "score_suspeita": np.where(suspeito, rng.uniform(0.3, 1, n), rng.uniform(0, 0.1, n)),
        "recomendacao_ia": ["pagar_integral"] * 40 + ["pagar_parcial"] * 10 + ["investigar"] * 10,
        "status_parecer": "ok", "fast_track": [True] * 40 + [False] * 20, "cobertura_valida": True,
        "forca_evidencia_climatica": "forte", "dias_desde_contratacao": 200.0, "menciona_dano_anterior": False,
        "desvio_preco_pct": np.where(np.array(padrao) == "orcamento_inflado", 0.8, 0.02)})


def test_resumo_do_teste_final():
    r = resumo_teste_final(_df())
    assert r["modelo"]["auc"] == 1.0 and r["parecer"]["recomendacao_correta"] == 1.0
    assert r["fast_track"]["no_fast_track"] == 40 and r["fast_track"]["suspeitos_no_fast_track"] == 0
    assert set(r["por_lote"]["lote"]) == {2, 5} and "prestador_concentrado_bloqueado" in r["por_lote"]
    assert r["regra"]["suspeitos_abaixo_limiar"] == 0.5  # a regra não pega o prestador concentrado


def test_render_do_teste_final():
    md = renderizar_teste_final("agora", [2, 5], resumo_teste_final(_df()))
    assert "| AUC | 1 |" in md and "Recomendação igual à do gabarito: **100.0%**" in md and "## Por lote" in md

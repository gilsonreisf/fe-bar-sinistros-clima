"""Fast track (spec 6.3 + D-020) e prioridade da fila (D-023)."""
import pandas as pd
import pytest

from regras.fast_track import BLOQUEANTES, PESOS_PRIORIDADE, avaliar_fast_track, prioridade


def _sinistro(**kw):
    base = {"valor_reclamado": 3000.0, "cobertura_valida": True, "forca_evidencia_climatica": "forte",
            "score_suspeita": 0.05, "recomendacao_ia": "pagar_integral", "status_parecer": "ok",
            "alertas_qualidade": ["sem_estacao_no_raio"], "flags_documento": []}
    return base | kw


def _avaliar(**kw):
    return avaliar_fast_track(pd.DataFrame([_sinistro(**kw)])).iloc[0]


def test_sinistro_simples_e_limpo_vai_para_o_fast_track():
    r = _avaliar()
    assert r.fast_track and r.bloqueios_fast_track == []  # sem_estacao_no_raio é só informativo (D-020)


@pytest.mark.parametrize("campo, valor, motivo", [
    ("valor_reclamado", 5000.01, "valor_acima_do_teto"),
    ("cobertura_valida", False, "sem_cobertura"),
    ("forca_evidencia_climatica", "fraca", "evidencia_nao_forte"),
    ("score_suspeita", 0.2, "score_suspeita"),
    ("recomendacao_ia", "pagar_parcial", "recomendacao_nao_integral"),
    ("status_parecer", "pendente", "parecer_nao_ok"),
    ("alertas_qualidade", ["fora_vigencia"], "fora_vigencia"),
    ("flags_documento", ["preco_nao_conferido"], "preco_nao_conferido"),
])
def test_cada_condicao_bloqueia_sozinha_com_o_motivo(campo, valor, motivo):
    r = _avaliar(**{campo: valor})
    assert not r.fast_track and motivo in r.bloqueios_fast_track, r.bloqueios_fast_track


@pytest.mark.parametrize("campo", ["valor_reclamado", "cobertura_valida", "forca_evidencia_climatica", "score_suspeita",
                                   "recomendacao_ia", "status_parecer"])
def test_dado_faltante_bloqueia(campo):
    assert not _avaliar(**{campo: None}).fast_track


def test_listas_nulas_nao_quebram_e_bloqueantes_conhecidos():
    assert _avaliar(alertas_qualidade=None, flags_documento=None).fast_track
    assert {"apolice_inexistente", "documento_ilegivel", "extracao_falhou", "documento_ausente"} <= set(BLOQUEANTES)
    assert "sem_estacao_no_raio" not in BLOQUEANTES


def test_prioridade_monotonica_e_limitada():
    hoje = pd.Timestamp("2026-09-30")
    df = pd.DataFrame({"score_suspeita": [0.1, 0.9, 0.1, 0.1, None], "valor_reclamado": [1000.0, 1000.0, 90000.0, 1000.0, None],
                       "data_aviso": pd.to_datetime(["2026-09-29", "2026-09-29", "2026-09-29", "2026-08-01", None])})
    p = prioridade(df, hoje=hoje)
    assert p.between(0, 1).all() and p[1] > p[0] and p[2] > p[0] and p[3] > p[0]
    assert p[4] == pytest.approx(PESOS_PRIORIDADE["suspeita"])  # sem dado: tratado como suspeita máxima, não como baixo


def test_pesos_precisam_somar_um():
    with pytest.raises(ValueError):
        prioridade(pd.DataFrame({"score_suspeita": [0.1], "valor_reclamado": [1.0], "data_aviso": [pd.Timestamp("2026-09-01")]}),
                   pesos={"suspeita": 0.5, "valor": 0.5, "espera": 0.5})

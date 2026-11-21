import numpy as np
import pandas as pd
import pytest

from regras.features import (CATEGORIAS, COLUNAS_ENTRADA, COLUNAS_PROIBIDAS, FEATURES, montar_features,
                             preparar_entrada, principais_fatores, rotulo_suspeito)


def _entrada(**kw):
    base = {"valor_reclamado": 4000.0, "lmi": 80000.0, "desvio_preco_pct": 0.05, "dias_desde_contratacao": 200,
            "forca_evidencia_climatica": "forte", "cobertura_valida": True, "menciona_dano_anterior": False,
            "participacao_prestador_30d": 0.0005, "causa_declarada": "granizo", "ramo": "residencial"}
    return pd.DataFrame([base | kw])


def test_rotulo_suspeito_so_legitimos_sao_zero():
    s = rotulo_suspeito(pd.Series(["legitimo_simples", "legitimo_complexo", "orcamento_inflado", "sem_cobertura"]))
    assert s.tolist() == [0, 0, 1, 1]


def test_rotulo_suspeito_recusa_padrao_nulo():
    with pytest.raises(ValueError):
        rotulo_suspeito(pd.Series(["legitimo_simples", None]))


def test_features_na_ordem_e_sem_colunas_proibidas():
    X = montar_features(_entrada())
    assert list(X.columns) == FEATURES
    assert not (set(X.columns) | set(COLUNAS_ENTRADA)) & COLUNAS_PROIBIDAS


def test_features_traduzem_evidencia_e_razoes():
    X = montar_features(pd.concat([_entrada(forca_evidencia_climatica=f) for f in ("contraria", "fraca", "forte", "outra")]))
    assert X["evidencia_climatica"].tolist()[:3] == [0.0, 1.0, 2.0] and np.isnan(X["evidencia_climatica"].iloc[3])
    assert X["razao_valor_lmi"].iloc[0] == pytest.approx(0.05)


def test_sem_cobertura_tem_lmi_nulo_e_razao_nula():
    X = montar_features(_entrada(cobertura_valida=False, lmi=None))
    assert X["cobertura_valida"].iloc[0] == 0.0 and np.isnan(X["razao_valor_lmi"].iloc[0])


def test_nulos_e_categoria_desconhecida_nao_quebram():
    X = montar_features(_entrada(menciona_dano_anterior=None, cobertura_valida=None, causa_declarada="incendio",
                                 participacao_prestador_30d=None, dias_desde_contratacao=None, lmi=0.0))
    assert X["menciona_dano_anterior"].iloc[0] == 0.0 and X["cobertura_valida"].iloc[0] == 0.0
    assert pd.isna(X["causa_declarada"].iloc[0]) and np.isnan(X["razao_valor_lmi"].iloc[0])
    assert list(X["causa_declarada"].cat.categories) == CATEGORIAS["causa_declarada"]


def test_coluna_de_entrada_ausente_falha_com_o_nome():
    with pytest.raises(KeyError, match="desvio_preco_pct"):
        montar_features(_entrada().drop(columns=["desvio_preco_pct"]))


def test_clima_bruto_so_quando_pedido():
    df = _entrada().assign(chuva_mm=12.0, chuva_max_hora_mm=8.0, rajada_max_ms=20.0, distancia_estacao_km=7.0)
    assert "rajada_max_ms" not in montar_features(df).columns
    assert montar_features(df, com_clima_bruto=True)["rajada_max_ms"].iloc[0] == 20.0


def _x(**kw):
    return montar_features(_entrada(**kw)).iloc[0]


def test_principais_fatores_so_os_que_aumentam_a_suspeita():
    nomes = list(FEATURES)
    contrib = np.zeros(len(nomes))
    contrib[nomes.index("desvio_preco_pct")] = 2.0
    contrib[nomes.index("dias_desde_contratacao")] = -1.0
    contrib[nomes.index("evidencia_climatica")] = 0.5
    fatores = principais_fatores(contrib, nomes, _x(desvio_preco_pct=0.8, forca_evidencia_climatica="contraria"))
    assert fatores == ["Preço acima da tabela de referência", "Evidência climática contrária ao evento declarado"]


def test_fator_so_aparece_se_o_valor_justifica():
    """Revisão #5: o SHAP positivo de uma feature com valor normal (ou nulo) não vira motivo para o regulador."""
    nomes = list(FEATURES)
    contrib = np.full(len(nomes), 1.0)
    normal = principais_fatores(contrib, nomes, _x(), k=10)
    assert normal == []  # valores típicos: nenhuma frase falsa
    sem_cobertura = principais_fatores(contrib, nomes, _x(cobertura_valida=False, lmi=None), k=10)
    assert "Causa sem cobertura contratada" in sem_cobertura
    assert not any("LMI" in f for f in sem_cobertura)  # LMI nulo não é "valor próximo do limite"
    atipico = principais_fatores(contrib, nomes, _x(participacao_prestador_30d=0.002, dias_desde_contratacao=6,
                                                    forca_evidencia_climatica="fraca", menciona_dano_anterior=True,
                                                    valor_reclamado=79000.0, lmi=80000.0), k=10)
    assert {"Prestador com concentração atípica de orçamentos", "Apólice contratada há menos de 30 dias",
            "Evidência climática fraca (sem dado no raio)", "Laudo menciona dano anterior ao evento",
            "Valor próximo do limite da cobertura (LMI)", "Valor reclamado alto"} <= set(atipico)


def test_contribuicao_pequena_nao_vira_fator():
    nomes = list(FEATURES)
    contrib = np.zeros(len(nomes))
    contrib[nomes.index("desvio_preco_pct")] = 0.01
    assert principais_fatores(contrib, nomes, _x(desvio_preco_pct=0.8)) == []


def test_decimal_do_spark_vira_float():
    from decimal import Decimal
    df = _entrada(participacao_prestador_30d=Decimal("0.000448"), valor_reclamado=Decimal("4000.00"))
    e = preparar_entrada(df)
    assert e["participacao_prestador_30d"].dtype == "float64" and e["valor_reclamado"].iloc[0] == 4000.0
    assert montar_features(df)["participacao_prestador_30d"].iloc[0] == pytest.approx(0.000448)


def test_booleano_anulavel_do_arrow_e_numpy():
    df = pd.concat([_entrada(), _entrada(), _entrada()], ignore_index=True)
    df["cobertura_valida"] = pd.array([True, None, False], dtype="boolean")
    df["menciona_dano_anterior"] = np.array([True, False, True])
    X = montar_features(df)
    assert X["cobertura_valida"].tolist() == [1.0, 0.0, 0.0] and X["menciona_dano_anterior"].tolist() == [1.0, 0.0, 1.0]


def test_preparar_entrada_seleciona_e_tipa_como_a_assinatura():
    df = _entrada(dias_desde_contratacao=200, extra="x").astype({"dias_desde_contratacao": "int64"})
    e = preparar_entrada(df)
    assert list(e.columns) == COLUNAS_ENTRADA and e["dias_desde_contratacao"].dtype == "float64"
    assert e["cobertura_valida"].dtype == object and e["causa_declarada"].iloc[0] == "granizo"

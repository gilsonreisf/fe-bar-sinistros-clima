from dados_sinteticos.precos import gerar_tabela_precos


def test_tabela_tem_210_itens_unicos_e_cobre_todas_as_causas():
    t = gerar_tabela_precos()
    assert len(t) == 210
    assert t["codigo_item"].is_unique
    for causa in ("granizo", "vendaval", "danos_eletricos", "alagamento"):
        assert t["causas"].str.split("|").apply(lambda cs: causa in cs).sum() >= 15
    assert (t["preco_referencia"] > 0).all()


def test_padrao_premium_mais_caro_que_economico():
    t = gerar_tabela_precos().set_index("codigo_item")
    assert t.loc["TEL-CER-PREMIUM", "preco_referencia"] > t.loc["TEL-CER-ECONOMICO", "preco_referencia"]

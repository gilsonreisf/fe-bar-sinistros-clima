import pytest

from ambiente import CAMADAS, carregar_ambiente


def test_padroes_sem_variaveis():
    amb = carregar_ambiente({})
    assert amb.catalogo == "sinistros_clima"
    assert [amb.schema(c) for c in CAMADAS] == ["landing", "bronze", "silver", "gold", "ml", "operacional"]
    assert amb.volume_arquivos == "/Volumes/sinistros_clima/landing/arquivos"
    assert amb.volume_restrito == "/Volumes/sinistros_clima/ml/restrito"


def test_catalogo_e_prefixo_vem_das_variaveis():
    amb = carregar_ambiente({"FE_BAR_CATALOGO": "outro_catalogo", "FE_BAR_PREFIXO_SCHEMA": "dev_"})
    assert amb.schema("bronze") == "dev_bronze"
    assert amb.volume_arquivos == "/Volumes/outro_catalogo/dev_landing/arquivos"
    assert amb.variaveis_sql() == {
        "catalogo": "outro_catalogo",
        "schema_landing": "dev_landing", "schema_bronze": "dev_bronze", "schema_silver": "dev_silver",
        "schema_gold": "dev_gold", "schema_ml": "dev_ml", "schema_operacional": "dev_operacional",
    }


def test_prefixo_vazio_equivale_a_sem_prefixo():
    assert carregar_ambiente({"FE_BAR_PREFIXO_SCHEMA": ""}).schema("gold") == "gold"


@pytest.mark.parametrize("variaveis", [
    {"FE_BAR_CATALOGO": "cat; DROP"},
    {"FE_BAR_CATALOGO": "Maiusculo"},
    {"FE_BAR_CATALOGO": ""},
    {"FE_BAR_PREFIXO_SCHEMA": "dev-"},
])
def test_nomes_invalidos_falham(variaveis):
    with pytest.raises(ValueError, match="inválido"):
        carregar_ambiente(variaveis)


def test_camada_desconhecida_falha():
    with pytest.raises(ValueError, match="camada"):
        carregar_ambiente({}).schema("platinum")

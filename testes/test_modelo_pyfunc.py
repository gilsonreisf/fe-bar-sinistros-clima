import json
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

import ml
import regras
from ml.treino import assinatura, treinar
from regras.features import COLUNAS_ENTRADA, FEATURES, montar_features, preparar_entrada
from test_treino import _dados


def _salvar(tmp_path: Path) -> str:
    df, y = _dados()
    modelo = treinar(montar_features(df), y)
    booster = tmp_path / "booster.txt"
    modelo.booster_.save_model(str(booster))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"features": FEATURES, "com_clima_bruto": False}))
    destino = tmp_path / "modelo"
    mlflow.pyfunc.save_model(
        path=str(destino), python_model=str(Path(ml.__file__).with_name("modelo_pyfunc.py")),
        artifacts={"booster": str(booster), "config": str(config)},
        code_paths=[str(Path(regras.__file__).parent)], signature=assinatura())
    return str(destino)


def test_modelo_salvo_carrega_e_pontua_entrada_com_nulos(tmp_path):
    carregado = mlflow.pyfunc.load_model(_salvar(tmp_path))
    entrada = pd.DataFrame({
        "valor_reclamado": [4000.0, 25000.0, 3000.0], "lmi": [80000.0, None, 50000.0],
        "desvio_preco_pct": [0.02, 0.9, None], "dias_desde_contratacao": [200.0, 5.0, None],
        "forca_evidencia_climatica": ["forte", "contraria", None], "cobertura_valida": [True, False, None],
        "menciona_dano_anterior": [False, True, None], "participacao_prestador_30d": [0.0005, None, 0.003],
        "causa_declarada": ["granizo", "vendaval", "incendio"], "ramo": ["residencial", "empresarial", None]})
    saida = carregado.predict(entrada[COLUNAS_ENTRADA])
    assert list(saida.columns) == ["score_suspeita", "fatores_suspeita"]
    assert saida["score_suspeita"].between(0, 1).all() and len(saida) == 3
    assert saida["score_suspeita"].iloc[1] > saida["score_suspeita"].iloc[0]
    assert "Preço acima da tabela de referência" in saida["fatores_suspeita"].iloc[1]
    # abaixo do limiar do fast track não há fator de suspeita a mostrar ao regulador
    assert saida["score_suspeita"].iloc[0] < 0.2 and saida["fatores_suspeita"].iloc[0] == ""


def test_modelo_aceita_dias_inteiros_como_vem_do_spark(tmp_path):
    """INT do Spark chega como int32 (conversão segura para double); int64 do pandas exige preparar_entrada."""
    carregado = mlflow.pyfunc.load_model(_salvar(tmp_path))
    df, _ = _dados(n=5)
    saida = carregado.predict(df.assign(dias_desde_contratacao=df["dias_desde_contratacao"].astype("int32"))[COLUNAS_ENTRADA])
    assert saida["score_suspeita"].notna().all() and np.isfinite(saida["score_suspeita"]).all()
    entrada64 = df.assign(dias_desde_contratacao=df["dias_desde_contratacao"].astype("int64"), extra=1)
    assert carregado.predict(preparar_entrada(entrada64))["score_suspeita"].notna().all()


def test_modelo_leva_as_regras_junto_e_nao_depende_do_wheel(tmp_path):
    """No serving e no spark_udf o wheel do projeto pode não estar instalado: features.py vai dentro do modelo."""
    destino = Path(_salvar(tmp_path))
    assert (destino / "code" / "regras" / "features.py").exists()
    assert (destino / "python_model.py").exists() or any(destino.rglob("modelo_pyfunc.py"))

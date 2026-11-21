"""Modelo MLflow do score de suspeita (models from code): booster LightGBM + o features.py do treino como artefato.

Entrada: as colunas de regras.features.COLUNAS_ENTRADA, como estão em silver.sinistros_enriquecidos (use
regras.features.preparar_entrada para tipar). Saída: score_suspeita (0 a 1) e fatores_suspeita (até 3 fatores que
mais aumentam a suspeita, em português; vazio quando o score fica abaixo do limiar do fast track).

O features.py é carregado POR CAMINHO, com nome de módulo único (revisão #2): com code_paths, um processo que já
importou `regras` (notebook, pipeline) usaria o código do processo, e não o do modelo, sem nenhum aviso.
"""
import importlib.util
import json
import uuid

import mlflow
import pandas as pd
from mlflow.pyfunc import PythonModel


def carregar_features(caminho: str):
    spec = importlib.util.spec_from_file_location(f"modelo_suspeita_features_{uuid.uuid4().hex}", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class ModeloSuspeita(PythonModel):
    def load_context(self, context):
        import lightgbm as lgb

        self.booster = lgb.Booster(model_file=context.artifacts["booster"])
        with open(context.artifacts["config"], encoding="utf-8") as f:
            self.config = json.load(f)
        self.features = carregar_features(context.artifacts["features"])

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        f = self.features
        X = f.montar_features(model_input, com_clima_bruto=self.config["com_clima_bruto"])[self.config["features"]]
        score = self.booster.predict(X)
        contrib = self.booster.predict(X, pred_contrib=True)[:, :-1]
        nomes = list(X.columns)
        fatores = []
        for i, s in enumerate(score):
            if s < f.LIMIAR_FAST_TRACK:
                fatores.append("")
                continue
            lista = f.principais_fatores(contrib[i], nomes, X.iloc[i])
            fatores.append("; ".join(lista) if lista else f.FATOR_COMBINADO)
        return pd.DataFrame({"score_suspeita": score.astype(float), "fatores_suspeita": fatores})


mlflow.models.set_model(ModeloSuspeita())

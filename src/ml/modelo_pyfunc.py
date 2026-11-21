"""Modelo MLflow do score de suspeita (models from code): booster LightGBM + features compartilhadas (regras).

Entrada: as colunas de regras.features.COLUNAS_ENTRADA, como estão em silver.sinistros_enriquecidos.
Saída: score_suspeita (0 a 1) e fatores_suspeita (até 3 fatores que mais aumentam a suspeita, em português).
"""
import json

import mlflow
import pandas as pd
from mlflow.pyfunc import PythonModel


class ModeloSuspeita(PythonModel):
    def load_context(self, context):
        import lightgbm as lgb

        self.booster = lgb.Booster(model_file=context.artifacts["booster"])
        with open(context.artifacts["config"], encoding="utf-8") as f:
            self.config = json.load(f)

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        from regras.features import montar_features, principais_fatores

        X = montar_features(model_input, com_clima_bruto=self.config["com_clima_bruto"])[self.config["features"]]
        score = self.booster.predict(X)
        contrib = self.booster.predict(X, pred_contrib=True)[:, :-1]
        nomes = list(X.columns)
        fatores = ["; ".join(principais_fatores(linha, nomes)) for linha in contrib]
        return pd.DataFrame({"score_suspeita": score.astype(float), "fatores_suspeita": fatores})


mlflow.models.set_model(ModeloSuspeita())

"""Modelo MLflow do parecer prévio (models from code), servido no endpoint e usado pelo app ("Reanalisar com IA").

Entrada: `entrada_json` (de silver.entrada_parecer) e, opcionais, `score_suspeita` e `fatores_suspeita` (modelo de
suspeita). Saída: o parecer validado; listas em JSON (texto), para o ai_query e o app.
O template do prompt vai congelado no artefato `config` (D-022): o endpoint não depende de ler o Prompt Registry.
"""
import json

import mlflow
import pandas as pd
from mlflow.pyfunc import PythonModel


def assinatura_parecer():
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    entrada = Schema([ColSpec("string", "entrada_json"), ColSpec("double", "score_suspeita", required=False),
                      ColSpec("string", "fatores_suspeita", required=False)])
    saida = Schema([ColSpec("string", "recomendacao"), ColSpec("double", "valor_sugerido"),
                    ColSpec("string", "motivos"), ColSpec("string", "clausulas"), ColSpec("string", "itens_excluidos"),
                    ColSpec("double", "confianca"), ColSpec("string", "status_parecer"),
                    ColSpec("string", "versao_prompt"), ColSpec("string", "trace_id"), ColSpec("string", "erros")])
    return ModelSignature(inputs=entrada, outputs=saida)


class ParecerSinistro(PythonModel):
    def load_context(self, context):
        import parecer.gerar as gerar

        with open(context.artifacts["config"], encoding="utf-8") as f:
            self.config = json.load(f)
        self.chamar = gerar.chamar_llm_databricks(self.config["endpoint_llm"])

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        from parecer.gerar import gerar_parecer, juntar_score

        linhas = []
        for registro in model_input.to_dict("records"):
            entrada = juntar_score(json.loads(registro["entrada_json"]), registro.get("score_suspeita"),
                                   registro.get("fatores_suspeita"))
            p = gerar_parecer(entrada, self.config["template"], self.chamar, self.config["versao_prompt"])
            linhas.append({
                "recomendacao": p["recomendacao"], "valor_sugerido": float(p["valor_sugerido"]),
                "motivos": json.dumps(p["motivos"], ensure_ascii=False),
                "clausulas": json.dumps(p["clausulas"], ensure_ascii=False),
                "itens_excluidos": json.dumps(p["itens_excluidos"], ensure_ascii=False),
                "confianca": float(p["confianca"]), "status_parecer": p["status_parecer"],
                "versao_prompt": p["versao_prompt"], "trace_id": p["trace_id"] or "",
                "erros": json.dumps(p["erros"], ensure_ascii=False)})
        return pd.DataFrame(linhas)


mlflow.models.set_model(ParecerSinistro())

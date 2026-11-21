"""Endpoint do parecer no Model Serving: CPU Small com scale-to-zero, tracing no experimento e AI Gateway (inference
table e usage tracking). Publicado pelo job de avaliação depois do portão de qualidade (D-022).
"""
from __future__ import annotations

from collections.abc import Callable

API = "/api/2.0/serving-endpoints"


def config_endpoint(modelo: str, versao: int | str, experimento_id: str, catalogo: str, schema: str,
                    prefixo_tabela: str = "parecer") -> dict:
    return {
        "config": {"served_entities": [{
            "name": "parecer", "entity_name": modelo, "entity_version": str(versao),
            "workload_size": "Small", "scale_to_zero_enabled": True,
            # traces do endpoint vão para o experimento do parecer (MLflow 3)
            "environment_vars": {"ENABLE_MLFLOW_TRACING": "true", "MLFLOW_EXPERIMENT_ID": str(experimento_id)},
        }]},
        "ai_gateway": {
            "inference_table_config": {"enabled": True, "catalog_name": catalogo, "schema_name": schema,
                                       "table_name_prefix": prefixo_tabela},
            "usage_tracking_config": {"enabled": True},
        },
        "tags": [{"key": "projeto", "value": "sinistros_clima"}, {"key": "componente", "value": "parecer"}],
    }


def publicar_endpoint(api: Callable[..., dict], nome: str, corpo: dict) -> str:
    """Cria o endpoint ou atualiza a versão servida e o AI Gateway (idempotente). `api(metodo, caminho, corpo)`."""
    from databricks.sdk.errors import NotFound

    try:
        api("GET", f"{API}/{nome}")
    except NotFound:
        api("POST", API, {"name": nome, **corpo})
        return "criado"
    api("PUT", f"{API}/{nome}/config", corpo["config"])
    api("PUT", f"{API}/{nome}/ai-gateway", corpo["ai_gateway"])
    return "atualizado"


def api_do_workspace(w) -> Callable[..., dict]:
    """Adaptador do WorkspaceClient para `publicar_endpoint`."""
    def api(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
        return w.api_client.do(metodo, caminho, body=corpo)
    return api

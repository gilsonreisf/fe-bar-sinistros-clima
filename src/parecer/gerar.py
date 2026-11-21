"""Geração do parecer prévio: prompt → LLM → validação (com nova tentativa) → valor calculado em código.

Usado igual pela avaliação (notebook), pelo modelo servido (endpoint) e pelo gold. Cada etapa vira um span de trace do
MLflow. Nenhuma falha propaga: sem LLM o parecer fica `pendente`; com JSON inválido, `invalido` (spec 10.3).
"""
from __future__ import annotations

import json
from collections.abc import Callable

import mlflow

from parecer.clausulas import texto_clausulas
from parecer.esquema import parecer_invalido, parecer_pendente, validar_parecer
from parecer.valor import calcular_valor, valores_de_referencia

LLM_PADRAO = "databricks-claude-sonnet-5-5"  # D-017: o Claude Sonnet mais recente do workspace


def renderizar_prompt(template: str, entrada: dict) -> str:
    completa = {**entrada, "valores_calculados": valores_de_referencia(entrada)}
    return (template.replace("{{clausulas}}", texto_clausulas())
            .replace("{{entrada}}", json.dumps(completa, ensure_ascii=False, indent=1, default=str)))


@mlflow.trace(name="gerar_parecer", span_type="CHAIN")
def gerar_parecer(entrada: dict, template: str, chamar_llm: Callable[[str], str], versao_prompt: str,
                  tentativas: int = 2) -> dict:
    prompt = renderizar_prompt(template, entrada)
    erros: list[str] = []
    parecer, status = None, "invalido"
    try:
        for tentativa in range(1, tentativas + 1):
            mensagem = prompt if tentativa == 1 else (
                f"{prompt}\n\nSua resposta anterior foi recusada pela validação ({'; '.join(erros[-3:])}). "
                "Responda somente com o objeto JSON pedido.")
            with mlflow.start_span(name=f"llm_tentativa_{tentativa}", span_type="LLM") as span:
                span.set_inputs({"prompt": mensagem})
                texto = chamar_llm(mensagem)
                span.set_outputs({"resposta": texto})
            with mlflow.start_span(name="validar_json", span_type="PARSER") as span:
                parecer, mensagens = validar_parecer(texto)
                span.set_outputs({"valido": parecer is not None, "mensagens": mensagens})
            if parecer is not None:
                status, erros = "ok", mensagens  # avisos (ex.: cláusula desconhecida removida)
                break
            erros += mensagens
    except Exception as e:  # LLM indisponível, endpoint frio, cota: nunca derruba o lote
        parecer, status, erros = None, "pendente", [f"{type(e).__name__}: {e}"]
    if parecer is None:
        parecer = parecer_pendente() if status == "pendente" else parecer_invalido()
    with mlflow.start_span(name="calcular_valor", span_type="TOOL") as span:
        valor = 0.0 if parecer["recomendacao"] == "recusar" else calcular_valor(
            entrada, parecer["base_valor"], parecer["itens_excluidos"])
        span.set_inputs({"base_valor": parecer["base_valor"], "itens_excluidos": parecer["itens_excluidos"]})
        span.set_outputs({"valor_sugerido": valor})
    return {**parecer, "valor_sugerido": valor, "status_parecer": status, "versao_prompt": str(versao_prompt),
            "erros": erros, "trace_id": mlflow.get_active_trace_id()}


def texto_da_resposta(content) -> str:
    """Texto da mensagem do LLM. Modelos com raciocínio (Claude 5.5 no FMAPI) devolvem uma lista de partes
    (`reasoning` + `text`); só as partes de texto valem."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    partes = []
    for parte in content:
        tipo = parte.get("type") if isinstance(parte, dict) else getattr(parte, "type", None)
        texto = parte.get("text") if isinstance(parte, dict) else getattr(parte, "text", None)
        if tipo == "text" and texto:
            partes.append(texto)
    return "".join(partes)


def chamar_llm_databricks(endpoint: str = LLM_PADRAO, max_tokens: int = 1500, cliente=None) -> Callable[[str], str]:
    """Chamada ao Foundation Model API pelo Databricks SDK: no notebook usa a identidade do job; no endpoint, o
    passthrough declarado em `resources` do modelo (D-022). Sem `temperature`: o modelo não aceita o parâmetro."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

    w = cliente or WorkspaceClient()

    def chamar(prompt: str) -> str:
        r = w.serving_endpoints.query(name=endpoint, max_tokens=max_tokens,
                                      messages=[ChatMessage(role=ChatMessageRole.USER, content=prompt)])
        return texto_da_resposta(r.choices[0].message.content)

    return chamar

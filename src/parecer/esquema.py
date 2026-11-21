"""Esquema do parecer prévio e validação da resposta do LLM (spec 6.2 e 10.3).

O modelo não aceita saída estruturada nativa (D-022): o JSON vem no texto e é validado aqui. Resposta inválida não
vira parecer: depois da nova tentativa, o sinistro vai ao regulador como `investigar`.
"""
from __future__ import annotations

import json
import re

from parecer.clausulas import CLAUSULAS

RECOMENDACOES = ("pagar_integral", "pagar_parcial", "recusar", "investigar")
BASES_VALOR = ("reclamado", "tabela_referencia", "itens_validos", "zero")
_CERCA = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def extrair_json(texto: str) -> dict:
    """O primeiro objeto JSON do texto (aceita cerca ```json e texto antes ou depois)."""
    if not isinstance(texto, str):
        raise ValueError("resposta vazia")
    m = _CERCA.search(texto)
    bruto = m.group(1) if m else texto[texto.find("{"): texto.rfind("}") + 1] if "{" in texto else ""
    if not bruto:
        raise ValueError("resposta sem JSON")
    obj = json.loads(bruto)
    if not isinstance(obj, dict):
        raise ValueError("o JSON não é um objeto")
    return obj


def validar_parecer(texto: str) -> tuple[dict | None, list[str]]:
    """(parecer, avisos) se a resposta é válida; (None, erros) se não."""
    try:
        obj = extrair_json(texto)
    except (ValueError, json.JSONDecodeError) as e:
        return None, [f"JSON inválido: {e}"]
    erros, avisos = [], []
    recomendacao = obj.get("recomendacao")
    if recomendacao not in RECOMENDACOES:
        erros.append(f"recomendacao inválida: {recomendacao!r}")
    base = obj.get("base_valor")
    if base not in BASES_VALOR:
        erros.append(f"base_valor inválida: {base!r}")
    motivos = obj.get("motivos")
    if not isinstance(motivos, list) or not [m for m in motivos if isinstance(m, str) and m.strip()]:
        erros.append("motivos ausentes ou vazios")
    excluidos = obj.get("itens_excluidos") or []
    if not isinstance(excluidos, list) or not all(isinstance(i, str) for i in excluidos):
        erros.append("itens_excluidos deve ser uma lista de textos")
        excluidos = []
    # recomendação e base do valor precisam combinar: "integral" com valor reduzido ou "parcial" com valor zero seriam
    # um parecer contraditório, e o integral é condição do fast track (revisão das fases 4 a 8, #18)
    combina = {"pagar_integral": ("reclamado",)}  # a recusa já sai com valor zero pelo código, seja qual for a base
    if recomendacao in combina and base in BASES_VALOR and base not in combina[recomendacao]:
        erros.append(f"base_valor {base!r} não combina com a recomendação {recomendacao!r}")
    if recomendacao == "pagar_parcial" and base == "zero":
        erros.append("pagar_parcial com base_valor = zero")
    if base == "itens_validos" and not excluidos:
        erros.append("itens_excluidos vazio com base_valor = itens_validos")
    confianca = obj.get("confianca")
    if isinstance(confianca, bool) or not isinstance(confianca, (int, float)) or not 0 <= confianca <= 1:
        erros.append(f"confianca deve ser um número de 0 a 1: {confianca!r}")
    clausulas = obj.get("clausulas") or []
    if not isinstance(clausulas, list):
        erros.append("clausulas deve ser uma lista")
        clausulas = []
    if erros:
        return None, erros
    conhecidas = [c for c in clausulas if c in CLAUSULAS]
    avisos += [f"cláusula desconhecida removida: {c}" for c in clausulas if c not in CLAUSULAS]
    return {"recomendacao": recomendacao, "base_valor": base, "itens_excluidos": excluidos,
            "motivos": [m.strip() for m in motivos if isinstance(m, str) and m.strip()],
            "clausulas": conhecidas, "confianca": float(confianca)}, avisos


def _encaminhar(motivo: str) -> dict:
    return {"recomendacao": "investigar", "base_valor": "zero", "itens_excluidos": [], "motivos": [motivo],
            "clausulas": [], "confianca": 0.0}


def parecer_invalido() -> dict:
    return _encaminhar("Parecer automático inválido; o sinistro segue para análise do regulador.")


def parecer_pendente() -> dict:
    return _encaminhar("Parecer automático indisponível no momento; o sinistro segue para o regulador e será reanalisado.")

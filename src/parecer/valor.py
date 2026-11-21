"""Valor da indenização calculado em código (D-022): o LLM escolhe a base, o código aplica franquia, LMI e itens.

Regras (as mesmas do gabarito do gerador): líquido = min(max(valor − franquia, 0), LMI); sem LMI informado, não há
teto; item sem par na tabela de referência entra pelo valor do orçamento.
"""
from __future__ import annotations

import math
import unicodedata


def _num(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def _liquido(valor: float, franquia: float, lmi: float | None) -> float:
    v = max(0.0, valor - franquia)
    return round(min(v, lmi) if lmi is not None else v, 2)


def _contexto(entrada: dict) -> tuple[float, float, float | None, list[dict]]:
    aviso, apolice, docs = (entrada.get(k) or {} for k in ("aviso", "apolice", "documentos"))
    reclamado = _num(aviso.get("valor_reclamado")) or 0.0
    franquia = _num(apolice.get("franquia")) or 0.0
    lmi = _num(apolice.get("lmi"))
    itens = [i for i in (docs.get("itens") or []) if isinstance(i, dict)]
    return reclamado, franquia, lmi, itens


def _total_item(item: dict) -> float:
    total = _num(item.get("valor_total"))
    if total is None:
        total = (_num(item.get("quantidade")) or 0.0) * (_num(item.get("valor_unitario")) or 0.0)
    return total


def _nome_base(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split(" (")[0].split())


def _excluido(item: dict, excluidos: list[str]) -> bool:
    nome = _nome_base(item.get("descricao", ""))
    return bool(nome) and any(e and (nome == e or nome.startswith(e) or e.startswith(nome))
                              for e in (_nome_base(x) for x in excluidos))


def valores_de_referencia(entrada: dict) -> dict:
    reclamado, franquia, lmi, itens = _contexto(entrada)
    tabela = reclamado
    if itens:
        tabela = sum((_num(i.get("quantidade")) or 0.0) * _num(i.get("preco_referencia"))
                     if _num(i.get("preco_referencia")) is not None else _total_item(i) for i in itens)
    return {"valor_liquido_reclamado": _liquido(reclamado, franquia, lmi),
            "valor_liquido_tabela": _liquido(tabela, franquia, lmi),
            "excede_lmi": lmi is not None and reclamado - franquia > lmi}


def calcular_valor(entrada: dict, base_valor: str, itens_excluidos: list[str]) -> float:
    reclamado, franquia, lmi, itens = _contexto(entrada)
    if base_valor == "zero":
        return 0.0
    if base_valor == "tabela_referencia":
        return valores_de_referencia(entrada)["valor_liquido_tabela"]
    if base_valor == "itens_validos" and itens:
        return _liquido(sum(_total_item(i) for i in itens if not _excluido(i, itens_excluidos)), franquia, lmi)
    return _liquido(reclamado, franquia, lmi)

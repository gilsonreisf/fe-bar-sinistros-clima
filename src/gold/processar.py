"""Processamento incremental do gold: quem analisar, pareceres em paralelo e as linhas da tabela analisada.

Invariantes (foco de revisão da fase 5): um parecer `ok` nunca é pago de novo; falha do LLM vira `pendente` e é
tentada de novo nas próximas execuções, até `max_tentativas`; nenhum erro derruba o lote.
"""
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from gold.visoes import COLUNAS_GOLD
from parecer.esquema import parecer_pendente
from regras.fast_track import PESOS_PRIORIDADE, avaliar_fast_track, prioridade


def selecionar_para_analise(silver: pd.DataFrame, gold: pd.DataFrame, max_tentativas: int = 3) -> list[str]:
    """Avisos novos, mais os de parecer não `ok` com menos de `max_tentativas`, na ordem da silver."""
    status = gold.set_index("id_aviso")[["status_parecer", "tentativas_parecer"]].to_dict("index") if len(gold) else {}
    escolhidos = []
    for id_aviso in silver["id_aviso"]:
        g = status.get(id_aviso)
        if g is None or (g["status_parecer"] != "ok" and int(g["tentativas_parecer"] or 0) < max_tentativas):
            escolhidos.append(id_aviso)
    return escolhidos


def gerar_pareceres(entradas: list[tuple[str, dict]], gerar: Callable[[dict], dict], paralelo: int = 8) -> dict[str, dict]:
    def um(item):
        id_aviso, entrada = item
        try:
            return id_aviso, gerar(entrada)
        except Exception as e:  # noqa: BLE001 (nenhuma falha derruba o lote: vira pendente e é tentada de novo)
            return id_aviso, {**parecer_pendente(), "valor_sugerido": 0.0, "status_parecer": "pendente",
                              "versao_prompt": "", "trace_id": None, "erros": [f"{type(e).__name__}: {e}"]}

    with ThreadPoolExecutor(max_workers=max(1, paralelo)) as pool:
        return dict(pool.map(um, entradas))


def linhas_gold(base: pd.DataFrame, scores: pd.DataFrame, pareceres: dict[str, dict], llm: str, versao_modelo: str,
                agora: pd.Timestamp, tentativas_anteriores: dict[str, int], pesos: dict[str, float] = PESOS_PRIORIDADE,
                hoje: pd.Timestamp | None = None) -> pd.DataFrame:
    """Uma linha por aviso, nas colunas de gold.sinistros_analisados (score + parecer + fast track + prioridade)."""
    if set(pesos) != {"suspeita", "valor", "espera"} or abs(sum(pesos.values()) - 1) > 1e-9:
        raise ValueError(f"os pesos precisam ter suspeita, valor e espera e somar 1: {pesos}")
    g = base.copy()
    g["score_suspeita"] = scores["score_suspeita"].to_numpy()
    g["fatores_suspeita"] = scores["fatores_suspeita"].to_numpy()
    p = [pareceres[i] for i in g["id_aviso"]]
    g["recomendacao_ia"] = [x["recomendacao"] for x in p]
    g["valor_sugerido"] = [float(x["valor_sugerido"]) for x in p]
    for coluna, chave in (("motivos", "motivos"), ("clausulas", "clausulas"), ("itens_excluidos", "itens_excluidos"),
                          ("erros_parecer", "erros")):
        g[coluna] = [list(x.get(chave) or []) for x in p]
    g["confianca"] = [float(x.get("confianca") or 0.0) for x in p]
    g["status_parecer"] = [x["status_parecer"] for x in p]
    g["versao_prompt"] = [str(x.get("versao_prompt") or "") for x in p]
    g["trace_id"] = [x.get("trace_id") for x in p]
    g["tentativas_parecer"] = [int(tentativas_anteriores.get(i, 0)) + 1 for i in g["id_aviso"]]
    g["llm"], g["versao_modelo"], g["analisado_em"] = llm, str(versao_modelo), agora
    g = pd.concat([g, avaliar_fast_track(g)], axis=1)
    g["prioridade"] = prioridade(g, pesos=pesos, hoje=hoje)
    return g[COLUNAS_GOLD]

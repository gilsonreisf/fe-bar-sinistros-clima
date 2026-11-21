"""Teste final honesto (D-021/D-023): lotes do evento que nunca foram vistos no treino nem na avaliação do parecer.

Mede, no gold produzido pelo job do evento:
- o score contra a linha de base de regras (AUC, escape, vazamento no fast track);
- o parecer (recomendação correta e valor a ±10%, por padrão);
- o fast track (taxa, suspeitos liberados e valor deles).
Gera evidencias/04c-teste-final.md.

Uso: uv run python scripts/avaliar_teste_final.py [lote_inicial=2]
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ambiente import carregar_ambiente
from evidencia_modelo import tabela_markdown

RAIZ = Path(__file__).resolve().parents[1]


def resumo_teste_final(df: pd.DataFrame) -> dict:
    """df: uma linha por aviso com gold + silver + gabarito (padrao, decisao_esperada, valor_devido)."""
    from ml.treino import metricas, metricas_fast_track, regra_base
    from parecer.avaliacao import valor_dentro_tolerancia

    y = (~df["padrao"].str.startswith("legitimo_")).astype(int).to_numpy()
    regra = regra_base(df).to_numpy()
    pagamentos = df[df["decisao_esperada"].str.startswith("pagar")]
    ft = df[df["fast_track"]]
    ft_susp = ft[~ft["padrao"].str.startswith("legitimo_")]
    return {
        "modelo": metricas(y, df["score_suspeita"], "") | metricas_fast_track(df, y, df["score_suspeita"], ""),
        "regra": metricas(y, regra, "") | metricas_fast_track(df, y, regra, ""),
        "parecer": {"recomendacao_correta": float((df["recomendacao_ia"] == df["decisao_esperada"]).mean()),
                    "valor_dentro_tolerancia_pagamentos": float(np.mean([
                        valor_dentro_tolerancia(v, d) for v, d in zip(pagamentos["valor_sugerido"], pagamentos["valor_devido"])]))
                    if len(pagamentos) else float("nan"),
                    "status_ok": float((df["status_parecer"] == "ok").mean())},
        "fast_track": {"avisos": int(len(df)), "no_fast_track": int(len(ft)), "pct": float(len(ft) / len(df)) if len(df) else 0.0,
                       "suspeitos_no_fast_track": int(len(ft_susp)),
                       "valor_suspeitos_no_fast_track": float(ft_susp["valor_sugerido"].sum()),
                       "valor_pago_fast_track": float(ft["valor_sugerido"].sum())},
        "por_padrao": (df.assign(correto=df["recomendacao_ia"] == df["decisao_esperada"],
                                 bloqueado=df["score_suspeita"] >= 0.2)
                       .groupby("padrao").agg(avisos=("id_aviso", "size"), parecer_correto=("correto", "mean"),
                                              score_bloqueia=("bloqueado", "mean"), fast_track=("fast_track", "mean"))
                       .round(3).reset_index()),
        "por_lote": (df.assign(suspeito=y, liberado=df["score_suspeita"] < 0.2)
                     .groupby("lote").apply(lambda g: pd.Series({
                         "avisos": len(g), "suspeitos": int(g["suspeito"].sum()),
                         "suspeitos_liberados_pelo_score": int((g["suspeito"] & g["liberado"]).sum()),
                         "prestador_concentrado_bloqueado": float((g.loc[g["padrao"] == "prestador_concentrado", "liberado"] == 0).mean())
                         if (g["padrao"] == "prestador_concentrado").any() else float("nan"),
                         "pct_fast_track": float(g["fast_track"].mean())}), include_groups=False)
                     .round(3).reset_index()),
    }


def renderizar_teste_final(quando: str, lotes: list[int], r: dict) -> str:
    m, g = r["modelo"], r["regra"]
    linhas = [("AUC", "auc"), ("suspeitos com score < 0,2 (escapariam do bloqueio)", "suspeitos_abaixo_limiar"),
              ("legítimos com score < 0,2", "legitimos_abaixo_limiar"), ("precisão nos 10% do topo", "precisao_top10"),
              ("recall nos 10% do topo", "recall_top10"), ("teto do recall nos 10% do topo", "recall_top10_teto"),
              ("elegíveis ao fast track (≤ R$ 5 mil, cobertura, evidência forte)", "ft_elegiveis"),
              ("suspeitos elegíveis", "ft_suspeitos_elegiveis"), ("suspeitos elegíveis liberados", "ft_suspeitos_liberados")]
    p = ["# Teste final: lotes do evento nunca vistos no treino nem na avaliação", "",
         f"Gerado em {quando} com `uv run python scripts/avaliar_teste_final.py`. Lotes: {', '.join(map(str, lotes))} "
         f"({r['fast_track']['avisos']} avisos). Fonte: `gold.sinistros_analisados` produzido pelo `job_evento` (score do "
         "`modelo_suspeita@champion`, parecer do prompt de produção, regras de fast track); o gabarito só é lido aqui.", "",
         "## Score de suspeita × linha de base de regras", "", "| métrica | modelo | regras |", "|---|---|---|"]
    p += [f"| {nome} | {m[k]:.4g} | {g[k]:.4g} |" for nome, k in linhas]
    pr, ft = r["parecer"], r["fast_track"]
    p += ["", "## Parecer prévio (todos os avisos dos lotes)", "",
          f"- Recomendação igual à do gabarito: **{pr['recomendacao_correta']:.1%}**",
          f"- Valor sugerido a ±10% do devido (pagamentos esperados): **{pr['valor_dentro_tolerancia_pagamentos']:.1%}**",
          f"- Pareceres com status `ok`: {pr['status_ok']:.1%}", "",
          "## Fast track", "",
          f"- {ft['no_fast_track']} de {ft['avisos']} avisos no fast track (**{ft['pct']:.1%}**), "
          f"com R$ {ft['valor_pago_fast_track']:,.2f} pagos sem regulador".replace(",", "X").replace(".", ",").replace("X", "."),
          f"- Suspeitos que entraram no fast track: **{ft['suspeitos_no_fast_track']}** "
          f"(R$ {ft['valor_suspeitos_no_fast_track']:,.2f})".replace(",", "X").replace(".", ",").replace("X", "."), "",
          "## Por padrão", "", tabela_markdown(r["por_padrao"]), "",
          "## Por lote (o prestador concentrado só aparece com histórico de 30 dias)", "", tabela_markdown(r["por_lote"]), ""]
    return "\n".join(p)


def main(lote_inicial: str = "2", saida: str = "evidencias/04c-teste-final.md") -> None:
    from databricks.sdk import WorkspaceClient

    w, amb = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")), carregar_ambiente()
    c = amb.catalogo
    sql = f"""SELECT g.id_aviso, g.lote, g.valor_reclamado, g.score_suspeita, g.recomendacao_ia, g.valor_sugerido,
        g.status_parecer, g.fast_track, s.cobertura_valida, s.forca_evidencia_climatica, s.dias_desde_contratacao,
        s.menciona_dano_anterior, s.desvio_preco_pct, gb.padrao, gb.decisao_esperada, CAST(gb.valor_devido AS DOUBLE) AS valor_devido
      FROM {c}.{amb.schema('gold')}.sinistros_analisados g
      JOIN {c}.{amb.schema('silver')}.sinistros_enriquecidos s ON s.id_aviso = g.id_aviso
      JOIN read_files('{amb.volume_restrito}/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) gb
        ON gb.id_aviso = g.id_aviso
      WHERE g.lote >= {int(lote_inicial)}"""
    r = w.statement_execution.execute_statement(statement=sql, warehouse_id=os.environ["FE_BAR_WAREHOUSE_ID"], wait_timeout="50s")
    linhas = list(r.result.data_array or [])
    proximo = r.result.next_chunk_index
    while proximo is not None:
        parte = w.statement_execution.get_statement_result_chunk_n(r.statement_id, proximo)
        linhas += parte.data_array or []
        proximo = parte.next_chunk_index
    df = pd.DataFrame(linhas, columns=[col.name for col in r.manifest.schema.columns])
    for col in ("valor_reclamado", "score_suspeita", "valor_sugerido", "dias_desde_contratacao", "desvio_preco_pct", "valor_devido"):
        df[col] = pd.to_numeric(df[col])
    df["lote"] = df["lote"].astype(int)
    for col in ("fast_track", "cobertura_valida", "menciona_dano_anterior"):
        df[col] = df[col].map({"true": True, "false": False})
    lotes = sorted(df["lote"].unique().tolist())
    md = renderizar_teste_final(datetime.now().strftime("%Y-%m-%d %H:%M"), lotes, resumo_teste_final(df))
    (RAIZ / saida).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main(*sys.argv[1:])

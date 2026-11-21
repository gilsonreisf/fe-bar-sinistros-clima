"""Custo real medido (system.billing.usage × list_prices) e custo por unidade: por PDF lido, por aviso processado no
pipeline e por parecer gerado no lote. Gera evidencias/09-custo-real.md.

Os valores são de preço de lista, no workspace de desenvolvimento, e servem de **referência, a calibrar na PoC**:
o faturamento chega com atraso de algumas horas e o volume por unidade depende do cliente (PDFs por aviso, tamanho dos
documentos, LLM escolhido). O SQL Warehouse e o treino são custo de desenvolvimento, não de unidade.

Uso: uv run python scripts/custo_por_unidade.py
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from ambiente import carregar_ambiente

RAIZ = Path(__file__).resolve().parents[1]


def _custo_sql(ws_id: str) -> str:
    return f"""SELECT u.billing_origin_product AS produto, u.sku_name AS sku,
  coalesce(u.usage_metadata.endpoint_name, u.usage_metadata.dlt_pipeline_id, u.usage_metadata.job_id,
           u.usage_metadata.app_name, u.usage_metadata.warehouse_id, '') AS recurso,
  round(sum(u.usage_quantity), 2) AS quantidade, any_value(u.usage_unit) AS unidade,
  round(sum(u.usage_quantity * lp.pricing.default), 2) AS custo_lista_usd, max(u.usage_end_time) AS faturado_ate
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices lp ON lp.sku_name = u.sku_name AND lp.cloud = u.cloud
  AND u.usage_start_time >= lp.price_start_time AND (lp.price_end_time IS NULL OR u.usage_start_time < lp.price_end_time)
WHERE u.workspace_id = '{ws_id}' AND u.usage_date >= DATE'2026-11-20'
GROUP BY ALL ORDER BY custo_lista_usd DESC"""


def main(saida: str = "evidencias/09-custo-real.md") -> None:
    from databricks.sdk import WorkspaceClient

    from executar_sql import executar

    w, amb = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")), carregar_ambiente()
    wh, c = os.environ["FE_BAR_WAREHOUSE_ID"], amb.catalogo
    ws_id = str(w.get_workspace_id())
    colunas, linhas = executar(w, wh, _custo_sql(ws_id))
    custo = [dict(zip(colunas, l)) for l in linhas]

    def soma(filtro) -> float:
        return sum(float(x["custo_lista_usd"] or 0) for x in custo if filtro(x))

    _, v = executar(w, wh, f"""SELECT (SELECT count(*) FROM {c}.{amb.schema('silver')}.documentos_texto) AS pdfs,
      (SELECT count(*) FROM {c}.{amb.schema('silver')}.avisos) AS avisos,
      (SELECT count(*) FROM {c}.{amb.schema('gold')}.sinistros_analisados WHERE status_parecer = 'ok'
         AND analisado_em <= (SELECT max(usage_end_time) FROM system.billing.usage
           WHERE workspace_id = '{ws_id}' AND usage_metadata.endpoint_name = 'databricks-claude-haiku-5-5')) AS pareceres_faturados""")
    pdfs, avisos, pareceres = (int(x) for x in v[0])
    ai_func = soma(lambda x: x["produto"] == "AI_FUNCTIONS")
    pipeline = soma(lambda x: x["produto"] == "DLT")
    haiku = soma(lambda x: x["recurso"] == "databricks-claude-haiku-5-5")
    # computação serverless do job do evento (score, regras e chamadas do parecer), que também escala com o evento
    job_evento = os.environ.get("FE_BAR_JOB_EVENTO_ID", "")
    computacao_job = soma(lambda x: x["produto"] == "JOBS" and x["recurso"] == job_evento) if job_evento else 0.0
    por_pdf = ai_func / max(pdfs, 1)
    por_aviso_pipeline = (ai_func + pipeline) / max(avisos, 1)
    por_parecer = (haiku + computacao_job) / max(pareceres, 1)
    total = soma(lambda x: True)

    def usd(x: float, casas: int = 2) -> str:
        return f"US$ {x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def inteiro(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    md = ["# Custo real medido e custo por unidade", "",
          f"Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M')} com `uv run python scripts/custo_por_unidade.py`, a partir "
          "de `system.billing.usage` com o preço de lista (`system.billing.list_prices`).", "",
          "> Valores de **referência, a calibrar na PoC**: preço de lista, workspace de desenvolvimento e faturamento com "
          "algumas horas de atraso (coluna `faturado_ate`). O volume por unidade depende do cliente (PDFs por aviso, "
          "tamanho dos documentos e LLM escolhido).", "",
          "## Custo por unidade (o que escala com o evento)", "",
          "| unidade | volume medido | custo medido | custo médio por unidade |", "|---|---|---|---|",
          f"| PDF lido e extraído (`ai_parse_document` + `ai_extract`) | {inteiro(pdfs)} PDFs | {usd(ai_func)} | "
          f"{usd(por_pdf, 4)} |",
          f"| Aviso processado no pipeline (PDFs + computação serverless) | {inteiro(avisos)} avisos | "
          f"{usd(ai_func + pipeline)} | {usd(por_aviso_pipeline, 4)} |",
          f"| Parecer prévio em lote (Claude Haiku 5.5 + computação do job do evento) | {inteiro(pareceres)} pareceres já "
          f"faturados | {usd(haiku + computacao_job)} | {usd(por_parecer, 4)} |", "",
          f"- **Por sinistro completo** (pipeline + parecer): cerca de **{usd(por_aviso_pipeline + por_parecer, 3)}**. "
          f"Em um evento de 8 mil avisos, isso dá cerca de {usd((por_aviso_pipeline + por_parecer) * 8000)}.",
          "- O parecer do app (\"Reanalisar com IA\", Claude Sonnet 5.5 no endpoint) é sob demanda: cerca de US$ 0,02 por "
          "chamada pela medição de tokens da fase 4 (D-022).",
          "- Custo fixo de operação (não por unidade): o endpoint do parecer e o Lakebase com scale-to-zero, e o SQL "
          "Warehouse do painel e do Genie enquanto estiver ligado.", "",
          f"## Tudo o que foi faturado no workspace desde 2026-11-20 (total {usd(total)}, inclui desenvolvimento)", "",
          "| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    md += ["| " + " | ".join("" if v is None else str(v) for v in l) + " |" for l in linhas]
    (RAIZ / saida).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{saida}: por PDF {por_pdf:.4f}, por aviso {por_aviso_pipeline:.4f}, por parecer {por_parecer:.4f}")


if __name__ == "__main__":
    main()

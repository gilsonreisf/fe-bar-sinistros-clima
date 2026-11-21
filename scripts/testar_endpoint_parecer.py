"""Testa o endpoint publicado do parecer com 3 sinistros reais (legítimo, sem evento climático, orçamento inflado) e
grava evidencias/05-endpoint-parecer.md: estado e AI Gateway do endpoint, parecer, latência, trace e inference table.

Uso: uv run python scripts/testar_endpoint_parecer.py [nome_do_endpoint]   (padrão: sinistros-clima-parecer-dev)
Espera o endpoint ficar pronto (scale-to-zero e primeira subida levam alguns minutos).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from ambiente import carregar_ambiente

RAIZ = Path(__file__).resolve().parents[1]
PADROES = ("legitimo_simples", "sem_evento_climatico", "orcamento_inflado")


def moeda(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def renderizar_teste_endpoint(quando: str, nome: str, estado: dict, gateway: dict, casos: list[dict],
                              trace_encontrado: dict[str, bool], inference_table: list[str]) -> str:
    p = ["# Endpoint do parecer prévio: teste ponta a ponta", "",
         f"Gerado em {quando} com `uv run python scripts/testar_endpoint_parecer.py`.", "",
         "## Endpoint", "", f"- Nome: `{nome}`",
         f"- Estado: ready = `{estado.get('ready')}`, config_update = `{estado.get('config_update')}`",
         f"- Modelo servido: `{estado.get('entidade')}` versão {estado.get('versao')} (CPU Small, scale-to-zero: "
         f"{estado.get('scale_to_zero')})",
         f"- AI Gateway: inference table = `{json.dumps(gateway.get('inference_table_config', {}), ensure_ascii=False)}`, "
         f"usage tracking = `{json.dumps(gateway.get('usage_tracking_config', {}))}`",
         f"- Tabelas de inferência no schema: {', '.join(f'`{t}`' for t in inference_table) or 'ainda não criadas (atraso normal)'}",
         "", "## Pareceres devolvidos pelo endpoint", ""]
    for c in casos:
        p += [f"### {c['id_aviso']} ({c['padrao']}; esperado: {c['esperado']})", "",
              f"- Recomendação: **{c['recomendacao']}**, valor sugerido {moeda(c['valor_sugerido'])}, confiança "
              f"{c['confianca']}, status `{c['status_parecer']}`, prompt v{c['versao_prompt']}",
              f"- Cláusulas: {', '.join(json.loads(c['clausulas']))}",
              "- Motivos:", *[f"  - {m}" for m in json.loads(c["motivos"])],
              f"- Latência da chamada: {c['latencia_s']:.1f} s; trace `{c['trace_id'] or '(sem id)'}` "
              f"(encontrado no experimento: {trace_encontrado.get(c['trace_id'], False)})", ""]
    return "\n".join(p)


def _sql(w, sql: str) -> list[list]:
    r = w.statement_execution.execute_statement(statement=sql, warehouse_id=os.environ["FE_BAR_WAREHOUSE_ID"],
                                                wait_timeout="50s")
    return r.result.data_array or []


def main(nome: str = "sinistros-clima-parecer-dev", saida: str = "evidencias/05-endpoint-parecer.md") -> None:
    import mlflow
    from databricks.sdk import WorkspaceClient

    perfil = os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")
    w, amb = WorkspaceClient(profile=perfil), carregar_ambiente()
    inicio = time.time()
    while True:
        ep = w.api_client.do("GET", f"/api/2.0/serving-endpoints/{nome}")
        st = ep.get("state", {})
        if st.get("ready") == "READY" and st.get("config_update") == "NOT_UPDATING":
            break
        if time.time() - inicio > 45 * 60 or st.get("config_update") == "UPDATE_FAILED":
            raise SystemExit(f"endpoint não ficou pronto: {st}")
        print(f"aguardando o endpoint: {st}")
        time.sleep(30)
    entidade = (ep.get("config", {}).get("served_entities") or [{}])[0]
    cat, silver, ml = amb.catalogo, amb.schema("silver"), amb.schema("ml")
    linhas = _sql(w, f"""WITH g AS (SELECT * FROM read_files('{amb.volume_restrito}/gabarito/gabarito_evento_2026.csv',
        format => 'csv', header => true)),
      x AS (SELECT e.id_aviso, e.entrada_json, g.padrao, g.decisao_esperada,
              row_number() OVER (PARTITION BY g.padrao ORDER BY e.id_aviso) AS rn
            FROM {cat}.{silver}.entrada_parecer e JOIN g ON g.id_aviso = e.id_aviso
            WHERE g.padrao IN ({', '.join(repr(p) for p in PADROES)}))
      SELECT id_aviso, entrada_json, padrao, decisao_esperada FROM x WHERE rn = 1 ORDER BY padrao""")
    casos = []
    for id_aviso, entrada_json, padrao, esperado in linhas:
        t = time.time()
        r = w.api_client.do("POST", f"/serving-endpoints/{nome}/invocations",
                            body={"dataframe_records": [{"entrada_json": entrada_json}]})
        pred = r["predictions"][0] if isinstance(r.get("predictions"), list) else r["predictions"]
        casos.append({"id_aviso": id_aviso, "padrao": padrao, "esperado": esperado, "latencia_s": time.time() - t, **pred})
    mlflow.set_tracking_uri(f"databricks://{perfil}")
    encontrados = {}
    for c in casos:
        try:
            encontrados[c["trace_id"]] = mlflow.get_trace(c["trace_id"]) is not None if c["trace_id"] else False
        except Exception:  # noqa: BLE001 (o trace do serving pode atrasar; registra como não encontrado)
            encontrados[c["trace_id"]] = False
    tabelas = [l[1] for l in _sql(w, f"SHOW TABLES IN {cat}.{ml} LIKE 'parecer*'")]
    md = renderizar_teste_endpoint(datetime.now().strftime("%Y-%m-%d %H:%M"), nome,
                                   {"ready": st.get("ready"), "config_update": st.get("config_update"),
                                    "entidade": entidade.get("entity_name"), "versao": entidade.get("entity_version"),
                                    "scale_to_zero": entidade.get("scale_to_zero_enabled")},
                                   ep.get("ai_gateway", {}), casos, encontrados, tabelas)
    (RAIZ / saida).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main(*sys.argv[1:])

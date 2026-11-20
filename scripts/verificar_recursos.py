"""Verifica no workspace os recursos de que a spec depende (seção 12) e grava a evidência em Markdown.

Uso: uv run python scripts/verificar_recursos.py
"""
from __future__ import annotations

import io
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from databricks.sdk import WorkspaceClient

from ambiente import Ambiente, carregar_ambiente
from executar_sql import executar

ICONES = {"ok": "✅", "parcial": "⚠️", "indisponivel": "❌"}
RECURSOS_DAB = ["pipelines", "jobs", "apps", "model_serving_endpoints", "experiments", "registered_models",
                "postgres_projects", "postgres_synced_tables", "synced_database_tables", "database_instances",
                "genie_spaces", "dashboards", "volumes", "schemas"]


@dataclass
class Verificacao:
    item: str
    status: str  # ok | parcial | indisponivel
    detalhe: str


def renderizar_markdown(verificacoes: list[Verificacao], quando: str) -> str:
    linhas = ["# Verificações do ambiente", "", f"Executado em {quando} pelo script `scripts/verificar_recursos.py`.", "",
              "| Item | Status | Detalhe |", "|---|---|---|"]
    linhas += [f"| {v.item} | {ICONES.get(v.status, '')} {v.status} | {v.detalhe} |" for v in verificacoes]
    return "\n".join(linhas) + "\n"


def _pdf_teste() -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 750, "Orçamento de teste: Telha cerâmica colonial, 35 m², R$ 1.925,00")
    c.save()
    return buf.getvalue()


def checar_modelos(w) -> Verificacao:
    nomes = sorted(e.name for e in w.serving_endpoints.list() if "claude" in e.name and "sonnet" in e.name)
    return Verificacao("Modelo fundacional Claude Sonnet (parecer)", "ok" if nomes else "indisponivel", ", ".join(nomes) or "nenhum endpoint")


def checar_ai_parse_document(w, wh, amb: Ambiente) -> Verificacao:
    caminho = f"{amb.volume_arquivos}/_verificacao/teste.pdf"
    w.files.upload(caminho, io.BytesIO(_pdf_teste()), overwrite=True)
    try:
        _, linhas = executar(w, wh, f"SELECT CAST(ai_parse_document(content) AS STRING) FROM READ_FILES('{caminho}', format => 'binaryFile')")
        texto = linhas[0][0] if linhas else ""
        return Verificacao("ai_parse_document", "ok" if "Telha" in texto else "parcial", f"{len(texto)} caracteres extraídos")
    except RuntimeError as e:
        return Verificacao("ai_parse_document", "indisponivel", str(e).splitlines()[0][:200])


def checar_abac(w, wh, amb: Ambiente) -> Verificacao:
    try:
        executar(w, wh, f"SHOW POLICIES ON SCHEMA {amb.catalogo}.{amb.schema('landing')}")
        return Verificacao("Políticas ABAC", "ok", "SHOW POLICIES executou")
    except RuntimeError as e:
        return Verificacao("Políticas ABAC", "indisponivel", str(e).splitlines()[0][:200])


def checar_lakebase(w) -> Verificacao:
    try:
        n = len(list(w.postgres.list_projects()))
    except Exception as e:  # noqa: BLE001 - a evidência registra qualquer falha
        return Verificacao("Lakebase (postgres API)", "indisponivel", str(e)[:200])
    cdf = hasattr(w.postgres, "create_cdf_config")
    return Verificacao("Lakebase (postgres API) e Lakehouse Sync", "ok" if cdf else "parcial",
                       f"{n} projetos; API de CDF (Lakehouse Sync) {'presente' if cdf else 'ausente'} no SDK; ativação real na fase 6")


def checar_dab() -> Verificacao:
    saida = subprocess.run(["databricks", "bundle", "schema"], capture_output=True, text=True, check=True).stdout
    props = json.loads(saida)
    texto = json.dumps(props)
    presentes = [r for r in RECURSOS_DAB if f'"{r}"' in texto]
    ausentes = [r for r in RECURSOS_DAB if r not in presentes]
    return Verificacao("Recursos suportados pelo DAB", "ok", f"presentes: {', '.join(presentes)}; ausentes: {', '.join(ausentes) or 'nenhum'}")


def checar_warehouse(w, wh) -> Verificacao:
    x = w.warehouses.get(wh)
    return Verificacao("SQL Warehouse", "ok" if x.enable_serverless_compute else "parcial", f"{x.name} (serverless={x.enable_serverless_compute})")


def main() -> None:
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    wh = os.environ["FE_BAR_WAREHOUSE_ID"]
    amb = carregar_ambiente()
    verificacoes = [checar_warehouse(w, wh), checar_modelos(w), checar_ai_parse_document(w, wh, amb),
                    checar_abac(w, wh, amb), checar_lakebase(w), checar_dab()]
    md = renderizar_markdown(verificacoes, datetime.now().strftime("%Y-%m-%d %H:%M"))
    destino = Path("evidencias/00a-verificacoes-ambiente.md")
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()

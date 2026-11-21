"""Converte a execução de um notebook de job em .ipynb com as saídas em TEXTO (o avaliador só lê texto).

Uso: uv run python scripts/exportar_execucao.py <task_run_id> <saida.ipynb>
O export do job é um HTML com o modelo do notebook (base64 de JSON com URL-encoding). Tabelas viram Markdown, imagens
viram uma linha apontando para os artefatos do MLflow, e o host do workspace e e-mails são ocultados (repo público).
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_HOST = re.compile(r"https://[a-z0-9.-]+\.(?:cloud\.databricks\.com|azuredatabricks\.net|gcp\.databricks\.com)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_ORG = re.compile(r"[?&]o=\d+")  # ID do workspace nas URLs


def extrair_modelo(html: str) -> dict:
    m = re.search(r"__DATABRICKS_NOTEBOOK_MODEL = '([^']+)'", html)
    if not m:
        raise ValueError("o HTML exportado não tem o modelo do notebook")
    return json.loads(urllib.parse.unquote(base64.b64decode(m.group(1)).decode("utf-8")))


def limpar_texto(texto: str) -> str:
    return _ORG.sub("", _EMAIL.sub("<e-mail>", _HOST.sub("<workspace>", _ANSI.sub("", texto))))


def _linhas(texto: str) -> list[str]:
    return texto.splitlines(keepends=True)


def _valor(v) -> str:
    return "" if v is None else str(v)


def _tabela(resultado: dict) -> str:
    colunas = [c["name"] for c in resultado.get("schema") or []]
    linhas = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    linhas += ["| " + " | ".join(_valor(v) for v in linha) + " |" for linha in resultado.get("data") or []]
    return "\n".join(linhas) + "\n"


def _saidas(resultados: dict | None) -> list[dict]:
    if not resultados:
        return []
    itens = resultados["data"] if resultados.get("type") == "listResults" else [resultados]
    saidas = []
    for item in itens:
        tipo = item.get("type")
        if tipo == "table":
            saidas.append({"output_type": "execute_result", "execution_count": None, "metadata": {},
                           "data": {"text/plain": _linhas(limpar_texto(_tabela(item)))}})
        elif tipo in ("image", "images", "mimeBundle") or (tipo == "html" and "<img" in str(item.get("data"))):
            saidas.append({"output_type": "stream", "name": "stdout", "text": ["[imagem: ver os artefatos do run no MLflow]\n"]})
        elif tipo == "error":
            saidas.append({"output_type": "stream", "name": "stderr", "text": _linhas(limpar_texto(str(item.get("data"))))})
        elif item.get("data") not in (None, ""):
            saidas.append({"output_type": "stream", "name": "stdout", "text": _linhas(limpar_texto(str(item["data"])))})
    return saidas


def modelo_para_ipynb(modelo: dict) -> dict:
    celulas = []
    for comando in sorted(modelo.get("commands", []), key=lambda c: float(c.get("position", 0))):
        fonte = comando.get("command", "")
        if fonte.lstrip().startswith("%md"):
            texto = re.sub(r"^\s*%md[ \t]*\n?", "", fonte, count=1)
            celulas.append({"cell_type": "markdown", "metadata": {}, "source": _linhas(texto)})
            continue
        saidas = _saidas(comando.get("results"))
        if comando.get("error"):
            saidas.append({"output_type": "stream", "name": "stderr", "text": _linhas(limpar_texto(str(comando["error"])))})
        celulas.append({"cell_type": "code", "metadata": {}, "execution_count": None, "source": _linhas(fonte),
                        "outputs": saidas})
    return {"nbformat": 4, "nbformat_minor": 5, "cells": celulas,
            "metadata": {"language_info": {"name": modelo.get("language", "python")},
                         "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}}


def main(task_run_id: str, saida: str) -> None:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.jobs import ViewsToExport

    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    export = w.jobs.export_run(int(task_run_id), views_to_export=ViewsToExport.CODE)
    nb = modelo_para_ipynb(extrair_modelo(export.views[0].content))
    Path(saida).parent.mkdir(parents=True, exist_ok=True)
    Path(saida).write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{saida}: {len(nb['cells'])} células")


if __name__ == "__main__":
    main(*sys.argv[1:])

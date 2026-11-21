import base64
import json
import urllib.parse

from exportar_execucao import extrair_modelo, limpar_texto, modelo_para_ipynb


def _html(modelo: dict) -> str:
    codificado = base64.b64encode(urllib.parse.quote(json.dumps(modelo)).encode()).decode()
    return f"<html><script>var __DATABRICKS_NOTEBOOK_MODEL = '{codificado}';</script></html>"


MODELO = {"language": "python", "commands": [
    {"position": 2.0, "command": "%md # Título\nTexto", "results": None},
    {"position": 1.0, "command": "print('oi')", "results": {"type": "listResults", "data": [
        {"type": "ansi", "data": "\x1b[1;38mmodelo: x\x1b[0m\nVer em https://fevm-exemplo.cloud.databricks.com/ml/x?o=1 por ana@exemplo.com"},
        {"type": "table", "schema": [{"name": "metrica"}, {"name": "valor"}], "data": [["auc", 0.99], ["ap", None]]},
        {"type": "image", "data": "iVBORw0KGgo="}]}},
    {"position": 3.0, "command": "dbutils.notebook.exit('{}')", "results": {"type": "raw", "data": "{\"a\": 1}"}},
]}


def test_extrai_o_modelo_do_html_exportado():
    assert extrair_modelo(_html(MODELO)) == MODELO


def test_limpa_ansi_e_oculta_host_e_email():
    texto = limpar_texto("\x1b[94mhttps://fevm-x.cloud.databricks.com/jobs/1?o=7474657549414280\x1b[0m de joao.silva@empresa.com")
    assert texto == "<workspace>/jobs/1 de <e-mail>"


def test_ipynb_na_ordem_com_markdown_texto_e_tabela():
    nb = modelo_para_ipynb(MODELO)
    assert nb["nbformat"] == 4 and [c["cell_type"] for c in nb["cells"]] == ["code", "markdown", "code"]
    codigo, markdown, saida = nb["cells"]
    assert "".join(markdown["source"]) == "# Título\nTexto"
    textos = [o for o in codigo["outputs"] if o["output_type"] == "stream"]
    assert "modelo: x" in "".join(textos[0]["text"]) and "<workspace>/ml/x" in "".join(textos[0]["text"])
    tabela = "".join(next(o for o in codigo["outputs"] if o["output_type"] == "execute_result")["data"]["text/plain"])
    assert "| metrica | valor |" in tabela and "| auc | 0.99 |" in tabela and "| ap |  |" in tabela
    assert "[imagem: ver os artefatos do run no MLflow]" in json.dumps(codigo["outputs"], ensure_ascii=False)
    assert "iVBORw0KGgo=" not in json.dumps(nb)
    assert "\"a\": 1" in "".join(saida["outputs"][0]["text"])

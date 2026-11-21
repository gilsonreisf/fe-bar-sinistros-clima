"""Checagens estáticas dos jobs do bundle: nada fixo (D-016), nada com nome de usuário, wheel do Volume (D-019)."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
JOB_TREINO = RAIZ / "recursos/job_treino_modelo.yml"
NOTEBOOK_TREINO = RAIZ / "notebooks/treino_modelo_suspeita.py"


def test_job_de_treino_sem_nomes_fixos_nem_usuario():
    yml = JOB_TREINO.read_text(encoding="utf-8")
    assert "fe_bar_sinistros_catalog" not in yml and "/Users/" not in yml and "@" not in yml


def test_experimento_em_pasta_compartilhada_e_o_mesmo_no_job():
    yml = JOB_TREINO.read_text(encoding="utf-8")
    caminhos = re.findall(r"(/Shared/\$\{bundle\.name\}/\$\{bundle\.target\}/[a-z_]+)", yml)
    assert len(caminhos) == 2 and len(set(caminhos)) == 1, caminhos


def test_job_de_treino_instala_o_wheel_e_fixa_o_lightgbm():
    yml = JOB_TREINO.read_text(encoding="utf-8")
    assert "- ${var.pacote_python}" in yml and "--no-deps" not in yml and "- lightgbm==4.7.0" in yml
    assert 'environment_version: "4"' in yml
    for parametro in ("catalogo", "schema_silver", "schema_ml", "experimento"):
        assert re.search(rf"^\s+{parametro}: ", yml, re.M), parametro


def test_notebook_de_treino_e_fonte_databricks_e_devolve_resultado():
    texto = NOTEBOOK_TREINO.read_text(encoding="utf-8")
    assert texto.startswith("# Databricks notebook source")
    assert "dbutils.notebook.exit(" in texto and 'set_registry_uri("databricks-uc")' in texto
    assert "fe_bar_sinistros_catalog" not in texto and "/Users/" not in texto
    # o rótulo só vem do gabarito restrito; nenhuma coluna proibida entra em montar_features (checado no próprio notebook)
    assert "COLUNAS_PROIBIDAS" in texto and "gabarito_historico_2025.csv" in texto


def test_wheel_so_depende_do_que_o_ambiente_serverless_ja_tem():
    """O job instala o wheel com dependências: nada de faker, reportlab ou databricks-sdk (conflito de pins)."""
    import tomllib
    deps = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    assert sorted(d.split(">")[0] for d in deps) == ["numpy", "pandas"]

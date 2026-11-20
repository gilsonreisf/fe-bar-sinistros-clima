"""Leitura dos arquivos horários do INMET (estações automáticas) e agregação diária por estação.

Fonte: https://portal.inmet.gov.br/dadoshistoricos (um .zip por ano, um CSV por estação, latin-1, ';').
O formato tratado aqui é o de 2019 em diante (colunas 'Data' e 'Hora UTC').
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from regras.clima import MIN_HORAS_VALIDAS, agregar_diario  # noqa: F401 (reexportados)

COL_CHUVA = "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)"
COL_RAJADA = "VENTO, RAJADA MAXIMA (m/s)"
COL_TEMP = "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)"


def _numero(serie: pd.Series) -> pd.Series:
    valores = pd.to_numeric(serie.str.strip().str.replace(",", ".", regex=False), errors="coerce")
    return valores.where(valores > -9000)


def ler_estacao_csv(texto: str) -> tuple[dict, pd.DataFrame]:
    linhas = texto.splitlines()
    meta = {}
    for linha in linhas[:8]:
        chave, _, valor = linha.partition(":;")
        meta[chave.strip().upper()] = valor.strip()
    inicio = next(i for i, l in enumerate(linhas) if l.startswith("Data;"))
    bruto = pd.read_csv(io.StringIO("\n".join(linhas[inicio:])), sep=";", dtype=str, keep_default_na=False)
    estacao = {
        "codigo_estacao": meta["CODIGO (WMO)"],
        "nome": meta["ESTACAO"],
        "uf": meta["UF"],
        "lat": float(meta["LATITUDE"].replace(",", ".")),
        "lon": float(meta["LONGITUDE"].replace(",", ".")),
    }
    horario = pd.DataFrame({
        "codigo_estacao": estacao["codigo_estacao"],
        "data": pd.to_datetime(bruto["Data"], format="%Y/%m/%d").dt.date,
        "hora_utc": bruto["Hora UTC"].str[:2].astype(int),
        "chuva_mm": _numero(bruto[COL_CHUVA]),
        "rajada_ms": _numero(bruto[COL_RAJADA]),
        "temp_c": _numero(bruto[COL_TEMP]),
    })
    return estacao, horario


def ler_zip_uf(caminho_zip: Path, uf: str = "SC") -> tuple[pd.DataFrame, pd.DataFrame]:
    estacoes, horarios = [], []
    with zipfile.ZipFile(caminho_zip) as z:
        for nome in sorted(z.namelist()):
            if f"_{uf}_" not in Path(nome).name:
                continue
            est, hor = ler_estacao_csv(z.read(nome).decode("latin-1"))
            estacoes.append(est)
            horarios.append(hor)
    return pd.DataFrame(estacoes), pd.concat(horarios, ignore_index=True)

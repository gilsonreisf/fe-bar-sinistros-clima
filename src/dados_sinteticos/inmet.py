"""Leitura dos arquivos horários do INMET (estações automáticas) e agregação diária por estação.

Fonte: https://portal.inmet.gov.br/dadoshistoricos (um .zip por ano, um CSV por estação, latin-1, ';').
O formato tratado aqui é o de 2019 em diante (colunas 'Data' e 'Hora UTC').
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from regras.clima import LIMIAR_CHUVA_HORA_MM, LIMIAR_QUEDA_TEMP_C, LIMIAR_RAJADA_MS

MIN_HORAS_VALIDAS = 12
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


def agregar_diario(horario: pd.DataFrame) -> pd.DataFrame:
    h = horario.sort_values(["codigo_estacao", "data", "hora_utc"]).reset_index(drop=True)
    temp = h.groupby("codigo_estacao")["temp_c"]
    minimo_2h = pd.concat([temp.shift(-1), temp.shift(-2)], axis=1).min(axis=1, skipna=True)
    h["queda_temp_2h_c"] = h["temp_c"] - minimo_2h
    completos = h[["chuva_mm", "rajada_ms", "queda_temp_2h_c"]].notna().all(axis=1)
    granizo = (h["chuva_mm"] >= LIMIAR_CHUVA_HORA_MM) & (h["rajada_ms"] >= LIMIAR_RAJADA_MS) & (h["queda_temp_2h_c"] >= LIMIAR_QUEDA_TEMP_C)
    h["granizo_hora"] = np.where(completos, granizo.astype(float), np.nan)
    d = h.groupby(["codigo_estacao", "data"]).agg(
        horas_chuva=("chuva_mm", "count"),
        chuva_mm=("chuva_mm", "sum"),
        chuva_max_hora_mm=("chuva_mm", "max"),
        horas_rajada=("rajada_ms", "count"),
        rajada_max_ms=("rajada_ms", "max"),
        queda_temp_max_c=("queda_temp_2h_c", "max"),
        granizo_horas=("granizo_hora", "sum"),
        granizo_validas=("granizo_hora", "count"),
    ).reset_index()
    d.loc[d["horas_chuva"] < MIN_HORAS_VALIDAS, ["chuva_mm", "chuva_max_hora_mm"]] = np.nan
    d.loc[d["horas_rajada"] < MIN_HORAS_VALIDAS, "rajada_max_ms"] = np.nan
    valido = d["granizo_validas"] >= MIN_HORAS_VALIDAS
    d["granizo_provavel"] = pd.Series(np.where(valido, d["granizo_horas"] > 0, None), dtype="boolean")
    colunas = ["codigo_estacao", "data", "horas_chuva", "chuva_mm", "chuva_max_hora_mm", "horas_rajada",
               "rajada_max_ms", "queda_temp_max_c", "granizo_provavel"]
    return d[colunas]

"""Leitores dos dados públicos preparados em dados/publicos/."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from dados_sinteticos.config import PESO_MINIMO_MUNICIPIO_DC
from regras.clima import JANELA_DIAS


def carregar_municipios_sc(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    return df[["codigo_ibge", "municipio", "lat", "lon"]].astype({"codigo_ibge": int})


def carregar_estacoes(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, dtype={"codigo_estacao": str})


def carregar_clima_diario(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype={"codigo_estacao": str})
    df["data"] = pd.to_datetime(df["data"]).dt.date
    df["granizo_provavel"] = df["granizo_provavel"].astype("boolean")
    return df


def carregar_defesa_civil(caminho: Path, municipios: pd.DataFrame) -> pd.DataFrame:
    dc = pd.read_csv(caminho, dtype={"moradias_atingidas": "Int64"})
    dc["data_inicio"] = pd.to_datetime(dc["data_inicio"]).dt.date
    dc["data_fim"] = pd.to_datetime(dc["data_fim"]).dt.date
    dc = dc.merge(municipios[["municipio", "codigo_ibge", "lat", "lon"]], on="municipio", how="left")
    faltando = dc.loc[dc["codigo_ibge"].isna(), "municipio"].unique().tolist()
    if faltando:
        raise ValueError(f"municípios da Defesa Civil não encontrados na base do IBGE: {faltando}")
    dc["codigo_ibge"] = dc["codigo_ibge"].astype(int)
    bruto = dc["moradias_atingidas"].fillna(PESO_MINIMO_MUNICIPIO_DC).astype(float)
    dc["peso"] = bruto / bruto.sum()
    return dc


def registro_defesa_civil(dc: pd.DataFrame, codigo_ibge: int, data: date) -> bool:
    folga = timedelta(days=JANELA_DIAS)
    linhas = dc[dc["codigo_ibge"] == codigo_ibge]
    return bool(((linhas["data_inicio"] - folga <= data) & (data <= linhas["data_fim"] + folga)).any())

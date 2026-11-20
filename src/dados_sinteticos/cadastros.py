"""Cadastros sintéticos: corretores, prestadores, segurados e apólices (com coberturas)."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from dados_sinteticos import config


def nova_faker(seed: int) -> Faker:
    fk = Faker("pt_BR")
    fk.seed_instance(seed)
    return fk


def gerar_corretores(fk: Faker, n: int) -> pd.DataFrame:
    return pd.DataFrame([{"id_corretor": f"CR-{i:04d}", "nome": fk.name(),
                          "registro_susep": str(fk.random_number(digits=9, fix_len=True))} for i in range(1, n + 1)])


def gerar_prestadores(fk: Faker, n: int) -> pd.DataFrame:
    return pd.DataFrame([{"id_prestador": f"PR-{i:04d}", "razao_social": fk.company(), "cnpj": fk.cnpj()}
                         for i in range(1, n + 1)])


def pesos_carteira(municipios: pd.DataFrame, defesa_civil: pd.DataFrame, fracao_populacao: float) -> pd.Series:
    """Peso de cada município na carteira (soma 1), em duas partes (D-018):
    - `fracao_populacao`: proporcional à população do IBGE (uniforme se a coluna `populacao` não existir);
    - o restante: concentração regional da seguradora nos municípios atingidos (peso da Defesa Civil)."""
    if "populacao" in municipios.columns:
        pop = municipios["populacao"].astype(float).to_numpy()
        base = pd.Series(fracao_populacao * pop / pop.sum(), index=municipios["codigo_ibge"].to_numpy())
    else:
        base = pd.Series(fracao_populacao / len(municipios), index=municipios["codigo_ibge"].to_numpy())
    dc = defesa_civil.groupby("codigo_ibge")["peso"].sum()
    dc = dc / dc.sum() * (1 - fracao_populacao)
    return base.add(dc, fill_value=0.0)


def criar_segurado_avulso(fk: Faker, rng: np.random.Generator, id_segurado: str, mun, codigo_ibge: int) -> dict:
    return {
        "id_segurado": id_segurado, "cpf": fk.cpf(), "nome": fk.name(), "telefone": fk.cellphone_number(),
        "email": fk.free_email(), "logradouro": fk.street_address(), "municipio": mun["municipio"],
        "codigo_ibge": int(codigo_ibge), "uf": "SC",
        "lat": round(float(mun["lat"]) + float(rng.normal(0, 0.01)), 5),
        "lon": round(float(mun["lon"]) + float(rng.normal(0, 0.01)), 5),
    }


def gerar_segurados(fk: Faker, rng: np.random.Generator, municipios: pd.DataFrame, pesos: pd.Series, n: int) -> pd.DataFrame:
    mun = municipios.set_index("codigo_ibge")
    codigos = rng.choice(pesos.index.to_numpy(), size=n, p=(pesos / pesos.sum()).to_numpy())
    return pd.DataFrame([criar_segurado_avulso(fk, rng, f"SG-{i:06d}", mun.loc[c], c) for i, c in enumerate(codigos, start=1)])


def sortear_lmi_franquia(rng: np.random.Generator, cobertura: str, ramo: str) -> tuple[float, float]:
    lo, hi = config.LMI_FAIXAS[cobertura]
    fator = 3 if ramo == "empresarial" else 1
    lmi = float(round(float(rng.uniform(lo, hi)) * fator, -3))
    franquia = config.FRANQUIAS[cobertura] * (2 if ramo == "empresarial" else 1)
    return lmi, float(franquia)


def criar_apolice_avulsa(rng: np.random.Generator, segurado, id_apolice: str, inicio: date, corretores: pd.DataFrame,
                         ramo: str = "residencial", forcar: frozenset = frozenset(), excluir: frozenset = frozenset()) -> tuple[dict, list[dict]]:
    coberturas = []
    for cobertura, prob in config.PROB_COBERTURA.items():
        if cobertura in excluir:
            continue
        if cobertura in forcar or rng.random() < prob:
            lmi, franquia = sortear_lmi_franquia(rng, cobertura, ramo)
            coberturas.append({"id_apolice": id_apolice, "cobertura": cobertura, "lmi": lmi, "franquia": franquia})
    apolice = {
        "id_apolice": id_apolice, "id_segurado": segurado["id_segurado"],
        "id_corretor": corretores["id_corretor"].iloc[int(rng.integers(0, len(corretores)))], "ramo": ramo,
        "codigo_ibge": int(segurado["codigo_ibge"]), "municipio": segurado["municipio"],
        "lat": float(segurado["lat"]), "lon": float(segurado["lon"]),
        "inicio_vigencia": inicio.isoformat(), "fim_vigencia": (inicio + timedelta(days=365)).isoformat(),
        "premio_anual": round(float(rng.uniform(*config.PREMIO_FAIXAS[ramo])), 2),
    }
    return apolice, coberturas


def gerar_apolices(rng: np.random.Generator, segurados: pd.DataFrame, corretores: pd.DataFrame, n: int,
                   inicio_min: date, inicio_max: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """As primeiras len(segurados) apólices são residenciais (uma por segurado); o restante é empresarial."""
    apolices, coberturas = [], []
    dias = (inicio_max - inicio_min).days
    for i in range(1, n + 1):
        if i <= len(segurados):
            segurado, ramo = segurados.iloc[i - 1], "residencial"
        else:
            segurado, ramo = segurados.iloc[int(rng.integers(0, len(segurados)))], "empresarial"
        inicio = inicio_min + timedelta(days=int(rng.integers(0, dias + 1)))
        ap, cob = criar_apolice_avulsa(rng, segurado, f"AP-{i:07d}", inicio, corretores, ramo=ramo)
        apolices.append(ap)
        coberturas.extend(cob)
    return pd.DataFrame(apolices), pd.DataFrame(coberturas)

"""Baixa e prepara os dados públicos (INMET 2025/2026 de SC e municípios de SC, com a população do Censo 2022).

Uso: uv run python scripts/preparar_dados_publicos.py
Saídas versionadas em dados/publicos/; arquivos grandes em dados/brutos/ (fora do git).
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pandas as pd

from dados_sinteticos.inmet import agregar_diario, ler_zip_uf

RAIZ = Path(__file__).resolve().parents[1]
BRUTOS = RAIZ / "dados/brutos"
PUBLICOS = RAIZ / "dados/publicos"
URL_INMET = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
URL_MUNICIPIOS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
# IBGE, Censo 2022, tabela 4709 (população residente), todos os municípios de SC (N6 dentro de N3 = 42)
URL_POPULACAO = "https://servicodados.ibge.gov.br/api/v3/agregados/4709/periodos/2022/variaveis/93?localidades=N6%5BN3%5B42%5D%5D"
ANOS = (2025, 2026)


def baixar(url: str, destino: Path) -> Path:
    if destino.exists():
        print(f"já existe: {destino.name}")
        return destino
    print(f"baixando {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r:
        destino.write_bytes(r.read())
    return destino


def main() -> None:
    BRUTOS.mkdir(parents=True, exist_ok=True)
    PUBLICOS.mkdir(parents=True, exist_ok=True)

    muni = pd.read_csv(baixar(URL_MUNICIPIOS, BRUTOS / "municipios_brasil.csv"))
    sc = muni[muni["codigo_uf"] == 42].rename(columns={"nome": "municipio", "latitude": "lat", "longitude": "lon"})
    series = json.loads(baixar(URL_POPULACAO, BRUTOS / "populacao_sc_censo2022.json").read_text())[0]["resultados"][0]["series"]
    pop = pd.DataFrame({"codigo_ibge": [int(s["localidade"]["id"]) for s in series],
                        "populacao": [int(s["serie"]["2022"]) for s in series]})
    sc = sc.merge(pop, on="codigo_ibge", how="left", validate="one_to_one")
    if sc["populacao"].isna().any():
        raise ValueError(f"municípios sem população no IBGE: {sc.loc[sc['populacao'].isna(), 'municipio'].tolist()}")
    sc = sc.astype({"populacao": int})
    sc[["codigo_ibge", "municipio", "lat", "lon", "populacao"]].sort_values("municipio").to_csv(PUBLICOS / "municipios_sc.csv", index=False)
    print(f"municípios de SC: {len(sc)}, população total: {sc['populacao'].sum():,}")

    estacoes = []
    for ano in ANOS:
        est, horario = ler_zip_uf(baixar(URL_INMET.format(ano=ano), BRUTOS / f"inmet_{ano}.zip"), "SC")
        estacoes.append(est)
        horario.to_csv(BRUTOS / f"inmet_sc_horario_{ano}.csv", index=False)
        diario = agregar_diario(horario)
        diario.to_csv(PUBLICOS / f"clima_sc_diario_{ano}.csv", index=False)
        print(f"{ano}: {est.shape[0]} estações, {len(horario)} horas, {len(diario)} estação-dias")
    pd.concat(estacoes).drop_duplicates("codigo_estacao").sort_values("codigo_estacao").to_csv(PUBLICOS / "estacoes_inmet_sc.csv", index=False)


if __name__ == "__main__":
    main()

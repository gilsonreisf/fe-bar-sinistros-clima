"""Baixa e prepara os dados públicos (INMET 2025/2026 de SC e municípios de SC).

Uso: uv run python scripts/preparar_dados_publicos.py
Saídas versionadas em dados/publicos/; arquivos grandes em dados/brutos/ (fora do git).
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import pandas as pd

from dados_sinteticos.inmet import agregar_diario, ler_zip_uf

RAIZ = Path(__file__).resolve().parents[1]
BRUTOS = RAIZ / "dados/brutos"
PUBLICOS = RAIZ / "dados/publicos"
URL_INMET = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
URL_MUNICIPIOS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
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
    sc[["codigo_ibge", "municipio", "lat", "lon"]].sort_values("municipio").to_csv(PUBLICOS / "municipios_sc.csv", index=False)
    print(f"municípios de SC: {len(sc)}")

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

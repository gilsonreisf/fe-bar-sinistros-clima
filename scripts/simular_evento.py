"""Simula a chegada do pico do evento: publica os próximos lotes de avisos e documentos no Volume.

Uso:
  uv run python scripts/simular_evento.py --lotes 1                 # publica no Volume do UC
  uv run python scripts/simular_evento.py --lotes 1 --destino local:/tmp/volume
O estado (lotes já publicados) fica em _saida/_staging/publicados.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parents[1]
VOLUME = "/Volumes/sinistros_clima/landing/arquivos"


def publicar_lotes(staging: Path, quantidade: int, enviar: Callable[[Path, str], None], estado: Path) -> list[str]:
    publicados = json.loads(estado.read_text())["publicados"] if estado.exists() else []
    pendentes = [p for p in sorted(staging.glob("lote_*")) if p.is_dir() and p.name not in publicados][:quantidade]
    for lote in pendentes:
        for pasta in ("documentos", "avisos"):  # documentos primeiro: quando o aviso chega, o PDF já existe
            for arquivo in sorted((lote / pasta).iterdir()):
                enviar(arquivo, f"{pasta}/{arquivo.name}")
        publicados.append(lote.name)
        estado.write_text(json.dumps({"publicados": publicados}, indent=2))
        print(f"publicado: {lote.name}")
    return [p.name for p in pendentes]


def enviar_local(destino: Path) -> Callable[[Path, str], None]:
    def _enviar(origem: Path, relativo: str) -> None:
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(origem, alvo)
    return _enviar


def enviar_volume() -> Callable[[Path, str], None]:
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))

    def _enviar(origem: Path, relativo: str) -> None:
        with open(origem, "rb") as f:
            w.files.upload(f"{VOLUME}/{relativo}", f, overwrite=True)
    return _enviar


def main() -> None:
    p = argparse.ArgumentParser(description="Publica os próximos lotes do evento")
    p.add_argument("--lotes", type=int, default=1)
    p.add_argument("--saida", default="_saida")
    p.add_argument("--destino", default="volume", help="'volume' ou 'local:<diretório>'")
    args = p.parse_args()
    staging = RAIZ / args.saida / "_staging"
    enviar = enviar_volume() if args.destino == "volume" else enviar_local(Path(args.destino.split(":", 1)[1]))
    publicar_lotes(staging, args.lotes, enviar, staging / "publicados.json")


if __name__ == "__main__":
    main()

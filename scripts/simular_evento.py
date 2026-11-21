"""Simula a chegada do pico do evento: publica os próximos lotes de avisos e documentos no Volume.

Uso:
  uv run python scripts/simular_evento.py --lotes 1                 # publica no Volume do UC (módulo `ambiente`)
  uv run python scripts/simular_evento.py --lotes 1 --destino local:/tmp/volume
O estado (lotes já publicados) fica em _saida/_staging/publicados_<destino>.json, um arquivo por destino, e
guarda a impressão digital da geração: publicar uma geração nova no mesmo destino é recusado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from ambiente import carregar_ambiente

RAIZ = Path(__file__).resolve().parents[1]


def arquivo_estado(staging: Path, destino: str) -> Path:
    """Um arquivo de estado por destino: publicar num diretório local de teste não afeta o Volume."""
    return staging / f"publicados_{re.sub(r'[^a-z0-9]+', '_', destino.lower()).strip('_')}.json"


def impressao_geracao(saida: Path) -> str:
    """Identifica a geração pelo hash do resumo (seed, volumes e distribuições)."""
    return hashlib.sha256((saida / "resumo_geracao.json").read_bytes()).hexdigest()[:16]


def publicar_lotes(staging: Path, quantidade: int, enviar: Callable[[Path, str], None], estado: Path,
                   geracao: str | None = None, paralelo: int = 1) -> list[str]:
    anterior = json.loads(estado.read_text()) if estado.exists() else {}
    if geracao and anterior.get("geracao") and anterior["geracao"] != geracao:
        raise RuntimeError(f"a geração mudou desde a última publicação neste destino ({anterior['geracao']} → {geracao}); "
                           "limpe o destino e o estado antes de publicar a geração nova")
    publicados = anterior.get("publicados", [])
    pendentes = [p for p in sorted(staging.glob("lote_*")) if p.is_dir() and p.name not in publicados][:quantidade]
    for lote in pendentes:
        # documentos primeiro (em paralelo) e só depois os avisos: quando o aviso chega, todos os PDFs já existem
        documentos = sorted((lote / "documentos").iterdir())
        with ThreadPoolExecutor(max_workers=max(1, paralelo)) as pool:
            list(pool.map(lambda a: enviar(a, f"documentos/{a.name}"), documentos))  # list(): propaga erros
        for arquivo in sorted((lote / "avisos").iterdir()):
            enviar(arquivo, f"avisos/{arquivo.name}")
        publicados.append(lote.name)
        estado.write_text(json.dumps({"geracao": geracao or anterior.get("geracao"), "publicados": publicados}, indent=2))
        print(f"publicado: {lote.name}")
    return [p.name for p in pendentes]


def enviar_local(destino: Path) -> Callable[[Path, str], None]:
    def _enviar(origem: Path, relativo: str) -> None:
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(origem, alvo)
    return _enviar


def enviar_volume(volume: str) -> Callable[[Path, str], None]:
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))

    def _enviar(origem: Path, relativo: str) -> None:
        with open(origem, "rb") as f:
            w.files.upload(f"{volume}/{relativo}", f, overwrite=True)
    return _enviar


def main() -> None:
    p = argparse.ArgumentParser(description="Publica os próximos lotes do evento")
    p.add_argument("--lotes", type=int, default=1)
    p.add_argument("--saida", default="_saida")
    p.add_argument("--destino", default="volume", help="'volume' ou 'local:<diretório>'")
    p.add_argument("--paralelo", type=int, default=16, help="envios simultâneos de PDFs")
    args = p.parse_args()
    staging = RAIZ / args.saida / "_staging"
    if args.destino == "volume":
        destino = carregar_ambiente().volume_arquivos
        enviar = enviar_volume(destino)
    else:
        destino = str(Path(args.destino.split(":", 1)[1]).resolve())
        enviar = enviar_local(Path(destino))
    publicar_lotes(staging, args.lotes, enviar, arquivo_estado(staging, destino), impressao_geracao(RAIZ / args.saida),
                   paralelo=args.paralelo)


if __name__ == "__main__":
    main()

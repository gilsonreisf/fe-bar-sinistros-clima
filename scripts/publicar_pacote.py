"""Constrói o wheel do projeto e o publica no Volume de artefatos, numa pasta com o hash do conteúdo.

Uso: uv run python scripts/publicar_pacote.py   (imprime o caminho do wheel no Volume)
O pipeline instala esse wheel com --no-deps (D-019), porque o compute serverless do pipeline não lê os arquivos do
workspace fora das próprias fontes. A pasta com o hash garante que um wheel antigo nunca seja reaproveitado.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from ambiente import carregar_ambiente

RAIZ = Path(__file__).resolve().parents[1]


def caminho_destino(volume_artefatos: str, wheel: Path) -> str:
    sha = hashlib.sha256(wheel.read_bytes()).hexdigest()[:12]
    return f"{volume_artefatos}/{sha}/{wheel.name}"


def main() -> None:
    from databricks.sdk import WorkspaceClient

    dist = RAIZ / "dist"
    shutil.rmtree(dist, ignore_errors=True)
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(dist)], cwd=RAIZ, check=True, capture_output=True)
    (wheel,) = dist.glob("*.whl")
    destino = caminho_destino(carregar_ambiente().volume_artefatos, wheel)
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    with open(wheel, "rb") as f:
        w.files.upload(destino, f, overwrite=True)
    print(destino)


if __name__ == "__main__":
    main()

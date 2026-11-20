"""Nomes do catálogo, dos schemas e dos volumes do projeto, lidos de variáveis de ambiente.

Fonte única para scripts, SQL e (via variáveis do bundle) pipelines, jobs e app. Nenhum nome fica fixo no código.

Variáveis (veja .env.exemplo):
- FE_BAR_CATALOGO: catálogo do Unity Catalog (padrão: sinistros_clima);
- FE_BAR_PREFIXO_SCHEMA: prefixo opcional dos schemas (padrão: vazio), útil para várias instalações no mesmo catálogo.
"""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

CATALOGO_PADRAO = "sinistros_clima"
CAMADAS = ("landing", "bronze", "silver", "gold", "ml", "operacional")
_IDENTIFICADOR = re.compile(r"[a-z_][a-z0-9_]*")
_PREFIXO = re.compile(r"[a-z0-9_]*")


@dataclass(frozen=True)
class Ambiente:
    catalogo: str = CATALOGO_PADRAO
    prefixo_schema: str = ""

    def schema(self, camada: str) -> str:
        if camada not in CAMADAS:
            raise ValueError(f"camada desconhecida: {camada} (válidas: {', '.join(CAMADAS)})")
        return f"{self.prefixo_schema}{camada}"

    @property
    def volume_arquivos(self) -> str:
        return f"/Volumes/{self.catalogo}/{self.schema('landing')}/arquivos"

    @property
    def volume_restrito(self) -> str:
        return f"/Volumes/{self.catalogo}/{self.schema('ml')}/restrito"

    def variaveis_sql(self) -> dict[str, str]:
        """Valores dos placeholders ${...} usados nos arquivos .sql do projeto."""
        return {"catalogo": self.catalogo, **{f"schema_{c}": self.schema(c) for c in CAMADAS}}


def carregar_ambiente(env: Mapping[str, str] = os.environ) -> Ambiente:
    catalogo = env.get("FE_BAR_CATALOGO", CATALOGO_PADRAO)
    prefixo = env.get("FE_BAR_PREFIXO_SCHEMA", "")
    if not _IDENTIFICADOR.fullmatch(catalogo):
        raise ValueError(f"FE_BAR_CATALOGO inválido: {catalogo!r} (use letras minúsculas, dígitos e _)")
    if not _PREFIXO.fullmatch(prefixo):
        raise ValueError(f"FE_BAR_PREFIXO_SCHEMA inválido: {prefixo!r} (use letras minúsculas, dígitos e _)")
    return Ambiente(catalogo=catalogo, prefixo_schema=prefixo)

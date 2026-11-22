"""Exporta o deck HTML (deck/slides) para markdown: o texto de cada slide e as speaker notes.

O avaliador do FE Bar lê texto; o PDF do deck não leva as notes. Este arquivo leva as duas coisas.

Uso: uv run python scripts/exportar_deck_md.py [--saida deck/deck-sinistros-clima.md]
"""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DECK = RAIZ / "deck"

BLOCOS = {"p", "div", "li", "h1", "h2", "h3", "tr", "br", "blockquote", "small"}


class _Texto(HTMLParser):
    """Junta o texto visível, quebrando linha nos elementos de bloco e separando as células de tabela."""

    def __init__(self) -> None:
        super().__init__()
        self.partes: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"svg", "script", "style", "button"}:
            self._ignorar += 1
        if tag in BLOCOS:
            self.partes.append("\n")
        if tag in {"td", "th"}:
            self.partes.append(" | ")

    def handle_endtag(self, tag):
        if tag in {"svg", "script", "style", "button"}:
            self._ignorar = max(0, self._ignorar - 1)
        if tag in BLOCOS:
            self.partes.append("\n")
        if tag == "b":
            self.partes.append(" ")

    def handle_data(self, data):
        if not self._ignorar:
            self.partes.append(data)

    def texto(self) -> str:
        bruto = "".join(self.partes)
        linhas = [re.sub(r"\s+", " ", linha).strip(" |") for linha in bruto.split("\n")]
        return "\n".join(linha for linha in linhas if linha)


def _texto(html: str) -> str:
    parser = _Texto()
    parser.feed(html)
    return parser.texto()


def _slides() -> list[str]:
    manifesto = (DECK / "slides" / "manifest.js").read_text(encoding="utf-8")
    lista = json.loads(re.search(r"\[(.*?)\]", manifesto, re.S).group(0))
    return [nome for nome in lista if not nome.startswith("_")]


def exportar(saida: Path) -> int:
    titulo = re.search(r"<title>(.*?)</title>", (DECK / "index.html").read_text(encoding="utf-8")).group(1)
    linhas = [
        f"# {titulo}",
        "",
        "Exportação em texto do deck (`deck/index.html`): o conteúdo de cada slide e as speaker notes.",
        "Gerado por `scripts/exportar_deck_md.py`. O PDF do deck está em `deck/deck-sinistros-clima.pdf`.",
        "",
    ]
    nomes = _slides()
    for n, nome in enumerate(nomes, start=1):
        js = (DECK / "slides" / nome).read_text(encoding="utf-8")
        html = re.search(r"DECK\.slide\(`(.*)`\);", js, re.S).group(1)
        html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
        notas = re.search(r'<div class="notes">(.*?)</div>\s*</div>\s*$', html, re.S)
        corpo = html[: notas.start()] if notas else html
        linhas += [f"## Slide {n}", "", _texto(corpo), ""]
        if notas:
            linhas += ["**Speaker notes:**", "", _texto(notas.group(1).replace("<br>", "\n")), ""]
    saida.write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8")
    return len(nomes)


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--saida", type=Path, default=DECK / "deck-sinistros-clima.md")
    saida = args.parse_args().saida
    print(f"{exportar(saida)} slides exportados para {saida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()

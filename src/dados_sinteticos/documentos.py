"""Textos livres (descrições e laudos) e PDFs de orçamento e laudo de vistoria."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

DESCRICOES = {
    "granizo": ["A chuva de granizo quebrou várias telhas e entrou água na {comodo}.",
                "Pedras de granizo danificaram o telhado e a calha; houve goteiras na {comodo}.",
                "O granizo quebrou o vidro da janela da {comodo} e parte da cobertura da garagem."],
    "vendaval": ["O vento forte arrancou parte do telhado e derrubou o muro dos fundos.",
                 "Durante o temporal, o vendaval levou telhas e danificou o portão da garagem.",
                 "A ventania destelhou a casa e a água estragou o forro da {comodo}."],
    "danos_eletricos": ["Depois da queda de energia no temporal, a {aparelho} não ligou mais.",
                        "Um raio caiu perto de casa e queimou a {aparelho} e o roteador.",
                        "Com a oscilação de energia durante a tempestade, a {aparelho} queimou."],
    "alagamento": ["A água da chuva invadiu a casa e chegou a {altura} cm, estragando móveis.",
                   "A rua alagou e a água entrou na {comodo}, danificando o piso e o sofá.",
                   "Com a chuva forte, a casa foi alagada e perdemos móveis da {comodo}."],
}
COMODOS = ["sala", "cozinha", "garagem", "quarto", "lavanderia"]
APARELHOS = ["geladeira", "televisão", "máquina de lavar", "computador", "bomba d'água"]
CAUSA_TEXTO = {"granizo": "chuva de granizo", "vendaval": "vendaval", "danos_eletricos": "descarga elétrica",
               "alagamento": "alagamento"}
SINAIS_PREEXISTENTES = ["oxidação antiga", "infiltração antiga com bolor", "desgaste e remendos antigos",
                        "fissuras antigas na alvenaria"]


def moeda(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _escolha(rng: np.random.Generator, opcoes: list[str]) -> str:
    return opcoes[int(rng.integers(0, len(opcoes)))]


def descrever(rng: np.random.Generator, causa: str) -> str:
    return _escolha(rng, DESCRICOES[causa]).format(comodo=_escolha(rng, COMODOS), aparelho=_escolha(rng, APARELHOS),
                                                   altura=int(rng.integers(20, 90)))


def texto_laudo(rng: np.random.Generator, causa: str, data_vistoria: date, itens: list[dict], padrao: str) -> str:
    abertura = f"Vistoria realizada em {data_vistoria.strftime('%d/%m/%Y')}."
    if padrao == "dano_preexistente":
        nomes = ", ".join(i["descricao"].split(" (")[0] for i in itens if i["preexistente"])
        return (f"{abertura} Parte dos danos é compatível com {CAUSA_TEXTO[causa]}. Entretanto, observa-se "
                f"{_escolha(rng, SINAIS_PREEXISTENTES)} nos seguintes itens: {nomes}, indicando dano anterior ao evento.")
    return (f"{abertura} Os danos observados são compatíveis com {CAUSA_TEXTO[causa]} ocorrido na data informada. "
            "Não foram observados indícios de danos anteriores.")


def gerar_orcamento_pdf(caminho: Path, rng: np.random.Generator, aviso: dict, itens: list[dict], prestador: dict,
                        nome_segurado: str) -> None:
    estilos = getSampleStyleSheet()
    total = sum(i["valor_total"] for i in itens)
    data = date.fromisoformat(aviso["data_aviso"]).strftime("%d/%m/%Y")
    partes = [Paragraph(f"<b>{prestador['razao_social']}</b> CNPJ {prestador['cnpj']}", estilos["Normal"]),
              Paragraph("Orçamento de reparos", estilos["Title"]),
              Paragraph(f"Cliente: {nome_segurado} | Local: {aviso['municipio']}/SC | Data: {data}", estilos["Normal"]),
              Spacer(1, 12)]
    if rng.random() < 0.5:  # layout 1: tabela
        linhas = [["Item", "Descrição", "Qtd.", "Un.", "Valor unit.", "Total"]]
        linhas += [[str(i["seq"]), i["descricao"], str(i["quantidade"]), i["unidade"], moeda(i["valor_unitario"]),
                    moeda(i["valor_total"])] for i in itens]
        partes.append(Table(linhas))
    else:  # layout 2: texto corrido
        for i in itens:
            partes.append(Paragraph(f"{i['seq']}) {i['quantidade']} {i['unidade']} de {i['descricao']} a "
                                    f"{moeda(i['valor_unitario'])} = {moeda(i['valor_total'])}", estilos["Normal"]))
    partes += [Spacer(1, 12), Paragraph(f"<b>Total do orçamento: {moeda(total)}</b>", estilos["Normal"]),
               Paragraph("Validade: 15 dias. Pagamento a combinar.", estilos["Normal"])]
    SimpleDocTemplate(str(caminho), pagesize=A4, title=f"Orçamento {aviso['id_aviso']}").build(partes)


def gerar_laudo_pdf(caminho: Path, aviso: dict, texto: str) -> None:
    estilos = getSampleStyleSheet()
    partes = [Paragraph("Laudo de vistoria", estilos["Title"]),
              Paragraph(f"Aviso {aviso['id_aviso']} | Local: {aviso['municipio']}/SC", estilos["Normal"]),
              Spacer(1, 12), Paragraph(texto, estilos["Normal"])]
    SimpleDocTemplate(str(caminho), pagesize=A4, title=f"Laudo {aviso['id_aviso']}").build(partes)

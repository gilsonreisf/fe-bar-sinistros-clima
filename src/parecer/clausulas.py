"""Condições gerais SINTÉTICAS do seguro residencial e empresarial da seguradora fictícia do protótipo (D-022).

Não reproduzem nenhuma apólice real. Servem para o parecer citar a regra aplicada por código, o que o regulador confere.
"""
from __future__ import annotations

CLAUSULAS: dict[str, str] = {
    "CG-2.1": "Coberturas contratadas: só há indenização para as causas listadas nas coberturas da apólice "
              "(vendaval e granizo, alagamento, danos elétricos).",
    "CG-2.4": "Início de vigência: sinistros ocorridos nos primeiros 30 dias de vigência passam por análise de "
              "contratação e de preexistência antes da indenização.",
    "CG-3.1": "Vendaval e granizo: danos ao imóvel causados por ventos fortes ou queda de granizo.",
    "CG-3.2": "Alagamento: danos causados por entrada de água de chuva no imóvel.",
    "CG-3.3": "Danos elétricos: danos a instalações e equipamentos por descarga atmosférica ou variação de tensão.",
    "CG-4.1": "Franquia: o valor da franquia da cobertura é deduzido de cada indenização.",
    "CG-4.2": "Limite máximo de indenização (LMI): a indenização de cada cobertura não ultrapassa o LMI contratado.",
    "CG-5.1": "Riscos excluídos: danos preexistentes ao evento, desgaste natural e falta de manutenção.",
    "CG-6.1": "Comprovação do evento: a seguradora verifica o evento por dados meteorológicos e registros oficiais "
              "(INMET e Defesa Civil); sem comprovação, o sinistro segue para regulação.",
    "CG-7.1": "Valor dos reparos: a indenização considera preços de mercado; orçamentos acima da tabela de referência "
              "são ajustados a ela.",
    "CG-8.1": "Regulação com vistoria: indícios de irregularidade (prestador, documentos ou contratação) levam o "
              "sinistro à vistoria e à análise do regulador.",
    "CG-9.1": "Prazo: a indenização é paga em até 30 dias após a entrega da documentação completa.",
}

CLAUSULA_DA_COBERTURA = {"vendaval_granizo": "CG-3.1", "alagamento": "CG-3.2", "danos_eletricos": "CG-3.3"}


def texto_clausulas() -> str:
    return "\n".join(f"- {codigo}: {texto}" for codigo, texto in CLAUSULAS.items())

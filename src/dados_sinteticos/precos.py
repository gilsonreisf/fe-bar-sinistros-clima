"""Tabela de preços de referência de itens e serviços (inspirada no SINAPI; valores sintéticos)."""
from __future__ import annotations

import pandas as pd

TELHADO = "granizo|vendaval"
INTERNO = "granizo|vendaval|alagamento"
ELETRICO = "danos_eletricos"
ALAGAMENTO = "alagamento"

# (código, descrição, unidade, preço base em R$, causas)
ITENS_BASE = [
    ("TEL-FIB", "Telha de fibrocimento 6 mm", "m²", 38.0, TELHADO),
    ("TEL-CER", "Telha cerâmica colonial", "m²", 55.0, TELHADO),
    ("TEL-CON", "Telha de concreto", "m²", 62.0, TELHADO),
    ("TEL-MET", "Telha metálica trapezoidal", "m²", 85.0, TELHADO),
    ("TEL-POL", "Telha de policarbonato", "m²", 120.0, TELHADO),
    ("CUM", "Cumeeira", "m", 45.0, TELHADO),
    ("CAL", "Calha de chapa galvanizada", "m", 70.0, TELHADO),
    ("RUF", "Rufo de chapa galvanizada", "m", 48.0, TELHADO),
    ("MAD", "Madeiramento de telhado (reposição)", "m²", 95.0, TELHADO),
    ("MO-TEL", "Mão de obra de retelhamento", "m²", 42.0, TELHADO),
    ("LONA", "Lona de cobertura emergencial", "m²", 9.0, TELHADO),
    ("FORRO-PVC", "Forro de PVC", "m²", 58.0, INTERNO),
    ("FORRO-GES", "Forro de gesso", "m²", 75.0, INTERNO),
    ("VID-COM", "Vidro comum 4 mm", "m²", 110.0, TELHADO),
    ("VID-TEM", "Vidro temperado 8 mm", "m²", 290.0, TELHADO),
    ("JAN", "Janela de alumínio", "un", 780.0, TELHADO),
    ("PORTAO", "Portão metálico basculante", "un", 2900.0, TELHADO),
    ("TOLDO", "Toldo ou cobertura de garagem", "m²", 260.0, TELHADO),
    ("MURO", "Reconstrução de muro de alvenaria", "m²", 180.0, TELHADO),
    ("ANT", "Antena e suporte", "un", 350.0, TELHADO),
    ("PLACA", "Placa solar fotovoltaica (módulo)", "un", 1100.0, TELHADO),
    ("AQ-SOL", "Coletor de aquecedor solar", "un", 1500.0, TELHADO),
    ("CX-AGUA", "Caixa d'água 1.000 L", "un", 680.0, TELHADO),
    ("PINT-EXT", "Pintura externa", "m²", 32.0, TELHADO),
    ("GEL", "Geladeira duplex", "un", 3800.0, ELETRICO),
    ("TV", "Televisor 50 polegadas", "un", 2900.0, ELETRICO),
    ("MAQ", "Máquina de lavar roupas", "un", 2600.0, ELETRICO),
    ("MIC", "Micro-ondas", "un", 750.0, ELETRICO),
    ("COMP", "Computador desktop", "un", 3500.0, ELETRICO),
    ("AR", "Ar-condicionado split 12.000 BTU", "un", 2700.0, ELETRICO),
    ("MOTOR-PORT", "Motor de portão eletrônico", "un", 1300.0, ELETRICO),
    ("BOMBA", "Bomba d'água", "un", 900.0, ELETRICO),
    ("ROT", "Roteador e modem", "un", 420.0, ELETRICO),
    ("QUADRO", "Reparo de quadro elétrico", "un", 650.0, ELETRICO),
    ("FIA", "Reparo de fiação elétrica", "m", 28.0, ELETRICO),
    ("PISO", "Piso cerâmico (reposição)", "m²", 85.0, ALAGAMENTO),
    ("SOFA", "Sofá 3 lugares", "un", 2400.0, ALAGAMENTO),
    ("COLCHAO", "Colchão de casal", "un", 1600.0, ALAGAMENTO),
    ("ARM", "Armário de cozinha", "un", 1900.0, ALAGAMENTO),
    ("LIMP", "Limpeza e higienização pós-alagamento", "m²", 18.0, ALAGAMENTO),
    ("PINT-INT", "Pintura interna", "m²", 26.0, ALAGAMENTO),
    ("PORTA", "Porta de madeira interna", "un", 520.0, ALAGAMENTO),
]
PADROES = {"ECONOMICO": 0.65, "POPULAR": 0.80, "MEDIO": 1.00, "SUPERIOR": 1.25, "PREMIUM": 1.60}


def gerar_tabela_precos() -> pd.DataFrame:
    linhas = [
        {"codigo_item": f"{cod}-{padrao}", "descricao": f"{desc} (padrão {padrao.lower()})", "unidade": un,
         "padrao": padrao.lower(), "preco_referencia": round(preco * fator, 2), "causas": causas}
        for cod, desc, un, preco, causas in ITENS_BASE
        for padrao, fator in PADROES.items()
    ]
    return pd.DataFrame(linhas)

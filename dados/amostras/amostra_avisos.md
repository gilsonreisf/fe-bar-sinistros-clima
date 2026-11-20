# Amostras de avisos sintéticos

Exemplos gerados pelo gerador (o padrão é do gabarito e não é publicado com o aviso). Os itens são os que aparecem no PDF do orçamento.

## Padrão `legitimo_simples`

```json
{
  "id_aviso": "AV-2026-000002",
  "id_apolice": "AP-0058677",
  "cpf_segurado": "718.638.539-79",
  "data_ocorrencia": "2026-08-01",
  "data_aviso": "2026-08-01",
  "causa_declarada": "vendaval",
  "descricao": "O vento forte arrancou parte do telhado e derrubou o muro dos fundos.",
  "valor_reclamado": 3784.84,
  "canal": "app",
  "codigo_ibge": 4219705,
  "municipio": "Xaxim",
  "lat": -26.9479,
  "lon": -52.53399,
  "id_prestador": "PR-1120",
  "documentos": [
    "AV-2026-000002_orcamento.pdf"
  ]
}
```

| Item | Qtd. | Un. | Valor unit. | Total | Preço de referência |
|---|---|---|---|---|---|
| Telha de concreto (padrão medio) | 35 | m² | R$ 61,92 | R$ 2.167,20 | R$ 62,00 |
| Telha de policarbonato (padrão economico) | 13 | m² | R$ 73,08 | R$ 950,04 | R$ 78,00 |
| Placa solar fotovoltaica (módulo) (padrão economico) | 1 | un | R$ 667,60 | R$ 667,60 | R$ 715,00 |

## Padrão `orcamento_inflado`

```json
{
  "id_aviso": "AV-2026-000062",
  "id_apolice": "AP-0047013",
  "cpf_segurado": "106.668.861-30",
  "data_ocorrencia": "2026-08-07",
  "data_aviso": "2026-08-09",
  "causa_declarada": "danos_eletricos",
  "descricao": "Um raio caiu perto de casa e queimou a computador e o roteador.",
  "valor_reclamado": 37974.45,
  "canal": "corretor",
  "codigo_ibge": 4211256,
  "municipio": "Morro Grande",
  "lat": -28.79628,
  "lon": -49.71545,
  "id_prestador": "PR-1802",
  "documentos": [
    "AV-2026-000062_orcamento.pdf",
    "AV-2026-000062_laudo.pdf"
  ]
}
```

| Item | Qtd. | Un. | Valor unit. | Total | Preço de referência |
|---|---|---|---|---|---|
| Motor de portão eletrônico (padrão superior) | 1 | un | R$ 2.668,78 | R$ 2.668,78 | R$ 1.625,00 |
| Computador desktop (padrão medio) | 2 | un | R$ 6.726,03 | R$ 13.452,06 | R$ 3.500,00 |
| Roteador e modem (padrão premium) | 19 | un | R$ 1.150,19 | R$ 21.853,61 | R$ 672,00 |

**Laudo:** Vistoria realizada em 12/08/2026. Os danos observados são compatíveis com descarga elétrica ocorrido na data informada. Não foram observados indícios de danos anteriores.

## Padrão `dano_preexistente`

```json
{
  "id_aviso": "AV-2026-000063",
  "id_apolice": "AP-0024946",
  "cpf_segurado": "509.717.558-17",
  "data_ocorrencia": "2026-08-07",
  "data_aviso": "2026-08-09",
  "causa_declarada": "vendaval",
  "descricao": "A ventania destelhou a casa e a água estragou o forro da sala.",
  "valor_reclamado": 37993.39,
  "canal": "app",
  "codigo_ibge": 4211454,
  "municipio": "Nova Itaberaba",
  "lat": -26.94656,
  "lon": -52.80795,
  "id_prestador": "PR-1841",
  "documentos": [
    "AV-2026-000063_orcamento.pdf",
    "AV-2026-000063_laudo.pdf"
  ]
}
```

| Item | Qtd. | Un. | Valor unit. | Total | Preço de referência |
|---|---|---|---|---|---|
| Telha cerâmica colonial (padrão superior) | 213 | m² | R$ 68,45 | R$ 14.579,85 | R$ 68,75 |
| Caixa d'água 1.000 L (padrão medio) | 7 | un | R$ 691,10 | R$ 4.837,70 | R$ 680,00 |
| Telha cerâmica colonial (padrão economico) | 473 | m² | R$ 35,16 | R$ 16.630,68 | R$ 35,75 |
| Portão metálico basculante (padrão economico) | 1 | un | R$ 1.945,16 | R$ 1.945,16 | R$ 1.885,00 |

**Laudo:** Vistoria realizada em 12/08/2026. Parte dos danos é compatível com vendaval. Entretanto, observa-se desgaste e remendos antigos nos seguintes itens: Telha cerâmica colonial, Telha cerâmica colonial, indicando dano anterior ao evento.

# Endpoint do parecer prévio: teste ponta a ponta

Gerado em 2026-11-21 00:50 com `uv run python scripts/testar_endpoint_parecer.py`.

## Endpoint

- Nome: `sinistros-clima-parecer-dev`
- Estado: ready = `READY`, config_update = `NOT_UPDATING`
- Modelo servido: `fe_bar_sinistros_catalog.ml.parecer_sinistro` versão 1 (CPU Small, scale-to-zero: True)
- AI Gateway: inference table = `{"catalog_name": "fe_bar_sinistros_catalog", "schema_name": "ml", "table_name_prefix": "parecer", "enabled": true}`, usage tracking = `{"enabled": true}`
- Tabelas de inferência no schema: `parecer_payload`

## Pareceres devolvidos pelo endpoint

### AV-2026-000002 (legitimo_simples; esperado: pagar_integral)

- Recomendação: **pagar_integral**, valor sugerido R$ 1.784,84, confiança 0.82, status `ok`, prompt v2
- Cláusulas: CG-3.1, CG-4.1
- Motivos:
  - Cobertura de vendaval e granizo contratada e válida para a causa declarada (vendaval), com LMI de R$ 207.000,00 e franquia de R$ 2.000,00
  - Evento confirmado por dados do INMET, com estação a 18,3 km e rajada máxima de 18,7 m/s na data de ocorrência (01/08/2026); não há registro da Defesa Civil, mas a evidência climática é forte
  - Orçamento de R$ 3.784,84 com desvio de preço de -2,93% em relação à tabela de referência, abaixo do limite de 30%
  - Não há menção a dano anterior nos documentos nem alertas de qualidade
  - Apólice com 228 dias de vigência, fora do período de análise inicial de 30 dias
  - Prestador PR-1120 com participação de 0,05% nos últimos 30 dias, sem indício de concentração atípica
  - Valor líquido reclamado de R$ 1.784,84 após a franquia, dentro do LMI
  - Para conferência do regulador: o orçamento inclui um módulo de placa solar fotovoltaica, item não mencionado na descrição do aviso (telhado e muro dos fundos), e não há item referente ao muro. Isso não altera a aplicação das regras
- Latência da chamada: 7.0 s; trace `tr-87ae77590b890296d018f169a93398c5` (encontrado no experimento: True)

### AV-2026-000062 (orcamento_inflado; esperado: pagar_parcial)

- Recomendação: **pagar_parcial**, valor sugerido R$ 13.000,00, confiança 0.85, status `ok`, prompt v2
- Cláusulas: CG-7.1
- Motivos:
  - Cobertura de danos elétricos contratada (LMI de R$ 13.000,00 e franquia de R$ 300,00), com vigência há 191 dias
  - Evento comprovado pelo INMET (evidência forte, estação a cerca de 26 km), e o laudo de vistoria é compatível com descarga elétrica, sem indícios de danos anteriores
  - Orçamento de R$ 37.974,45 com desvio de 77,51% acima da tabela de referência, o que exige ajuste aos preços de referência
  - Itens com preço acima da referência: computador desktop (R$ 6.726,03 contra R$ 3.500,00), motor de portão (R$ 2.668,78 contra R$ 1.625,00) e roteador/modem (R$ 1.150,19 contra R$ 672,00)
  - O orçamento traz 19 unidades de roteador/modem e um motor de portão, itens que a descrição do aviso não menciona; recomenda-se que o regulador confira a quantidade e a pertinência
  - Mesmo pela tabela de referência, o valor líquido (R$ 13.000,00) fica no limite do LMI contratado
- Latência da chamada: 6.9 s; trace `tr-5d710417c0fc9835bb408f39e4cc22ed` (encontrado no experimento: True)

### AV-2026-000001 (sem_evento_climatico; esperado: investigar)

- Recomendação: **investigar**, valor sugerido R$ 0,00, confiança 0.85, status `ok`, prompt v2
- Cláusulas: CG-6.1
- Motivos:
  - A cobertura de vendaval e granizo está contratada e vigente (início em 02/04/2026, 121 dias desde a contratação), mas a comprovação do evento não foi obtida.
  - A estação do INMET, a cerca de 7,7 km do local, registrou 0,2 mm de chuva, rajada máxima de 7,0 m/s e granizo improvável na data da ocorrência (01/08/2026).
  - Não há registro da Defesa Civil para o município de Ilhota na data do evento, o que caracteriza evidência climática contrária ao evento declarado.
  - Conforme a CG-6.1, sem comprovação por dados meteorológicos e registros oficiais, o sinistro segue para regulação, a cargo do regulador, sem presumir irregularidade por parte do segurado.
  - O orçamento de R$ 18.738,54 está 4,27% abaixo da tabela de referência e não há menção a dano anterior. Esses pontos não alteram a recomendação, pois a regra de evidência climática contrária prevalece.
- Latência da chamada: 4.9 s; trace `tr-581b556d6c83a9bcc2882e24c41d3811` (encontrado no experimento: True)

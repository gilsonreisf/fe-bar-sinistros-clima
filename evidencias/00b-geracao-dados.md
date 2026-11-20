# Geração dos dados sintéticos

Seed `20260920`. Script: `uv run python -m dados_sinteticos.gerar`. Arquivo completo: `_saida/resumo_geracao.json`.

## Cadastros

| Entidade | Quantidade |
|---|---|
| segurados | 50.251 |
| apolices | 60.251 |
| corretores | 300 |
| prestadores | 2.000 |
| itens_preco | 210 |

## Evento (avisos de 2026)

- Avisos: **8000**, PDFs: **9705**, lotes: {1: 800, 2: 800, 3: 800, 4: 800, 5: 800, 6: 800, 7: 800, 8: 800, 9: 800, 10: 800}
- Ticket médio: **R$ 11.748,11**; avisos até o teto de fast track (R$ 5 mil): **58.9%**

### Padrão

| Valor | % |
|---|---|
| apolice_recente | 2.0% |
| dano_preexistente | 2.0% |
| legitimo_complexo | 25.0% |
| legitimo_simples | 60.0% |
| orcamento_inflado | 4.0% |
| prestador_concentrado | 1.0% |
| sem_cobertura | 3.0% |
| sem_evento_climatico | 3.0% |

### Causa

| Valor | % |
|---|---|
| alagamento | 8.9% |
| danos_eletricos | 15.9% |
| granizo | 44.8% |
| vendaval | 30.4% |

### Força da evidência esperada

| Valor | % |
|---|---|
| contraria | 2.9% |
| forte | 96.8% |
| fraca | 0.2% |

### Fonte da evidência esperada

| Valor | % |
|---|---|
| ambas | 1.0% |
| defesa_civil | 91.4% |
| inmet | 7.4% |
| nenhuma | 0.2% |

### Municípios com mais avisos

| Município | Avisos |
|---|---|
| Florianópolis | 2726 |
| Biguaçu | 2395 |
| Seara | 977 |
| Ipuaçu | 147 |
| São José do Cedro | 139 |
| Ponte Serrada | 139 |
| Santiago do Sul | 131 |
| Entre Rios | 66 |
| São Domingos | 61 |
| Anita Garibaldi | 59 |

## Histórico regulado (2025)

- Sinistros: **20000**

| Decisão final | % |
|---|---|
| investigar | 6.0% |
| pagar_integral | 81.5% |
| pagar_parcial | 9.5% |
| recusar | 3.0% |

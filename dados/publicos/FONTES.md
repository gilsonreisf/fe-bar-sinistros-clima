# Fontes dos dados públicos

| Arquivo | Fonte | Como foi produzido |
|---|---|---|
| `municipios_sc.csv` | Código, nome e coordenadas: compilação de dados do IBGE em https://github.com/kelvins/municipios-brasileiros (`csv/municipios.csv`). População: IBGE, Censo 2022, tabela 4709 (API de agregados, `servicodados.ibge.gov.br`) | `scripts/preparar_dados_publicos.py`: filtra `codigo_uf = 42` (SC) e junta a população residente pelo código IBGE (295 municípios, 7.610.361 habitantes) |
| `estacoes_inmet_sc.csv` | INMET, dados históricos das estações automáticas (https://portal.inmet.gov.br/dadoshistoricos, 2025.zip e 2026.zip) | Metadados do cabeçalho de cada CSV de estação de SC |
| `clima_sc_diario_2025.csv`, `clima_sc_diario_2026.csv` | INMET (mesmos arquivos) | `agregar_diario`: soma e máximo da chuva, rajada máxima, queda de temperatura e granizo provável; dias com menos de 12 h válidas ficam ausentes |
| `defesa_civil_sc_2026.csv` | Boletins da Defesa Civil de SC e imprensa (URL em cada linha) | Curadoria manual em 2026-11-20 (veja `docs/dados/defesa-civil-sc-2026.md`) |

Os arquivos horários completos do INMET (`dados/brutos/inmet_sc_horario_AAAA.csv`) não são versionados por causa do tamanho. Eles são recriados pelo script e enviados ao Volume `landing/arquivos/clima/`.

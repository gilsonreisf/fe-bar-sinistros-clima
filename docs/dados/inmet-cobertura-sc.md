# Cobertura dos dados do INMET em Santa Catarina (agosto e setembro)

**Data da análise:** 2026-11-20
**Fonte:** INMET, dados históricos horários das estações automáticas (`https://portal.inmet.gov.br/dadoshistoricos`).
- `2026.zip`: atualizado em 05/11/2026, cobre de 01/01/2026 a 31/10/2026, 23 estações em SC.
- `2025.zip`: ano completo, 24 estações em SC.

**Script:** `scripts/exploracao/verificar_cobertura_inmet.py`

## Resultado: agosto e setembro (1.464 horas por estação)

| Estação | 2026 precip. | 2026 rajada | 2026 chuva (mm) | 2026 rajada máx. (m/s) | 2025 precip. | 2025 rajada | 2025 chuva (mm) | 2025 rajada máx. (m/s) |
|---|---|---|---|---|---|---|---|---|
| A865 Lages | 100% | 100% | 540,8 | 16,6 | 100% | 100% | 399,4 | 18,2 |
| A868 Itajaí | 100% | 100% | 454,4 | 14,6 | 100% | 100% | 181,0 | 14,7 |
| A895 Chapecó | 100% | 100% | 467,0 | 22,5 | 100% | 100% | 359,0 | 24,5 |
| A898 Campos Novos | 87% | 87% | 523,0 | **27,6** | 97% | 96% | 352,8 | 20,7 |
| A867 Araranguá | 100% | 61% | 333,6 | 19,7 | 100% | 100% | 231,0 | 18,7 |
| A862 Rio Negrinho | 65% | 65% | 244,2 | 15,5 | 100% | 100% | 132,8 | 19,6 |
| A863 Ituporanga | 95% | 0% | 436,8 | — | 100% | 100% | 326,0 | 14,3 |
| A870 Rancho Queimado | 100% | 0% | 519,0 | — | 100% | 0% | 322,8 | — |
| A848 Dionísio Cerqueira | 100% | 0% | 438,8 | — | 61% | 0% | 202,0 | — |
| A860 Curitibanos | 0% | 100% | — | 22,6 | 51% | 100% | 20,6 | 17,9 |
| A861 Rio do Campo | 0% | 100% | — | 17,0 | 51% | 100% | 54,0 | 15,1 |
| A864 Major Vieira | 0% | 100% | — | 18,4 | 0% | 100% | — | 18,3 |
| A851 Itapoá | 9% | 9% | 0,2 | 9,9 | 100% | 100% | 220,6 | 14,6 |
| Demais estações (Florianópolis, Joaçaba, Caçador, Xanxerê etc.) | majoritariamente sem dados nos dois anos | | | | | | | |

## Conclusões

1. **2026 tem o sinal do evento.** A chuva acumulada foi bem maior que em 2025 (Itajaí 2,5×, Lages 1,4×) e há rajada de ~99 km/h em Campos Novos.
2. **A cobertura é parcial nos dois anos.** Muitas estações têm lacunas ou não medem uma das variáveis. A cobertura de 2025 é um pouco melhor, mas o ano não tem o evento.
3. **O INMET não mede granizo.** O granizo precisa ser inferido por indicadores: chuva intensa em pouco tempo, rajada forte e queda brusca de temperatura.

## Implicações para o desenho

- O vínculo entre sinistro e clima usa a **estação válida mais próxima por variável** (a mais próxima com precipitação e a mais próxima com rajada) e registra a distância.
- Sem estação válida num raio razoável, o sinistro **não é recusado**: ele recebe a marca "evidência climática fraca" e vai para o regulador. É o mesmo caso de uma notícia de 27/09/2026, em que a indenização dependia de uma estação do INMET a 40 km da casa do segurado.
- A lacuna de dados vira parte da história de qualidade de dados no pipeline (expectations do Lakeflow).

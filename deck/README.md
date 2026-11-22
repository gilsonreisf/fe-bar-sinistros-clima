# Deck: regulação inteligente de sinistros em eventos climáticos

Apresentação para a diretoria de sinistros (patrocinadora) e para a arquitetura de TI de uma seguradora patrimonial. Começa pelo resultado de negócio, mostra a demo e fecha com a proposta de PoC. Todos os slides têm speaker notes.

| Arquivo | Para quê |
|---|---|
| `deck-sinistros-clima.pptx` | O deck em PowerPoint, editável e com as speaker notes (para apresentar) |
| `deck-sinistros-clima.pdf` | O deck em PDF, um slide por página (o arquivo da submissão) |
| `deck-sinistros-clima.md` | O texto de cada slide e as speaker notes, em markdown (gerado por `scripts/exportar_deck_md.py`) |
| `faq-roleplay.md` | Guia do roleplay: roteiro com tempo, números para decorar e respostas às objeções das duas personas |
| `index.html` | O deck vivo (HTML, abre com duplo clique, sem servidor) |

## Abrir e apresentar

Abra `index.html` no navegador. Atalhos: `→` e `←` navegam, `G` mostra a visão geral, `N` as notas, `S` a visão do apresentador (com as notas sincronizadas), `L` o ponteiro e `F` a tela cheia. O slide 7 abre o app da regulação numa aba nova (o login usa o SSO do workspace).

## Exportar

No menu **Export** da barra: PDF ou Google Slides. Para regenerar os arquivos do repositório:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --no-sandbox \
  --virtual-time-budget=9000 --no-pdf-header-footer \
  --print-to-pdf="$PWD/deck/deck-sinistros-clima.pdf" "file://$PWD/deck/index.html"
uv run python scripts/exportar_deck_md.py
```

O PowerPoint sai do Google Slides (texto, tabelas e notas nativos): `python3 deck/tools/gslides/export_gslides.py --deck "$PWD/deck" --folder <id da pasta no Drive> --pptx --allow-public-images`, depois de rodar com `--preview` e consentir no compartilhamento temporário das imagens. O arquivo usa as fontes DM Sans e DM Mono; instale as de `resources/fonts/` para o PowerPoint não trocar a fonte.

## Slides

1. Capa: sinistros climáticos pagos em dias, com a IA sob controle
2. Resumo executivo
3. No pico de um evento, três problemas chegam juntos
4. Mensagem: pagar em dias quem tem direito e segurar quem não tem
5. As metas, nos KPIs da diretoria de sinistros (hoje, meta e medido)
6. Cada aviso é analisado assim que chega
7. Demonstração (abre o app; o roteiro está nas notas)
8. Resultados medidos nos lotes nunca vistos
9. R$ 2,4 milhões de ganho de referência por evento
10. A composição do ganho
11. O custo medido por sinistro
12. A IA trabalha sob o controle do regulador
13. Seção técnica: do arquivo à decisão, numa plataforma só
14. Arquitetura integrada sob o Unity Catalog
15. Integração, segurança e LGPD, escala
16. PoC em 6 semanas
17. Próximos passos
18. Encerramento
19. Apêndice
20. Perguntas da diretoria de sinistros
21. Perguntas da arquitetura de TI
22. Decisões de arquitetura e trade-offs
23. De onde vêm os números

## Os números

Os números medidos vêm das evidências em `../evidencias/` (teste final em lotes nunca vistos, custo no faturamento, Genie). Os ganhos em reais e as metas são **premissas de referência nossas, a calibrar na PoC** (`../docs/negocio/02-ganhos-kpis-e-personas.md`). Os dados são sintéticos sobre fontes públicas; nenhum dado de cliente.

## Edição

Os slides ficam em `slides/*.js`, na ordem de `slides/manifest.js`. O tema está nos tokens `:root` de `assets/style.css`. As verificações de layout e de texto estão em `tools/verify/` (`verify_deck.py`, `audit_layout.py` e `deslop_lint.py`). O deck foi feito com o template de slides da Databricks (skill `dbx-slides`).

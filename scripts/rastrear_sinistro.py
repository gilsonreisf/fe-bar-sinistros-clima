"""Rastreio ponta a ponta de um sinistro (spec 12; evidencias/08-rastreio-ponta-a-ponta.md): o mesmo aviso em cada
camada, do arquivo que chegou ao Volume até a decisão do regulador que voltou ao Unity Catalog.

Sem argumento, escolhe o caso mais recente decidido por um regulador de teste (identidade fictícia; nenhum e-mail real
entra na evidência). O CPF aparece só mascarado.

Uso: uv run python scripts/rastrear_sinistro.py [id_aviso]
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

from ambiente import carregar_ambiente

RAIZ = Path(__file__).resolve().parents[1]


def _tabela(colunas: list[str], linhas: list[list]) -> list[str]:
    if not linhas:
        return ["(nenhuma linha)", ""]
    corpo = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    corpo += ["| " + " | ".join("" if v is None else str(v).replace("|", "/")[:300] for v in l) + " |" for l in linhas]
    return corpo + [""]


def consultas(amb, id_aviso: str) -> list[tuple[str, str, str]]:
    c, b, s, g, o, m = (amb.catalogo, amb.schema("bronze"), amb.schema("silver"), amb.schema("gold"),
                        amb.schema("operacional"), amb.schema("ml"))
    a = f"'{id_aviso}'"
    return [
        ("1. Chegada (Volume → bronze, Auto Loader)", "O aviso entrou pelo arquivo do lote, com metadados de ingestão.",
         f"SELECT id_aviso, regexp_extract(_arquivo, '[^/]+$', 0) AS arquivo, _ingerido_em, causa_declarada, valor_reclamado, "
         f"size(documentos) AS documentos FROM {c}.{b}.avisos WHERE id_aviso = {a}"),
        ("2. Documentos (bronze → silver: `ai_parse_document` + `ai_extract`)",
         "Cada PDF lido e os campos extraídos por IA, ainda dentro do pipeline.",
         f"SELECT tipo_documento, regexp_extract(_arquivo, '[^/]+$', 0) AS arquivo, legivel, valor_total, "
         f"menciona_dano_anterior, size(itens) AS itens, erro_extracao FROM {c}.{s}.documentos_extraidos WHERE id_aviso = {a}"),
        ("3. Cruzamentos (silver: apólice, clima INMET/Defesa Civil, preço, prestador)",
         "Fatos que o regulador conferiria à mão, já calculados.",
         f"SELECT cobertura_valida, dentro_vigencia, dias_desde_contratacao, forca_evidencia_climatica, fonte_evidencia, "
         f"round(desvio_preco_pct, 4) AS desvio_preco, participacao_prestador_30d, to_json(alertas_qualidade) AS alertas "
         f"FROM {c}.{s}.sinistros_enriquecidos WHERE id_aviso = {a}"),
        ("4. Score de suspeita (modelo `ml.modelo_suspeita@champion`) e parecer prévio (LLM com prompt versionado)",
         "Saída do job do evento no gold, com versões e trace do MLflow.",
         f"SELECT round(score_suspeita, 4) AS score, fatores_suspeita, versao_modelo, recomendacao_ia, valor_sugerido, "
         f"confianca, status_parecer, versao_prompt, llm, trace_id FROM {c}.{g}.sinistros_analisados WHERE id_aviso = {a}"),
        ("5. Fast track, prioridade e posição na fila (gold)", "Por que o caso não saiu automático e onde ele entrou na fila.",
         f"SELECT a.fast_track, to_json(a.bloqueios_fast_track) AS bloqueios, round(a.prioridade, 4) AS prioridade, "
         f"f.posicao_fila FROM {c}.{g}.sinistros_analisados a LEFT JOIN {c}.{g}.fila_regulacao f USING (id_aviso) "
         f"WHERE a.id_aviso = {a}"),
        ("6. Consumo governado (visão de detalhe com CPF mascarado)", "O que o app mostra ao regulador.",
         f"SELECT id_aviso, cpf_segurado, municipio, recomendacao_ia FROM {c}.{g}.sinistro_detalhe WHERE id_aviso = {a}"),
        ("7. Decisão do regulador de volta ao UC (Lakebase → Lakehouse Sync)",
         "A decisão gravada no Postgres (aqui por um regulador de teste de `scripts/testar_lakebase.py`, com as mesmas "
         "consultas do app), já como histórico SCD2 no Unity Catalog.",
         f"SELECT _pg_change_type, regulador, decisao, recomendacao_ia, concordou_com_ia, valor_aprovado, criado_em "
         f"FROM {c}.{o}.lb_decisoes_regulador_history WHERE id_aviso = {a} ORDER BY criado_em"),
        ("8. Lineage registrado pelo Unity Catalog para as tabelas do caminho", "Origem → destino, por tipo de entidade.",
         f"SELECT DISTINCT source_table_full_name AS origem, target_table_full_name AS destino, entity_type AS por "
         f"FROM system.access.table_lineage WHERE event_date >= DATE'2026-11-20' "
         f"AND target_table_full_name IN ('{c}.{s}.sinistros_enriquecidos', '{c}.{s}.entrada_parecer', "
         f"'{c}.{g}.sinistros_analisados', '{c}.{g}.sinistros_analisados_lb', '{c}.{o}.lb_decisoes_regulador_history') "
         f"AND source_table_full_name IS NOT NULL ORDER BY destino, origem"),
        ("9. Uso do modelo servido (inference table do AI Gateway)",
         "Cada chamada ao endpoint (teste do endpoint e \"Reanalisar com IA\" no app) fica auditada; a tabela chega "
         "com atraso de até uma hora. O parecer em lote chama o LLM direto (D-023) e fica no trace do MLflow.",
         f"SELECT count(*) AS requisicoes, min(request_time) AS primeira, max(request_time) AS ultima "
         f"FROM {c}.{m}.parecer_payload"),
    ]


def main(id_aviso: str | None = None, saida: str = "evidencias/08-rastreio-ponta-a-ponta.md") -> None:
    from databricks.sdk import WorkspaceClient

    from executar_sql import executar
    from lakebase.operacao import conectar

    w, amb = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")), carregar_ambiente()
    wh = os.environ["FE_BAR_WAREHOUSE_ID"]
    projeto = os.environ.get("FE_BAR_LAKEBASE_PROJETO", "sinistros-clima")
    if not id_aviso:
        _, linhas = executar(w, wh, f"SELECT id_aviso FROM {amb.catalogo}.{amb.schema('operacional')}."
                                    "lb_decisoes_regulador_history WHERE regulador LIKE 'regulador_teste_%' "
                                    "ORDER BY criado_em DESC LIMIT 1")
        id_aviso = linhas[0][0]
    md = [f"# Rastreio ponta a ponta do sinistro {id_aviso}", "",
          f"Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M')} com `uv run python scripts/rastrear_sinistro.py`. "
          "O mesmo aviso em cada camada: Lakeflow (bronze e silver) → Unity Catalog → ML e GenAI → gold → Lakebase "
          "→ app → de volta ao UC.", ""]
    for titulo, explicacao, sql in consultas(amb, id_aviso):
        colunas, linhas = executar(w, wh, sql)
        md += [f"## {titulo}", "", explicacao, ""] + _tabela(colunas, linhas)
        if titulo.startswith("6."):
            with conectar(w, projeto) as con:
                fila = con.execute(f"SELECT id_aviso, fast_track, round(prioridade::numeric, 4), recomendacao_ia FROM "
                                   f"{amb.schema('gold')}.sinistros_analisados_lb WHERE id_aviso = %s", (id_aviso,)).fetchall()
                atrib = con.execute("SELECT regulador, status, atribuido_em FROM operacao.atribuicoes WHERE id_aviso = %s",
                                    (id_aviso,)).fetchall()
            md += ["## 6b. Operação no Lakebase (synced table do gold e atribuição)", "",
                   "A fila lida em baixa latência pelo app e quem assumiu o caso.", ""]
            md += _tabela(["id_aviso", "fast_track", "prioridade", "recomendacao_ia"], [list(x) for x in fila])
            md += _tabela(["regulador", "status", "atribuido_em"], [list(x) for x in atrib])
    texto = "\n".join(md) + "\n"
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", texto)
    if emails:  # nenhuma identidade real na evidência
        linhas_com = emails[:3]
        raise SystemExit(f"a evidência contém um e-mail; escolha um caso decidido por um regulador de teste: {linhas_com}")
    (RAIZ / saida).write_text(texto, encoding="utf-8")
    print(f"{saida} gerado para {id_aviso}")


if __name__ == "__main__":
    main(*sys.argv[1:])

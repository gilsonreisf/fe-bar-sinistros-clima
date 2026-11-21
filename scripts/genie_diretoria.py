"""Genie "Sinistros Clima — Diretoria" (spec 8): definição do espaço (fontes, instruções, perguntas de exemplo e
benchmarks), criação ou atualização idempotente e avaliação dos benchmarks, com a evidência em evidencias/06-genie.md.

As fontes são as metric views do gold (métricas definidas uma vez no UC; D-025) e a fila de regulação (linha a linha,
para "quais sinistros"). Nenhum nome fixo: catálogo e schemas vêm do `.env` (D-016).

Uso: uv run python scripts/genie_diretoria.py [criar|avaliar|tudo] [eval_run_id já iniciado]   (padrão: tudo)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TITULO = "Sinistros Clima — Diretoria"
DESCRICAO = ("Perguntas da diretoria de sinistros sobre o evento climático: volume e exposição, fast track, suspeita de "
             "fraude, recomendações da IA e concordância dos reguladores. Dados sintéticos.")


def _id(texto: str) -> str:
    """ID estável (32 hex) a partir do texto: reaplicar o script não cria itens novos."""
    return hashlib.md5(texto.encode("utf-8")).hexdigest()  # noqa: S324 (identificador, não segurança)


def consultas(catalogo: str, schema_gold: str) -> dict[str, list[tuple[str, str]]]:
    sm, rm, fila = (f"{catalogo}.{schema_gold}.sinistros_metrics", f"{catalogo}.{schema_gold}.regulacao_metrics",
                    f"{catalogo}.{schema_gold}.fila_regulacao")
    benchmarks = [
        ("Quantos avisos de sinistro recebemos no evento?", f"SELECT MEASURE(`Avisos`) AS avisos FROM {sm}"),
        ("Qual a exposição total do evento, em valor reclamado?",
         f"SELECT MEASURE(`Valor reclamado`) AS valor_reclamado FROM {sm}"),
        ("Qual o percentual de sinistros liberados no fast track?",
         f"SELECT MEASURE(`Percentual de fast track`) AS pct_fast_track FROM {sm}"),
        ("Quais os 5 municípios com maior valor reclamado?",
         f"SELECT `Município`, MEASURE(`Valor reclamado`) AS valor_reclamado FROM {sm} GROUP BY ALL "
         "ORDER BY valor_reclamado DESC LIMIT 5"),
        ("Quantos avisos temos por causa declarada?",
         f"SELECT `Causa declarada`, MEASURE(`Avisos`) AS avisos FROM {sm} GROUP BY ALL ORDER BY avisos DESC"),
        ("Quanto a IA sugeriu ajustar por evidência nos sinistros com cobertura?",
         f"SELECT MEASURE(`Ajuste por evidência sugerido pela IA`) AS ajuste_sugerido FROM {sm}"),
        ("Quantos sinistros são suspeitos e quanto eles reclamam?",
         f"SELECT MEASURE(`Sinistros suspeitos`) AS suspeitos, MEASURE(`Valor reclamado suspeito`) AS valor_suspeito "
         f"FROM {sm}"),
        ("Quantos pareceres a IA deu de cada tipo de recomendação?",
         f"SELECT `Recomendação da IA`, MEASURE(`Avisos`) AS avisos FROM {sm} GROUP BY ALL ORDER BY avisos DESC"),
        ("Qual o percentual de fast track em cada lote?",
         f"SELECT `Lote`, MEASURE(`Percentual de fast track`) AS pct_fast_track FROM {sm} GROUP BY ALL ORDER BY `Lote`"),
        ("Quantos sinistros foram encaminhados ao regulador?",
         f"SELECT MEASURE(`Encaminhados ao regulador`) AS encaminhados FROM {sm}"),
        ("Quanto já foi liberado pelo fast track?",
         f"SELECT MEASURE(`Valor liberado no fast track`) AS valor_liberado FROM {sm}"),
        ("Qual a taxa de concordância dos reguladores com a IA?",
         f"SELECT MEASURE(`Concordância com a IA`) AS concordancia FROM {rm}"),
        ("Quais são os 10 sinistros mais prioritários da fila?",
         f"SELECT posicao_fila, id_aviso, municipio, causa_declarada, valor_reclamado, score_suspeita, recomendacao_ia "
         f"FROM {fila} WHERE posicao_fila <= 10 ORDER BY posicao_fila"),
        ("Como se divide a exposição entre residencial e empresarial?",
         f"SELECT `Ramo`, MEASURE(`Valor reclamado`) AS valor_reclamado FROM {sm} "
         "GROUP BY ALL ORDER BY valor_reclamado DESC"),
        ("Quantos sinistros não têm evidência climática forte?",
         f"SELECT MEASURE(`Avisos`) AS avisos FROM {sm} WHERE `Força da evidência climática` <> 'forte'"),
        ("Qual o score médio de suspeita por causa declarada?",
         f"SELECT `Causa declarada`, MEASURE(`Score médio de suspeita`) AS score_medio FROM {sm} GROUP BY ALL "
         "ORDER BY score_medio DESC"),
    ]
    exemplos = [  # instrutivos, diferentes dos benchmarks
        ("Qual o valor reclamado e o sugerido pela IA nos sinistros de alta suspeita, por município?",
         f"SELECT `Município`, MEASURE(`Avisos`) AS avisos, MEASURE(`Valor reclamado`) AS valor_reclamado, "
         f"MEASURE(`Valor sugerido pela IA`) AS valor_sugerido FROM {sm} WHERE `Faixa de suspeita` = 'alta' "
         "GROUP BY ALL ORDER BY valor_reclamado DESC"),
        ("Como evoluíram os avisos e o fast track por dia de aviso?",
         f"SELECT `Data do aviso`, MEASURE(`Avisos`) AS avisos, MEASURE(`Sinistros no fast track`) AS fast_track "
         f"FROM {sm} GROUP BY ALL ORDER BY `Data do aviso`"),
        ("Em que recomendações os reguladores mais divergem da IA?",
         f"SELECT `Recomendação da IA`, `Decisão do regulador`, MEASURE(`Decisões`) AS decisoes FROM {rm} "
         "GROUP BY ALL ORDER BY decisoes DESC"),
    ]
    return {"benchmarks": benchmarks, "exemplos": exemplos}


INSTRUCOES = [
    "Responda sempre em português do Brasil, com valores em reais (R$) e percentuais com uma casa decimal.",
    "Use as metric views para qualquer número agregado: sinistros_metrics (avisos, exposição, fast track, suspeita e "
    "recomendações da IA) e regulacao_metrics (decisões dos reguladores e concordância com a IA). Consulte as medidas com "
    "MEASURE(`nome da medida`) e agrupe com GROUP BY ALL; nunca use SELECT * nas metric views.",
    "Para 'os N maiores' ou 'top N', ordene pela medida (ORDER BY ... DESC) e use LIMIT N; não use RANK.",
    "Use fila_regulacao só para listar sinistros um a um (ex.: os mais prioritários), ordenando por posicao_fila.",
    "A recomendação da IA é um parecer prévio: a decisão final é sempre do regulador. Para 'economia', 'pagamento "
    "indevido evitado' ou 'ajuste', use a medida 'Ajuste por evidência sugerido pela IA' e diga que é uma sugestão, "
    "sujeita à decisão do regulador; franquia, LMI e recusa por falta de cobertura não entram nela.",
    "Encaminhados ao regulador = fora do fast track; quantos já foram decididos está em regulacao_metrics.",
    "Fast track = sinistro liberado sem fila: valor até R$ 5 mil, cobertura válida, evidência climática forte, score de "
    "suspeita abaixo de 0,2 e parecer de pagamento integral. Suspeito = score de suspeita >= 0,2.",
    "Exposição = valor reclamado. Lote = grupo de chegada dos avisos (1 a 10) ao longo dos dias do evento.",
    "Dados pessoais de segurados (CPF, nome, telefone) não estão neste espaço, por LGPD; se pedirem, explique isso. "
    "A dimensão Regulador identifica o funcionário que decidiu, para a supervisão.",
]
PERGUNTAS_UI = [
    "Qual a exposição total do evento e quanto já foi liberado no fast track?",
    "Quais municípios concentram mais sinistros suspeitos?",
    "Quanto a IA sugeriu ajustar por evidência?",
    "Qual a concordância dos reguladores com a IA?",
    "Quais são os sinistros mais prioritários da fila agora?",
]


def montar_espaco(catalogo: str, schema_gold: str) -> dict:
    q = consultas(catalogo, schema_gold)
    g = f"{catalogo}.{schema_gold}"
    benchmarks = sorted(({"id": _id("b:" + p), "question": [p], "answer": [{"format": "SQL", "content": [s]}]}
                         for p, s in q["benchmarks"]), key=lambda x: x["id"])
    return {
        "version": 2,
        "config": {"sample_questions": sorted(({"id": _id("q:" + p), "question": [p]} for p in PERGUNTAS_UI),
                                              key=lambda x: x["id"])},
        "data_sources": {
            "tables": [{"identifier": f"{g}.fila_regulacao", "column_configs": sorted([
                {"column_name": "municipio", "enable_format_assistance": True, "enable_entity_matching": True},
                {"column_name": "causa_declarada", "enable_format_assistance": True, "enable_entity_matching": True},
                {"column_name": "recomendacao_ia", "enable_format_assistance": True, "enable_entity_matching": True},
            ], key=lambda c: c["column_name"])}],
            "metric_views": sorted([{"identifier": f"{g}.regulacao_metrics"}, {"identifier": f"{g}.sinistros_metrics"}],
                                   key=lambda t: t["identifier"]),
        },
        "instructions": {
            "text_instructions": [{"id": _id("instrucoes"), "content": [linha + "\n" for linha in INSTRUCOES]}],
            "example_question_sqls": sorted(({"id": _id("e:" + p), "question": [p], "sql": [s]}
                                             for p, s in q["exemplos"]), key=lambda x: x["id"]),
        },
        "benchmarks": {"questions": benchmarks},
    }


def _cli(*args: str, json_body: dict | None = None) -> dict:
    cmd = ["databricks", *args, "-o", "json", "--profile", os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")]
    if json_body is not None:
        cmd += ["--json", json.dumps(json_body, ensure_ascii=False)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:2])}: {r.stderr.strip()[:800]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def _space_id() -> str | None:
    espacos = _cli("genie", "list-spaces").get("spaces", [])
    return next((e["space_id"] for e in espacos if e.get("title") == TITULO), None)


def criar(amb) -> str:
    espaco = json.dumps(montar_espaco(amb.catalogo, amb.schema("gold")), ensure_ascii=False)
    pasta = os.environ.get("FE_BAR_PASTA_GENIE", "/Workspace/Shared/sinistros_clima/dev")
    sid = _space_id()
    if sid:
        _cli("genie", "update-space", sid, json_body={"serialized_space": espaco, "title": TITULO,
                                                      "description": DESCRICAO})
        print(f"Genie atualizado: {sid}")
    else:
        subprocess.run(["databricks", "workspace", "mkdirs", pasta, "--profile",
                        os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar")], check=True)
        sid = _cli("genie", "create-space", json_body={
            "warehouse_id": os.environ["FE_BAR_WAREHOUSE_ID"], "title": TITULO, "description": DESCRICAO,
            "parent_path": pasta, "serialized_space": espaco})["space_id"]
        print(f"Genie criado: {sid}")
    return sid


def avaliar(amb, sid: str, rid: str | None = None, saida: str = "evidencias/06-genie.md") -> None:
    """Roda todos os benchmarks (corpo vazio = todas as perguntas) ou acompanha uma execução já iniciada (`rid`)."""
    if not sid:
        raise RuntimeError(f"espaço Genie '{TITULO}' não encontrado; rode primeiro com 'criar'")
    if not rid:
        rid = _cli("genie", "genie-create-eval-run", sid, json_body={})["eval_run_id"]
    print(f"avaliação {rid} em andamento")
    while True:
        estado = _cli("genie", "genie-get-eval-run", sid, rid)
        if estado.get("eval_run_status") in ("DONE", "FAILED", "CANCELLED"):
            break
        time.sleep(15)
    resultados = _cli("genie", "genie-list-eval-results", sid, rid).get("eval_results", [])
    perguntas = {b["id"]: b["question"][0] for b in montar_espaco(amb.catalogo, amb.schema("gold"))["benchmarks"]["questions"]}
    linhas = []
    for r in resultados:
        det = _cli("genie", "genie-get-eval-result-details", sid, rid, r["result_id"])
        sql = ""
        try:
            sql = det["actual_response"][0]["response"]
        except (KeyError, IndexError, TypeError):
            pass
        linhas.append((perguntas.get(r.get("benchmark_question_id"), r.get("benchmark_question_id")),
                       r.get("assessment") or det.get("assessment"), " ".join(str(sql).split())[:400],
                       "; ".join(det.get("assessment_reasons") or r.get("assessment_reasons") or [])))
    certos = sum(1 for _, a, _, _ in linhas if str(a).upper() == "GOOD")
    quando = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# Genie \"{TITULO}\": benchmarks", "",
          f"Gerado em {quando} com `uv run python scripts/genie_diretoria.py`, pela avaliação de benchmarks do Genie "
          "(modo chat: compara o resultado do SQL gerado com o do SQL de referência).", "",
          "- Fontes: metric views `sinistros_metrics` e `regulacao_metrics` e a visão `fila_regulacao`, todas do gold.",
          f"- Instruções de negócio: {len(INSTRUCOES)} regras; {len(consultas(amb.catalogo, amb.schema('gold'))['exemplos'])} "
          "exemplos de SQL (diferentes dos benchmarks).",
          f"- **Resultado: {certos} de {len(linhas)} benchmarks corretos** (status da execução: "
          f"{estado.get('eval_run_status')}).", "",
          "| pergunta | avaliação | SQL gerado pelo Genie | motivo |", "|---|---|---|---|"]
    md += [f"| {p} | {a} | `{s}` | {m} |" for p, a, s, m in linhas]
    (RAIZ / saida).write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{certos}/{len(linhas)} corretos → {saida}")


def main(acao: str = "tudo", eval_run_id: str | None = None) -> None:
    from ambiente import carregar_ambiente

    amb = carregar_ambiente()
    sid = criar(amb) if acao in ("criar", "tudo") else _space_id()
    if acao in ("avaliar", "tudo"):
        avaliar(amb, sid, eval_run_id)


if __name__ == "__main__":
    main(*sys.argv[1:])

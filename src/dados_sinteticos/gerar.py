"""Orquestra a geração completa dos dados sintéticos e grava o layout de saída (veja o plano, tarefa 1.9).

Uso: uv run python -m dados_sinteticos.gerar --saida _saida --escala 1.0
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from dados_sinteticos import config
from dados_sinteticos.cadastros import (
    gerar_apolices, gerar_corretores, gerar_prestadores, gerar_segurados, nova_faker, pesos_carteira,
)
from dados_sinteticos.documentos import gerar_laudo_pdf, gerar_orcamento_pdf, moeda
from dados_sinteticos.precos import gerar_tabela_precos
from dados_sinteticos.publicos import carregar_clima_diario, carregar_defesa_civil, carregar_estacoes, carregar_municipios_sc
from dados_sinteticos.sinistros import ContextoGeracao, gerar_evento, gerar_historico

RAIZ = Path(__file__).resolve().parents[2]


@dataclass
class Volumes:
    corretores: int = config.N_CORRETORES
    prestadores: int = config.N_PRESTADORES
    segurados: int = config.N_SEGURADOS
    apolices: int = config.N_APOLICES
    historico: int = config.N_HISTORICO
    evento: int = config.N_AVISOS_EVENTO
    lotes: int = config.N_LOTES

    def escalar(self, fator: float) -> "Volumes":
        def e(x: int, minimo: int) -> int:
            return max(minimo, int(round(x * fator)))
        return Volumes(corretores=e(self.corretores, 20), prestadores=e(self.prestadores, 100), segurados=e(self.segurados, 500),
                       apolices=e(self.apolices, 600), historico=e(self.historico, 500), evento=e(self.evento, 50), lotes=self.lotes)


def _csv(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, index=False)


def _distribuicao(serie: pd.Series) -> dict:
    return {str(k): round(float(v), 4) for k, v in serie.value_counts(normalize=True).sort_index().items()}


def gerar(publicos_dir: Path, brutos_dir: Path | None, saida: Path, volumes: Volumes, seed: int = config.SEED) -> dict:
    if saida.exists():
        shutil.rmtree(saida)
    rng, fk = np.random.default_rng(seed), nova_faker(seed)
    municipios = carregar_municipios_sc(publicos_dir / "municipios_sc.csv")
    estacoes = carregar_estacoes(publicos_dir / "estacoes_inmet_sc.csv")
    clima_2025 = carregar_clima_diario(publicos_dir / "clima_sc_diario_2025.csv")
    clima_2026 = carregar_clima_diario(publicos_dir / "clima_sc_diario_2026.csv")
    dc = carregar_defesa_civil(publicos_dir / "defesa_civil_sc_2026.csv", municipios)
    precos = gerar_tabela_precos()
    corretores = gerar_corretores(fk, volumes.corretores)
    prestadores = gerar_prestadores(fk, volumes.prestadores)
    segurados = gerar_segurados(fk, rng, municipios, pesos_carteira(municipios, dc, config.FRACAO_CARTEIRA_UNIFORME), volumes.segurados)
    apolices, coberturas = gerar_apolices(rng, segurados, corretores, volumes.apolices, *config.INICIO_VIGENCIA_CARTEIRA)

    ctx_hist = ContextoGeracao(rng, fk, municipios, estacoes, clima_2025, precos, prestadores, config.JANELA_HISTORICO_2025)
    historico, itens_hist = gerar_historico(ctx_hist, volumes.historico)
    ctx_ev = ContextoGeracao(rng, fk, municipios, estacoes, clima_2026, precos, prestadores, config.JANELA_EVENTO_2026, dc)
    ev = gerar_evento(ctx_ev, segurados, apolices, coberturas, corretores, volumes.evento, volumes.lotes)

    land = saida / "landing"
    _csv(pd.concat([segurados, ev.segurados_extra], ignore_index=True), land / "apolices/segurados.csv")
    _csv(pd.concat([apolices, ev.apolices_extra], ignore_index=True), land / "apolices/apolices.csv")
    _csv(pd.concat([coberturas, ev.coberturas_extra], ignore_index=True), land / "apolices/apolices_coberturas.csv")
    _csv(corretores, land / "apolices/corretores.csv")
    _csv(precos, land / "referencias/precos_referencia.csv")
    _csv(prestadores, land / "referencias/prestadores.csv")
    for nome in ("municipios_sc.csv", "estacoes_inmet_sc.csv", "defesa_civil_sc_2026.csv"):
        (land / "referencias").mkdir(parents=True, exist_ok=True)
        shutil.copy(publicos_dir / nome, land / "referencias" / nome)
    if brutos_dir is not None:
        (land / "clima").mkdir(parents=True, exist_ok=True)
        for ano in (2025, 2026):
            shutil.copy(brutos_dir / f"inmet_sc_horario_{ano}.csv", land / "clima" / f"inmet_sc_horario_{ano}.csv")
    _csv(historico, land / "historico/historico_sinistros_2025.csv")
    _csv(itens_hist, land / "historico/historico_itens_2025.csv")
    _csv(ev.gabarito, saida / "restrito/gabarito_evento_2026.csv")
    _csv(ev.itens, saida / "restrito/gabarito_itens_evento_2026.csv")

    prest = prestadores.set_index("id_prestador")
    itens_por_aviso = {a: g.to_dict("records") for a, g in ev.itens.groupby("id_aviso")}
    publicas = [c for c in ev.avisos.columns if not c.startswith("_") and c != "lote"]
    for lote, grupo in ev.avisos.groupby("lote"):
        base = saida / "_staging" / f"lote_{lote:02d}"
        (base / "avisos").mkdir(parents=True)
        (base / "documentos").mkdir(parents=True)
        with open(base / "avisos" / f"avisos_lote_{lote:02d}.jsonl", "w", encoding="utf-8") as f:
            for a in grupo.to_dict("records"):
                f.write(json.dumps({k: a[k] for k in publicas}, ensure_ascii=False) + "\n")
                gerar_orcamento_pdf(base / "documentos" / a["documentos"][0], rng, a, itens_por_aviso[a["id_aviso"]],
                                    prest.loc[a["id_prestador"]].to_dict(), a["_nome_segurado"])
                if len(a["documentos"]) > 1:
                    gerar_laudo_pdf(base / "documentos" / a["documentos"][1], a, a["_texto_laudo"])

    resumo = {
        "seed": seed, "volumes": asdict(volumes),
        "cadastros": {"segurados": len(segurados) + len(ev.segurados_extra), "apolices": len(apolices) + len(ev.apolices_extra),
                      "corretores": len(corretores), "prestadores": len(prestadores), "itens_preco": len(precos)},
        "historico": {"sinistros": len(historico), "decisao_final": _distribuicao(historico["decisao_final"]),
                      "motivo_decisao": _distribuicao(historico["motivo_decisao"])},
        "evento": {"avisos": len(ev.avisos), "documentos_pdf": int(ev.avisos["documentos"].map(len).sum()),
                   "lotes": {int(k): int(v) for k, v in ev.avisos["lote"].value_counts().sort_index().items()},
                   "ticket_medio_rs": round(float(ev.avisos["valor_reclamado"].mean()), 2),
                   "pct_ate_teto_fast_track": round(float((ev.avisos["valor_reclamado"] <= config.TETO_FAST_TRACK_RS).mean()), 4),
                   "padrao": _distribuicao(ev.gabarito["padrao"]), "causa": _distribuicao(ev.avisos["causa_declarada"]),
                   "forca_evidencia": _distribuicao(ev.gabarito["forca_evidencia_esperada"]),
                   "fonte_evidencia": _distribuicao(ev.gabarito["fonte_evidencia_esperada"]),
                   "top_municipios": {str(k): int(v) for k, v in ev.avisos["municipio"].value_counts().head(10).items()}},
    }
    (saida / "resumo_geracao.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    resumo["_amostras"] = _amostras(ev, itens_por_aviso)
    return resumo


def _amostras(ev, itens_por_aviso) -> list[dict]:
    escolhidos = []
    for padrao in ("legitimo_simples", "orcamento_inflado", "dano_preexistente"):
        linhas = ev.avisos[ev.avisos["_padrao"] == padrao]
        if not linhas.empty:
            a = linhas.iloc[0].to_dict()
            escolhidos.append({"padrao": padrao, "aviso": {k: a[k] for k in ev.avisos.columns if not k.startswith("_") and k != "lote"},
                               "itens": itens_por_aviso[a["id_aviso"]], "laudo": a["_texto_laudo"]})
    return escolhidos


def renderizar_resumo_md(resumo: dict) -> str:
    e = resumo["evento"]
    linhas = ["# Geração dos dados sintéticos", "",
              f"Seed `{resumo['seed']}`. Script: `uv run python -m dados_sinteticos.gerar`. Arquivo completo: `_saida/resumo_geracao.json`.", "",
              "## Cadastros", "", "| Entidade | Quantidade |", "|---|---|"]
    linhas += [f"| {k} | {v:,} |".replace(",", ".") for k, v in resumo["cadastros"].items()]
    linhas += ["", "## Evento (avisos de 2026)", "", f"- Avisos: **{e['avisos']}**, PDFs: **{e['documentos_pdf']}**, lotes: {e['lotes']}",
               f"- Ticket médio: **{moeda(e['ticket_medio_rs'])}**; avisos até o teto de fast track (R$ 5 mil): **{e['pct_ate_teto_fast_track']:.1%}**", ""]
    for titulo, chave in (("Padrão", "padrao"), ("Causa", "causa"), ("Força da evidência esperada", "forca_evidencia"),
                          ("Fonte da evidência esperada", "fonte_evidencia")):
        linhas += [f"### {titulo}", "", "| Valor | % |", "|---|---|"] + [f"| {k} | {v:.1%} |" for k, v in e[chave].items()] + [""]
    linhas += ["### Municípios com mais avisos", "", "| Município | Avisos |", "|---|---|"]
    linhas += [f"| {k} | {v} |" for k, v in e["top_municipios"].items()]
    h = resumo["historico"]
    linhas += ["", "## Histórico regulado (2025)", "", f"- Sinistros: **{h['sinistros']}**", "", "| Decisão final | % |", "|---|---|"]
    linhas += [f"| {k} | {v:.1%} |" for k, v in h["decisao_final"].items()]
    return "\n".join(linhas) + "\n"


def renderizar_amostras_md(amostras: list[dict]) -> str:
    linhas = ["# Amostras de avisos sintéticos", "",
              "Exemplos gerados pelo gerador (o padrão é do gabarito e não é publicado com o aviso). Os itens são os que aparecem no PDF do orçamento.", ""]
    for a in amostras:
        linhas += [f"## Padrão `{a['padrao']}`", "", "```json", json.dumps(a["aviso"], ensure_ascii=False, indent=2), "```", "",
                   "| Item | Qtd. | Un. | Valor unit. | Total | Preço de referência |", "|---|---|---|---|---|---|"]
        linhas += [f"| {i['descricao']} | {i['quantidade']} | {i['unidade']} | {moeda(i['valor_unitario'])} | {moeda(i['valor_total'])} | {moeda(i['preco_referencia'])} |"
                   for i in a["itens"]]
        if a["laudo"]:
            linhas += ["", f"**Laudo:** {a['laudo']}"]
        linhas.append("")
    return "\n".join(linhas)


def main() -> None:
    p = argparse.ArgumentParser(description="Gera os dados sintéticos do caso")
    p.add_argument("--saida", default="_saida")
    p.add_argument("--escala", type=float, default=1.0)
    args = p.parse_args()
    volumes = Volumes().escalar(args.escala) if args.escala != 1.0 else Volumes()
    resumo = gerar(RAIZ / "dados/publicos", RAIZ / "dados/brutos", RAIZ / args.saida, volumes)
    amostras = resumo.pop("_amostras")
    (RAIZ / "evidencias").mkdir(exist_ok=True)
    (RAIZ / "evidencias/00b-geracao-dados.md").write_text(renderizar_resumo_md(resumo), encoding="utf-8")
    (RAIZ / "dados/amostras").mkdir(parents=True, exist_ok=True)
    (RAIZ / "dados/amostras/amostra_avisos.md").write_text(renderizar_amostras_md(amostras), encoding="utf-8")
    print(renderizar_resumo_md(resumo))


if __name__ == "__main__":
    main()

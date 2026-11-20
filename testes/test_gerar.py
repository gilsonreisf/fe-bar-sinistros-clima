import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from dados_sinteticos.gerar import Volumes, gerar, renderizar_resumo_md

RAIZ = Path(__file__).resolve().parents[1]


def _publicos_minimos(destino: Path, mundo):
    ctx, _ = mundo
    destino.mkdir(parents=True)
    ctx.municipios.to_csv(destino / "municipios_sc.csv", index=False)
    ctx.estacoes.to_csv(destino / "estacoes_inmet_sc.csv", index=False)
    clima = ctx.clima_diario.copy()
    clima2025 = clima.assign(data=clima["data"].map(lambda d: d.replace(year=2025)))
    clima.to_csv(destino / "clima_sc_diario_2026.csv", index=False)
    clima2025.to_csv(destino / "clima_sc_diario_2025.csv", index=False)
    dc = ctx.defesa_civil.drop(columns=["codigo_ibge", "lat", "lon", "peso"])
    dc.to_csv(destino / "defesa_civil_sc_2026.csv", index=False)


def test_gera_layout_completo_em_escala_minima(tmp_path, mundo, monkeypatch):
    import dados_sinteticos.config as config
    monkeypatch.setattr(config, "JANELA_EVENTO_2026", mundo[0].janela)
    monkeypatch.setattr(config, "JANELA_HISTORICO_2025", tuple(d.replace(year=2025) for d in mundo[0].janela))
    publicos = tmp_path / "publicos"
    _publicos_minimos(publicos, mundo)
    v = Volumes(corretores=5, prestadores=50, segurados=200, apolices=230, historico=60, evento=80, lotes=4)
    resumo = gerar(publicos, None, tmp_path / "saida", v, seed=3)

    s = tmp_path / "saida"
    for f in ["landing/apolices/apolices.csv", "landing/apolices_coberturas/apolices_coberturas.csv",
              "landing/segurados/segurados.csv", "landing/corretores/corretores.csv",
              "landing/precos_referencia/precos_referencia.csv", "landing/prestadores/prestadores.csv",
              "landing/municipios_sc/municipios_sc.csv", "landing/estacoes_inmet_sc/estacoes_inmet_sc.csv",
              "landing/defesa_civil_sc_2026/defesa_civil_sc_2026.csv",
              "landing/historico_sinistros/historico_sinistros_2025.csv", "landing/historico_itens/historico_itens_2025.csv",
              "restrito/gabarito_evento_2026.csv", "restrito/gabarito_historico_2025.csv", "resumo_geracao.json"]:
        assert (s / f).exists(), f
    # Revisão #6: cada pasta do landing tem um único schema (um Auto Loader por pasta)
    for pasta in (s / "landing").iterdir():
        cabecalhos = {p.read_text(encoding="utf-8").splitlines()[0] for p in pasta.glob("*.csv")}
        assert len(cabecalhos) == 1, pasta.name
    # Revisão #4: o padrão (rótulo) do histórico fica só no restrito
    hist = pd.read_csv(s / "landing/historico_sinistros/historico_sinistros_2025.csv")
    assert "motivo_decisao" not in hist.columns and not any(c.startswith("_") for c in hist.columns)
    gab_hist = pd.read_csv(s / "restrito/gabarito_historico_2025.csv")
    assert {"id_sinistro", "padrao", "motivo_decisao"} <= set(gab_hist.columns)
    assert set(gab_hist["id_sinistro"]) == set(hist["id_sinistro"])
    lotes = sorted(p.name for p in (s / "_staging").iterdir())
    assert lotes == ["lote_01", "lote_02", "lote_03", "lote_04"]
    linhas = [json.loads(l) for p in sorted((s / "_staging").glob("lote_*/avisos/*.jsonl")) for l in p.read_text().splitlines()]
    assert len(linhas) == 80
    assert not any(k.startswith("_") for k in linhas[0])  # colunas internas não vazam
    pdfs = list((s / "_staging").glob("lote_*/documentos/*.pdf"))
    assert len(pdfs) == sum(len(l["documentos"]) for l in linhas)
    assert resumo["evento"]["avisos"] == 80
    assert "Geração dos dados sintéticos" in renderizar_resumo_md(resumo)


def test_escalar_volumes():
    v = Volumes(corretores=300, prestadores=2000, segurados=50_000, apolices=60_000, historico=20_000, evento=8_000, lotes=10)
    p = v.escalar(0.0625)
    assert p.evento == 500 and p.lotes == 10 and p.corretores >= 20


def test_gerar_recusa_apagar_saida_ja_publicada(tmp_path):
    """Revisão #1: regenerar por cima de lotes já publicados quebraria a correspondência gabarito × bronze."""
    saida = tmp_path / "saida"
    (saida / "_staging").mkdir(parents=True)
    (saida / "_staging" / "publicados_volume.json").write_text('{"publicados": ["lote_01"]}')
    v = Volumes(corretores=5, prestadores=50, segurados=200, apolices=230, historico=60, evento=80, lotes=4)
    with pytest.raises(RuntimeError, match="publicad"):
        gerar(tmp_path / "nao_usado", None, saida, v, seed=1)
    assert (saida / "_staging" / "publicados_volume.json").exists()

import shutil
from pathlib import Path

import pytest

from simular_evento import arquivo_estado, enviar_local, publicar_lotes


def _staging(tmp_path: Path) -> Path:
    s = tmp_path / "_staging"
    for k in (1, 2, 3):
        (s / f"lote_{k:02d}/avisos").mkdir(parents=True)
        (s / f"lote_{k:02d}/documentos").mkdir(parents=True)
        (s / f"lote_{k:02d}/avisos/avisos_lote_{k:02d}.jsonl").write_text("{}\n")
        (s / f"lote_{k:02d}/documentos/AV-{k}_orcamento.pdf").write_bytes(b"%PDF")
    return s


def test_publica_documentos_antes_dos_avisos(tmp_path):
    ordem = []
    publicar_lotes(_staging(tmp_path), 1, lambda origem, rel: ordem.append(rel), tmp_path / "estado.json")
    assert ordem == ["documentos/AV-1_orcamento.pdf", "avisos/avisos_lote_01.jsonl"]


def test_publicacao_idempotente(tmp_path):
    """Foco de revisão 5: rodar de novo continua do próximo lote, sem duplicar nem pular."""
    s, estado, destino = _staging(tmp_path), tmp_path / "estado.json", tmp_path / "volume"
    assert publicar_lotes(s, 2, enviar_local(destino), estado) == ["lote_01", "lote_02"]
    assert publicar_lotes(s, 2, enviar_local(destino), estado) == ["lote_03"]
    assert publicar_lotes(s, 2, enviar_local(destino), estado) == []
    assert sorted(p.name for p in (destino / "avisos").iterdir()) == [f"avisos_lote_0{k}.jsonl" for k in (1, 2, 3)]


def test_estado_separado_por_destino(tmp_path):
    """Revisão #1: publicar num destino local de teste não pode marcar o lote como publicado no Volume."""
    s = _staging(tmp_path)
    local, volume = arquivo_estado(s, "local:/tmp/x"), arquivo_estado(s, "/Volumes/c/landing/arquivos")
    assert local != volume
    publicar_lotes(s, 1, lambda origem, rel: None, local, geracao="g1")
    assert publicar_lotes(s, 10, lambda origem, rel: None, volume, geracao="g1") == ["lote_01", "lote_02", "lote_03"]


def test_geracao_diferente_da_publicada_falha(tmp_path):
    """Revisão #1: depois de regenerar, publicar no mesmo destino misturaria duas gerações."""
    s, estado = _staging(tmp_path), tmp_path / "estado.json"
    publicar_lotes(s, 1, lambda origem, rel: None, estado, geracao="g1")
    with pytest.raises(RuntimeError, match="geração"):
        publicar_lotes(s, 1, lambda origem, rel: None, estado, geracao="g2")

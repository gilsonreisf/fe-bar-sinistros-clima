from publicar_pacote import caminho_destino


def test_destino_tem_o_hash_do_conteudo(tmp_path):
    """Wheel com conteúdo novo vai para outra pasta: o ambiente do pipeline nunca reaproveita um wheel antigo."""
    a, b = tmp_path / "a" / "pkg-0.1.0-py3-none-any.whl", tmp_path / "b" / "pkg-0.1.0-py3-none-any.whl"
    for p, conteudo in ((a, b"um"), (b, b"dois")):
        p.parent.mkdir()
        p.write_bytes(conteudo)
    da, db = caminho_destino("/Volumes/c/ml/artefatos", a), caminho_destino("/Volumes/c/ml/artefatos", b)
    assert da.startswith("/Volumes/c/ml/artefatos/") and da.endswith("/pkg-0.1.0-py3-none-any.whl")
    assert da != db and caminho_destino("/Volumes/c/ml/artefatos", a) == da

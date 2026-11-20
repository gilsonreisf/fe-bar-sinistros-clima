def test_pacotes_importaveis():
    import dados_sinteticos
    import regras

    assert regras.__doc__ and dados_sinteticos.__doc__

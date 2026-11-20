from verificar_recursos import Verificacao, renderizar_markdown


def test_renderiza_tabela_markdown():
    md = renderizar_markdown(
        [Verificacao("Modelos fundacionais", "ok", "databricks-claude-sonnet-x"),
         Verificacao("ABAC", "indisponivel", "erro de sintaxe")],
        quando="2026-11-20 10:00",
    )
    assert "# Verificações do ambiente" in md
    assert "| Modelos fundacionais | ✅ ok | databricks-claude-sonnet-x |" in md
    assert "| ABAC | ❌ indisponivel | erro de sintaxe |" in md

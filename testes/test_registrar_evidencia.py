from registrar_evidencia import renderizar_evidencia


def test_renderiza_cada_consulta_com_sql_e_tabela():
    md = renderizar_evidencia("Ingestão", "src/governanca/91.sql", "2026-11-20 20:00",
                              [("SELECT 1 AS a, NULL AS b", ["a", "b"], [["1", None]])])
    assert md.startswith("# Ingestão\n")
    assert "```sql\nSELECT 1 AS a, NULL AS b\n```" in md
    assert "| a | b |\n|---|---|\n| 1 |  |" in md


def test_consulta_sem_colunas_vira_nota():
    md = renderizar_evidencia("X", "y.sql", "agora", [("COMMENT ON TABLE t IS 'x'", [], [])])
    assert "(comando sem resultado tabular)" in md

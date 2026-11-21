"""Permissões do app: mínimas e sem nomes fixos (D-016, D-025)."""
from ambiente import Ambiente
from permissoes_app import comandos_pg, comandos_uc


def test_uc_so_leitura_do_que_o_app_usa():
    cmds = comandos_uc(Ambiente(catalogo="cat", prefixo_schema="p_"), "sp-1")
    texto = "\n".join(cmds)
    assert "GRANT SELECT ON TABLE cat.p_gold.sinistros_metrics TO `sp-1`" in texto
    assert "EXECUTE ON FUNCTION cat.p_gold.mascarar_cpf" in texto
    assert "bronze" not in texto and "gabarito" not in texto and "MODIFY" not in texto and "ALL PRIVILEGES" not in texto


def test_postgres_escreve_so_em_operacao():
    cmds = comandos_pg(Ambiente(catalogo="cat", prefixo_schema="p_"), "sp-1")
    escrita = [c for c in cmds if "INSERT" in c or "UPDATE" in c]
    assert escrita and all("operacao." in c for c in escrita)
    assert 'GRANT SELECT ON p_gold.sinistros_analisados_lb TO "sp-1"' in cmds
    assert not any("DELETE" in c for c in cmds)

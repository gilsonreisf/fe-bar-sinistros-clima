"""Avaliação do parecer prévio (spec 6.4): expectativas por padrão, amostra estratificada e métricas de código.

As funções são puras (testadas localmente) e viram `@scorer` do MLflow no notebook de avaliação. O gabarito só é
usado aqui, para montar as expectativas; nunca entra na entrada do parecer.
"""
from __future__ import annotations

import re

import pandas as pd

from parecer.clausulas import CLAUSULA_DA_COBERTURA

TOLERANCIA_VALOR = 0.10  # spec 6.4: valor dentro de ±10% do devido
FATOS_POR_PADRAO = {
    "legitimo_simples": ["A causa declarada tem cobertura contratada na apólice",
                         "O evento climático foi confirmado no local e na data"],
    "legitimo_complexo": ["A causa declarada tem cobertura contratada na apólice",
                          "O evento climático foi confirmado no local e na data"],
    "sem_evento_climatico": ["Não há evidência do evento climático no local e na data informados"],
    "orcamento_inflado": ["O orçamento está acima da tabela de preços de referência"],
    "sem_cobertura": ["A causa declarada não tem cobertura contratada na apólice"],
    "apolice_recente": ["A apólice foi contratada poucos dias antes do sinistro"],
    "dano_preexistente": ["O laudo aponta dano anterior ao evento em parte dos itens"],
    "prestador_concentrado": ["O prestador tem concentração atípica de orçamentos"],
}
CLAUSULA_POR_PADRAO = {"sem_evento_climatico": "CG-6.1", "orcamento_inflado": "CG-7.1", "sem_cobertura": "CG-2.1",
                       "apolice_recente": "CG-2.4", "dano_preexistente": "CG-5.1", "prestador_concentrado": "CG-8.1"}
_PALAVRAS_POR_PADRAO = {
    "sem_evento_climatico": r"evid[eê]ncia|clim|meteorol|evento|esta[cç][aã]o|defesa civil",
    "orcamento_inflado": r"tabela|refer[eê]ncia|pre[cç]o|acima|mercado",
    "sem_cobertura": r"cobertura",
    "apolice_recente": r"recente|contrata|vig[eê]ncia|in[ií]cio|dias",
    "dano_preexistente": r"preexist|anterior|desgaste",
    "prestador_concentrado": r"prestador|concentra",
}


def expectativas(padrao: str, decisao_esperada: str, valor_devido: float, cobertura_necessaria: str | None) -> dict:
    """Expectativas de um caso a partir do gabarito: recomendação, valor, fatos esperados (juiz Correctness) e a
    cláusula que um parecer correto cita."""
    clausula = CLAUSULA_POR_PADRAO.get(padrao) or CLAUSULA_DA_COBERTURA.get(cobertura_necessaria or "", "CG-4.1")
    return {"recomendacao_esperada": decisao_esperada, "valor_devido": float(valor_devido), "padrao": padrao,
            "clausula_esperada": clausula,
            "expected_facts": [*FATOS_POR_PADRAO[padrao], f"A recomendação é {decisao_esperada}"]}


def amostra_estratificada(df: pd.DataFrame, coluna: str, n_max: int, seed: int = 42) -> pd.DataFrame:
    """Até n_max linhas por grupo (todas, se o grupo for menor), com a seed fixa."""
    partes = [g.sample(min(len(g), n_max), random_state=seed) for _, g in df.groupby(coluna, sort=True)]
    return pd.concat(partes).sort_index() if partes else df.iloc[0:0]


def recomendacao_correta(outputs: dict, expectations: dict) -> bool:
    return outputs.get("recomendacao") == expectations.get("recomendacao_esperada")


def json_valido(outputs: dict) -> bool:
    return outputs.get("status_parecer") == "ok"


def padrao_identificado(outputs: dict, expectations: dict) -> bool:
    """Os motivos citam o fato que caracteriza o padrão; para os legítimos, basta recomendar pagamento."""
    padrao = expectations.get("padrao", "")
    if padrao.startswith("legitimo"):
        return str(outputs.get("recomendacao", "")).startswith("pagar")
    texto = " ".join(outputs.get("motivos") or []).lower()
    return bool(re.search(_PALAVRAS_POR_PADRAO.get(padrao, r"$^"), texto))


def cita_clausula(outputs: dict, expectations: dict) -> bool:
    return expectations.get("clausula_esperada") in (outputs.get("clausulas") or [])


def valor_dentro_tolerancia(valor: float, devido: float, tolerancia: float = TOLERANCIA_VALOR) -> bool:
    return abs(float(valor) - float(devido)) <= tolerancia * max(abs(float(devido)), 1.0)


# Registro de prompts em tabela Delta do UC (D-022): o Prompt Registry do MLflow não está habilitado no FEVM
# (FEATURE_DISABLED). Mesmas operações: versão nova só quando o texto muda, alias de produção e métrica por versão; o
# histórico Delta da tabela é a trilha de auditoria. Funções puras sobre um DataFrame pequeno (uma linha por versão).
COLUNAS_PROMPTS = ["versao", "rotulo", "template", "sha256", "mensagem", "criado_em", "recomendacao_correta", "producao"]


def tabela_prompts_vazia() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in zip(COLUNAS_PROMPTS, (
        "int64", "object", "object", "object", "object", "object", "float64", "bool"))})


def registrar_versao(tabela: pd.DataFrame, template: str, rotulo: str, mensagem: str, agora: str) -> tuple[pd.DataFrame, int, bool]:
    """(tabela, versão, nova?). Reaproveita a versão com o mesmo texto (sha256); senão, cria a próxima."""
    import hashlib

    sha = hashlib.sha256(template.encode("utf-8")).hexdigest()
    iguais = tabela[tabela["sha256"] == sha]
    if len(iguais):
        return tabela, int(iguais["versao"].iloc[0]), False
    versao = int(tabela["versao"].max()) + 1 if len(tabela) else 1
    linha = pd.DataFrame([{"versao": versao, "rotulo": rotulo, "template": template, "sha256": sha, "mensagem": mensagem,
                           "criado_em": agora, "recomendacao_correta": float("nan"), "producao": False}])
    return pd.concat([tabela, linha], ignore_index=True)[COLUNAS_PROMPTS], versao, True


def gravar_metrica(tabela: pd.DataFrame, versao: int, valor: float) -> pd.DataFrame:
    t = tabela.copy()
    t.loc[t["versao"] == versao, "recomendacao_correta"] = float(valor)
    return t


def versao_producao(tabela: pd.DataFrame) -> dict | None:
    linhas = tabela[tabela["producao"].astype(bool)]
    return None if linhas.empty else linhas.iloc[0].to_dict()


def definir_producao(tabela: pd.DataFrame, versao: int) -> pd.DataFrame:
    """Alias único: só uma versão fica com producao = verdadeiro."""
    if not (tabela["versao"] == versao).any():
        raise ValueError(f"versão {versao} não existe no registro de prompts")
    t = tabela.copy()
    t["producao"] = t["versao"] == versao
    return t

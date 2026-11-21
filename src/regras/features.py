"""Features do modelo de suspeita, iguais no treino (histórico 2025) e no score (evento 2026).

As colunas de entrada existem com o mesmo nome e significado em silver.historico_enriquecido e em
silver.sinistros_enriquecidos (mesmas regras do pipeline). Aqui elas viram a matriz do modelo. Nada aqui lê o gabarito.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LIMIAR_FAST_TRACK = 0.2  # spec 6.3: score abaixo disso é condição do fast track (e não há fator a explicar)
JANELA_PRESTADOR_DIAS = 30  # participação do prestador nos 30 dias anteriores ao aviso (point-in-time; D-020/D-021)
MIN_AVISOS_JANELA_PRESTADOR = 200  # abaixo disso a proporção é ruído (início do histórico ou do evento) e fica nula

COLUNAS_ENTRADA = ["valor_reclamado", "lmi", "desvio_preco_pct", "dias_desde_contratacao", "forca_evidencia_climatica",
                   "cobertura_valida", "menciona_dano_anterior", "participacao_prestador_30d", "causa_declarada", "ramo"]
# Fora do modelo principal (D-021): no histórico, sem Defesa Civil, o clima bruto se confunde com a fonte da evidência
COLUNAS_CLIMA_BRUTO = ["chuva_mm", "chuva_max_hora_mm", "rajada_max_ms", "distancia_estacao_km"]
CATEGORIAS = {"causa_declarada": ["granizo", "vendaval", "alagamento", "danos_eletricos"],
              "ramo": ["residencial", "empresarial"]}
ORDEM_EVIDENCIA = {"contraria": 0.0, "fraca": 1.0, "forte": 2.0}
FEATURES = ["log_valor_reclamado", "razao_valor_lmi", "desvio_preco_pct", "dias_desde_contratacao", "evidencia_climatica",
            "cobertura_valida", "menciona_dano_anterior", "participacao_prestador_30d", "causa_declarada", "ramo"]
# Vazam o rótulo: nunca entram como feature (histórico: decisão e pagamento; itens: preexistente; evento: gabarito)
COLUNAS_PROIBIDAS = frozenset({"decisao_final", "valor_pago", "motivo_decisao", "padrao", "preexistente",
                               "decisao_esperada", "valor_devido", "motivo", "suspeito"})

ROTULOS = {
    "log_valor_reclamado": "Valor reclamado alto",
    "razao_valor_lmi": "Valor próximo do limite da cobertura (LMI)",
    "desvio_preco_pct": "Preço acima da tabela de referência",
    "dias_desde_contratacao": "Apólice contratada há pouco tempo",
    "evidencia_climatica": "Evidência climática fraca ou contrária",
    "cobertura_valida": "Causa sem cobertura contratada",
    "menciona_dano_anterior": "Laudo menciona dano anterior ao evento",
    "participacao_prestador_30d": "Prestador com concentração atípica de orçamentos",
    "causa_declarada": "Causa declarada",
    "ramo": "Ramo da apólice",
    "chuva_mm": "Chuva no dia", "chuva_max_hora_mm": "Chuva máxima em uma hora",
    "rajada_max_ms": "Rajada máxima", "distancia_estacao_km": "Distância até a estação",
}


def rotulo_suspeito(padrao: pd.Series) -> pd.Series:
    """1 para todo padrão diferente de legitimo_* (spec 6.1). Padrão nulo é erro: o rótulo não pode ser inventado."""
    if padrao.isna().any():
        raise ValueError(f"{int(padrao.isna().sum())} sinistro(s) sem padrão no gabarito")
    return (~padrao.astype(str).str.startswith("legitimo_")).astype(int)


def _numero(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)


def _booleano(s: pd.Series) -> pd.Series:
    """Booleano do Spark (True/False/None) como 1.0/0.0; nulo conta como 0 (sem cobertura, sem menção)."""
    def um(v) -> float:
        if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
            return 0.0
        if isinstance(v, str):
            return 1.0 if v.strip().lower() == "true" else 0.0
        return 1.0 if bool(v) else 0.0

    return s.astype(object).map(um).astype(float)


def montar_features(df: pd.DataFrame, com_clima_bruto: bool = False) -> pd.DataFrame:
    colunas = COLUNAS_ENTRADA + (COLUNAS_CLIMA_BRUTO if com_clima_bruto else [])
    faltando = [c for c in colunas if c not in df.columns]
    if faltando:
        raise KeyError(f"colunas de entrada ausentes: {', '.join(faltando)}")
    valor, lmi = _numero(df["valor_reclamado"]), _numero(df["lmi"])
    X = pd.DataFrame(index=df.index)
    X["log_valor_reclamado"] = np.log1p(valor.clip(lower=0))
    X["razao_valor_lmi"] = valor / lmi.where(lmi > 0)
    X["desvio_preco_pct"] = _numero(df["desvio_preco_pct"])
    X["dias_desde_contratacao"] = _numero(df["dias_desde_contratacao"])
    X["evidencia_climatica"] = df["forca_evidencia_climatica"].map(ORDEM_EVIDENCIA).astype(float)
    X["cobertura_valida"] = _booleano(df["cobertura_valida"])
    X["menciona_dano_anterior"] = _booleano(df["menciona_dano_anterior"])
    X["participacao_prestador_30d"] = _numero(df["participacao_prestador_30d"])
    for coluna, categorias in CATEGORIAS.items():
        X[coluna] = pd.Categorical(df[coluna].where(df[coluna].isin(categorias)), categories=categorias)
    if com_clima_bruto:
        for coluna in COLUNAS_CLIMA_BRUTO:
            X[coluna] = _numero(df[coluna])
    return X


_TEXTO_OU_BOOLEANO = {"forca_evidencia_climatica", "causa_declarada", "ramo", "cobertura_valida", "menciona_dano_anterior"}


def preparar_entrada(df: pd.DataFrame, com_clima_bruto: bool = False) -> pd.DataFrame:
    """Só as colunas de entrada do modelo servido, com os números em float64 (a assinatura do MLflow recusa int64 em
    coluna double: o INT do Spark chega como int32 e passa, mas um int64 do pandas, não)."""
    colunas = COLUNAS_ENTRADA + (COLUNAS_CLIMA_BRUTO if com_clima_bruto else [])
    faltando = [c for c in colunas if c not in df.columns]
    if faltando:
        raise KeyError(f"colunas de entrada ausentes: {', '.join(faltando)}")
    saida = df[colunas].copy()
    for coluna in colunas:
        if coluna not in _TEXTO_OU_BOOLEANO:
            saida[coluna] = _numero(saida[coluna])
        else:
            saida[coluna] = saida[coluna].astype(object).where(saida[coluna].notna(), None)
    return saida


def principais_fatores(contribuicoes: np.ndarray, nomes: list[str], k: int = 3) -> list[str]:
    """Até k fatores que mais AUMENTAM a suspeita (contribuição SHAP > 0), em português, do maior para o menor."""
    ordem = np.argsort(-np.asarray(contribuicoes, dtype=float))
    return [ROTULOS.get(nomes[i], nomes[i]) for i in ordem[:k] if contribuicoes[i] > 0]

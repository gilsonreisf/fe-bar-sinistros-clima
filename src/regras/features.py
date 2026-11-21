"""Features do modelo de suspeita, iguais no treino (histórico 2025) e no score (evento 2026).

As colunas de entrada existem com o mesmo nome e significado em silver.historico_enriquecido e em
silver.sinistros_enriquecidos (mesmas regras do pipeline). Aqui elas viram a matriz do modelo. Nada aqui lê o gabarito.
"""
from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

LIMIAR_FAST_TRACK = 0.2  # spec 6.3: score abaixo disso é condição do fast track (e não há fator a explicar)
TETO_FAST_TRACK_RS = 5000.0  # spec 6.3: valor reclamado máximo do fast track
JANELA_PRESTADOR_DIAS = 30  # participação do prestador nos 30 dias anteriores ao aviso (point-in-time; D-020/D-021)
# Proporção suavizada (empírica bayesiana): (avisos do prestador + 1) / (avisos na janela + 2000), como se houvesse
# 2.000 avisos "virtuais" a 0,5‰ (participação típica de um prestador no histórico). Sem isso, no início de um evento
# a janela é pequena e 1 aviso anterior já parecia concentração (lote 1: 47 de 53 falsos positivos; D-021).
PSEUDO_AVISOS_JANELA = 2000
PSEUDO_AVISOS_PRESTADOR = 1  # = 2000 × 0,0005 (inteiro: o literal 1.0 virava DECIMAL no Spark; revisão #1)
# Versão do contrato das features: mudar a definição de qualquer feature exige subir este número. O portão de promoção
# só compara AUC entre versões do mesmo contrato (D-021). O teste test_contrato_de_features_acompanha_o_codigo amarra o
# número ao hash deste arquivo e do SQL das colunas de entrada (src/regras/contrato_features.json).
VERSAO_CONTRATO_FEATURES = "3"

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

LIMIAR_VALOR_ALTO_RS = 20000.0  # acima disso o orçamento exige laudo (gerador e regra de negócio)
LIMIAR_DIAS_RECENTE = 30  # CG-2.4: sinistro nos primeiros 30 dias de vigência passa por análise
LIMIAR_DESVIO_PRECO = 0.30  # mesmo corte da flag preco_acima_referencia (silver)
LIMIAR_PARTICIPACAO_ATIPICA = 0.001  # 1‰ ≈ 3 ou mais avisos em 30 dias no histórico (≈ p95 dos prestadores comuns)
CONTRIBUICAO_MINIMA = 0.1  # SHAP (logito) mínimo para um fator ser citado

# Fator citado ao regulador só quando o VALOR da feature justifica a frase (revisão #5): o SHAP sozinho também é
# positivo para valores típicos ou nulos e geraria motivos falsos (ex.: "valor próximo do LMI" com LMI nulo).
_FATORES = {
    "log_valor_reclamado": lambda v: "Valor reclamado alto" if v >= np.log1p(LIMIAR_VALOR_ALTO_RS) else None,
    "razao_valor_lmi": lambda v: "Valor próximo do limite da cobertura (LMI)" if v >= 0.8 else None,
    "desvio_preco_pct": lambda v: "Preço acima da tabela de referência" if v >= LIMIAR_DESVIO_PRECO else None,
    "dias_desde_contratacao": lambda v: "Apólice contratada há menos de 30 dias" if v < LIMIAR_DIAS_RECENTE else None,
    "evidencia_climatica": lambda v: ("Evidência climática contrária ao evento declarado" if v == 0
                                      else "Evidência climática fraca (sem dado no raio)" if v == 1 else None),
    "cobertura_valida": lambda v: "Causa sem cobertura contratada" if v == 0 else None,
    "menciona_dano_anterior": lambda v: "Laudo menciona dano anterior ao evento" if v == 1 else None,
    "participacao_prestador_30d": lambda v: ("Prestador com concentração atípica de orçamentos"
                                             if v >= LIMIAR_PARTICIPACAO_ATIPICA else None),
}
FATOR_COMBINADO = "Combinação de fatores fora do padrão do histórico"
ROTULOS = {  # nomes legíveis das features (gráficos de SHAP)
    "log_valor_reclamado": "Valor reclamado", "razao_valor_lmi": "Valor ÷ LMI", "desvio_preco_pct": "Desvio de preço",
    "dias_desde_contratacao": "Dias desde a contratação", "evidencia_climatica": "Evidência climática",
    "cobertura_valida": "Cobertura válida", "menciona_dano_anterior": "Laudo com dano anterior",
    "participacao_prestador_30d": "Participação do prestador (30 dias)", "causa_declarada": "Causa declarada",
    "ramo": "Ramo da apólice", "chuva_mm": "Chuva no dia", "chuva_max_hora_mm": "Chuva máxima em uma hora",
    "rajada_max_ms": "Rajada máxima", "distancia_estacao_km": "Distância até a estação",
}


def rotulo_suspeito(padrao: pd.Series) -> pd.Series:
    """1 para todo padrão diferente de legitimo_* (spec 6.1). Padrão nulo é erro: o rótulo não pode ser inventado."""
    if padrao.isna().any():
        raise ValueError(f"{int(padrao.isna().sum())} sinistro(s) sem padrão no gabarito")
    return (~padrao.astype(str).str.startswith("legitimo_")).astype(int)


def _numero(s: pd.Series) -> pd.Series:
    """Número como float64; aceita Decimal (DECIMAL do Spark) e texto numérico."""
    return pd.to_numeric(s.map(lambda v: float(v) if isinstance(v, Decimal) else v), errors="coerce").astype(float)


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


def principais_fatores(contribuicoes: np.ndarray, nomes: list[str], valores: pd.Series, k: int = 3) -> list[str]:
    """Até k fatores que mais AUMENTAM a suspeita, em português: contribuição SHAP ≥ CONTRIBUICAO_MINIMA e valor da
    feature que justifica a frase. Valor nulo nunca vira fator."""
    contribuicoes = np.asarray(contribuicoes, dtype=float)
    fatores = []
    for i in np.argsort(-contribuicoes, kind="stable"):
        if contribuicoes[i] < CONTRIBUICAO_MINIMA or len(fatores) == k:
            break
        regra, valor = _FATORES.get(nomes[i]), valores.get(nomes[i])
        if regra is None or valor is None or pd.isna(valor):
            continue
        frase = regra(float(valor))
        if frase and frase not in fatores:
            fatores.append(frase)
    return fatores

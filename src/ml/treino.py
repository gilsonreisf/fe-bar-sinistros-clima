"""Treino, métricas e portão de promoção do modelo de suspeita (pandas, LightGBM e MLflow; roda no job e nos testes)."""
from __future__ import annotations

import math

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from regras.features import (COLUNAS_CLIMA_BRUTO, COLUNAS_ENTRADA, LIMIAR_DESVIO_PRECO, LIMIAR_DIAS_RECENTE,
                             LIMIAR_FAST_TRACK, TETO_FAST_TRACK_RS, _booleano, _numero)

CORTE_TESTE = "2025-10-01"  # treino: jan–set/2025; teste: out–dez/2025 (split temporal)
FRACAO_TOPO = 0.10  # spec 6.1: precisão e recall nos 10% mais suspeitos
PARAMS_LGBM = dict(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=30, subsample=0.8,
                   subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=42, verbose=-1,
                   deterministic=True, force_col_wise=True)  # reprodutível na mesma versão Delta (revisão #10)
PISO_AUC = 0.80  # piso absoluto para virar champion (revisão #7b)
TETO_SUSPEITOS_ABAIXO_LIMIAR = 0.10  # no máximo 10% dos suspeitos do teste abaixo do limiar do fast track
_TIPOS_ENTRADA = {"forca_evidencia_climatica": "string", "causa_declarada": "string", "ramo": "string",
                  "cobertura_valida": "boolean", "menciona_dano_anterior": "boolean"}


def dividir_temporal(df: pd.DataFrame, coluna: str = "data_aviso", corte: str = CORTE_TESTE):
    datas = pd.to_datetime(df[coluna])
    treino, teste = df[datas < pd.Timestamp(corte)], df[datas >= pd.Timestamp(corte)]
    if treino.empty or teste.empty:
        raise ValueError(f"split temporal vazio: treino={len(treino)}, teste={len(teste)} (corte {corte})")
    return treino, teste


def treinar(X: pd.DataFrame, y, params: dict = PARAMS_LGBM) -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(**params).fit(X, np.asarray(y))


def metricas(y, score, prefixo: str = "") -> dict[str, float]:
    y, score = np.asarray(y).astype(int), np.asarray(score, dtype=float)
    k = max(1, math.ceil(FRACAO_TOPO * len(y)))
    topo = np.argsort(-score, kind="stable")[:k]
    n_susp = int(y.sum())
    abaixo = score < LIMIAR_FAST_TRACK
    m = {
        "auc": float(roc_auc_score(y, score)) if 0 < n_susp < len(y) else float("nan"),
        "ap": float(average_precision_score(y, score)) if n_susp else float("nan"),
        "precisao_top10": float(y[topo].mean()),
        "recall_top10": float(y[topo].sum() / n_susp) if n_susp else float("nan"),
        # teto do recall nos 10% do topo: com prevalência acima de 10%, nem um modelo perfeito chega a 1 (revisão #12)
        "recall_top10_teto": float(min(1.0, k / n_susp)) if n_susp else float("nan"),
        "suspeitos_abaixo_limiar": float(abaixo[y == 1].mean()) if n_susp else float("nan"),
        "legitimos_abaixo_limiar": float(abaixo[y == 0].mean()) if n_susp < len(y) else float("nan"),
        "n": float(len(y)), "n_suspeitos": float(n_susp),
    }
    return {f"{prefixo}{c}": v for c, v in m.items()}


def por_padrao(padrao: pd.Series, score) -> pd.DataFrame:
    """Por padrão do gabarito: quantos, score mediano e % com score ≥ limiar do fast track (bloqueados)."""
    t = pd.DataFrame({"padrao": np.asarray(padrao), "score": np.asarray(score, dtype=float)})
    return (t.groupby("padrao")
            .agg(n=("score", "size"), score_mediano=("score", "median"),
                 pct_acima_limiar=("score", lambda s: round(100 * float((s >= LIMIAR_FAST_TRACK).mean()), 1)))
            .reset_index().sort_values("padrao").reset_index(drop=True))


def contribuicoes(booster: lgb.Booster, X: pd.DataFrame) -> pd.DataFrame:
    """Valores SHAP exatos (TreeSHAP do próprio LightGBM), na escala do logito; a última coluna é o valor base."""
    return pd.DataFrame(booster.predict(X, pred_contrib=True), columns=[*X.columns, "base"], index=X.index)


def passa_piso(metricas_teste: dict) -> bool:
    """Piso absoluto: mesmo com outro contrato de features, uma versão ruim nunca vira champion (revisão #7b)."""
    auc, escape = metricas_teste.get("teste_auc"), metricas_teste.get("teste_suspeitos_abaixo_limiar")
    return (auc is not None and not math.isnan(auc) and auc >= PISO_AUC
            and escape is not None and not math.isnan(escape) and escape <= TETO_SUSPEITOS_ABAIXO_LIMIAR)


def decidir_promocao(auc_novo: float, auc_champion: float | None, contrato_igual: bool = True,
                     passou_piso: bool = True) -> str:
    """Spec 6.1: só vira champion com AUC MAIOR que o do champion atual no mesmo teste; a primeira versão é champion.

    Com outro contrato de features, o champion atual recebe entradas com outro significado e o AUC dele não é
    comparável: a versão nova assume (D-021). AUC do champion NaN também não é comparável. Sem o piso, nunca assume.
    """
    if not passou_piso:
        return "challenger"
    if auc_champion is None or math.isnan(auc_champion) or not contrato_igual:
        return "champion"
    return "champion" if auc_novo > auc_champion else "challenger"


def regra_base(df: pd.DataFrame) -> pd.Series:
    """Linha de base honesta (revisão #6): o OU das regras simples que um analista escreveria sem modelo."""
    sem_cobertura = _booleano(df["cobertura_valida"]) == 0
    contraria = df["forca_evidencia_climatica"].astype(object).eq("contraria")
    recente = _numero(df["dias_desde_contratacao"]) < LIMIAR_DIAS_RECENTE
    dano_anterior = _booleano(df["menciona_dano_anterior"]) == 1
    preco = _numero(df["desvio_preco_pct"]) >= LIMIAR_DESVIO_PRECO
    return (sem_cobertura | contraria | recente | dano_anterior | preco).astype(int)


def metricas_fast_track(df: pd.DataFrame, y, score, prefixo: str = "") -> dict[str, float]:
    """Vazamento na população que de fato concorre ao fast track (≤ R$ 5 mil, com cobertura e evidência forte):
    quantos suspeitos passariam pelo critério do score (< 0,2) e quantos legítimos seguem liberados (revisão #12)."""
    y, score = np.asarray(y).astype(int), np.asarray(score, dtype=float)
    elegivel = ((_numero(df["valor_reclamado"]) <= TETO_FAST_TRACK_RS).to_numpy()
                & (_booleano(df["cobertura_valida"]) == 1).to_numpy()
                & df["forca_evidencia_climatica"].astype(object).eq("forte").to_numpy())
    liberado = score < LIMIAR_FAST_TRACK
    legitimos = elegivel & (y == 0)
    m = {"ft_elegiveis": float(elegivel.sum()), "ft_suspeitos_elegiveis": float((elegivel & (y == 1)).sum()),
         "ft_suspeitos_liberados": float((elegivel & (y == 1) & liberado).sum()),
         "ft_legitimos_liberados_pct": float(liberado[legitimos].mean()) if legitimos.any() else float("nan")}
    return {f"{prefixo}{c}": v for c, v in m.items()}


def assinatura(com_clima_bruto: bool = False):
    """Assinatura explícita (não inferida): todas as colunas aceitam nulo, como chegam da silver."""
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    colunas = COLUNAS_ENTRADA + (COLUNAS_CLIMA_BRUTO if com_clima_bruto else [])
    entrada = Schema([ColSpec(_TIPOS_ENTRADA.get(c, "double"), c, required=False) for c in colunas])
    saida = Schema([ColSpec("double", "score_suspeita"), ColSpec("string", "fatores_suspeita")])
    return ModelSignature(inputs=entrada, outputs=saida)

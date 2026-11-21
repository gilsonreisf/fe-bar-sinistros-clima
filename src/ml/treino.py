"""Treino, métricas e portão de promoção do modelo de suspeita (pandas, LightGBM e MLflow; roda no job e nos testes)."""
from __future__ import annotations

import math

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from regras.features import COLUNAS_CLIMA_BRUTO, COLUNAS_ENTRADA, LIMIAR_FAST_TRACK

CORTE_TESTE = "2025-10-01"  # treino: jan–set/2025; teste: out–dez/2025 (split temporal)
FRACAO_TOPO = 0.10  # spec 6.1: precisão e recall nos 10% mais suspeitos
PARAMS_LGBM = dict(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=30, subsample=0.8,
                   subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=42, verbose=-1)
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


def decidir_promocao(auc_novo: float, auc_champion: float | None) -> str:
    """Spec 6.1: só vira champion com AUC MAIOR que o do champion atual no mesmo teste; a primeira versão é champion."""
    return "champion" if auc_champion is None or auc_novo > auc_champion else "challenger"


def assinatura(com_clima_bruto: bool = False):
    """Assinatura explícita (não inferida): todas as colunas aceitam nulo, como chegam da silver."""
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    colunas = COLUNAS_ENTRADA + (COLUNAS_CLIMA_BRUTO if com_clima_bruto else [])
    entrada = Schema([ColSpec(_TIPOS_ENTRADA.get(c, "double"), c, required=False) for c in colunas])
    saida = Schema([ColSpec("double", "score_suspeita"), ColSpec("string", "fatores_suspeita")])
    return ModelSignature(inputs=entrada, outputs=saida)

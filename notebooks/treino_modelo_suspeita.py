# Databricks notebook source
# MAGIC %md
# MAGIC # Modelo de suspeita: treino no histórico de 2025
# MAGIC
# MAGIC **Problema de negócio.** Num evento climático chegam milhares de avisos em poucos dias. A seguradora quer pagar
# MAGIC rápido os casos simples (fast track) sem deixar passar pagamento indevido (*leakage*). O `score_suspeita`
# MAGIC (0 a 1) faz duas coisas:
# MAGIC - **bloqueia o fast track** quando o score passa de 0,2 (spec 6.3);
# MAGIC - **prioriza a fila do regulador.**
# MAGIC
# MAGIC Cada score traz os fatores que mais pesaram, em português, para o regulador e para o parecer.
# MAGIC
# MAGIC **Dados.**
# MAGIC - `silver.historico_enriquecido`: 20 mil sinistros regulados em 2025, com as **mesmas features** do evento,
# MAGIC   calculadas pelas mesmas regras do pipeline.
# MAGIC - Rótulo: `restrito/gabarito/gabarito_historico_2025.csv`. Alvo `suspeito` = padrão diferente de `legitimo_*`.
# MAGIC
# MAGIC **Validação.**
# MAGIC - Split temporal: treino de jan a set e teste de out a dez/2025.
# MAGIC - Checagem fora do tempo nos avisos do evento de 2026 já publicados (lote 1).
# MAGIC
# MAGIC **Decisões (D-021):**
# MAGIC - o clima bruto fica fora do modelo (no histórico ele se confunde com a fonte da evidência, porque não há
# MAGIC   Defesa Civil em 2025); uma ablação mostra o efeito;
# MAGIC - SHAP pelo próprio LightGBM (TreeSHAP exato);
# MAGIC - participação do prestador point-in-time.
# MAGIC
# MAGIC **Leitura honesta das métricas.** Os padrões sintéticos têm sinais plantados, então um AUC alto é esperado. O que
# MAGIC este notebook prova é que o sinal sobrevive ao pipeline real (OCR, extração por IA e cruzamentos) e que o score
# MAGIC é explicável. Com dados reais, o desempenho seria menor, e a calibração viria da PoC.

# COMMAND ----------

import json
import tempfile
from pathlib import Path

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from pyspark.sql import functions as F
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_curve

import ml
import regras
from ml.treino import (CORTE_TESTE, FRACAO_TOPO, LIMIAR_FAST_TRACK, PARAMS_LGBM, assinatura, contribuicoes,
                       decidir_promocao, dividir_temporal, metricas, por_padrao, treinar)
from regras.features import (COLUNAS_CLIMA_BRUTO, COLUNAS_ENTRADA, COLUNAS_PROIBIDAS, FEATURES, ROTULOS,
                             VERSAO_CONTRATO_FEATURES, montar_features, preparar_entrada, rotulo_suspeito)

for nome in ("catalogo", "schema_silver", "schema_ml", "experimento"):
    dbutils.widgets.text(nome, "")  # noqa: F821 (dbutils é injetado pelo Databricks)
catalogo, schema_silver, schema_ml, experimento = (dbutils.widgets.get(n) for n in  # noqa: F821
                                                   ("catalogo", "schema_silver", "schema_ml", "experimento"))
assert all((catalogo, schema_silver, schema_ml, experimento)), "parâmetros do job ausentes"
SILVER, ML = f"{catalogo}.{schema_silver}", f"{catalogo}.{schema_ml}"
NOME_MODELO = f"{ML}.modelo_suspeita"
TABELA_FEATURES = f"{ML}.features_treino"
GABARITO = f"/Volumes/{catalogo}/{schema_ml}/restrito/gabarito"
print(f"modelo: {NOME_MODELO} | features: {TABELA_FEATURES} | experimento: {experimento}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Dados de treino: histórico enriquecido + rótulo do gabarito restrito
# MAGIC
# MAGIC Duas checagens de segurança:
# MAGIC - as colunas de entrada existem com o mesmo nome nas duas tabelas silver (treino e evento);
# MAGIC - nenhuma coluna que vaza o rótulo entra nas features.
# MAGIC
# MAGIC O resultado vai para `ml.features_treino`, uma tabela Delta versionada, para o `log_input` do MLflow.

# COMMAND ----------

for tabela in ("historico_enriquecido", "sinistros_enriquecidos"):
    faltando = set(COLUNAS_ENTRADA + COLUNAS_CLIMA_BRUTO) - set(spark.table(f"{SILVER}.{tabela}").columns)  # noqa: F821
    assert not faltando, f"{tabela} sem as colunas {faltando}"
assert not (set(FEATURES) | set(COLUNAS_ENTRADA)) & COLUNAS_PROIBIDAS, "feature proibida (vaza o rótulo)"

hist = spark.table(f"{SILVER}.historico_enriquecido")  # noqa: F821
gab = spark.read.csv(f"{GABARITO}/gabarito_historico_2025.csv", header=True).select("id_sinistro", "padrao")  # noqa: F821
base = (hist.select("id_sinistro", "data_aviso", *COLUNAS_ENTRADA, *COLUNAS_CLIMA_BRUTO)
        .join(gab, "id_sinistro", "left")
        .withColumn("suspeito", (~F.col("padrao").startswith("legitimo_")).cast("int"))
        .withColumn("conjunto", F.when(F.col("data_aviso") < F.lit(CORTE_TESTE).cast("date"), "treino").otherwise("teste")))
base.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TABELA_FEATURES)
spark.sql(f"COMMENT ON TABLE {TABELA_FEATURES} IS 'Features de treino do modelo de suspeita (histórico 2025) com rótulo e conjunto (treino/teste).'")  # noqa: F821
VERSAO_FEATURES = int(spark.sql(f"DESCRIBE HISTORY {TABELA_FEATURES} LIMIT 1").first()["version"])  # noqa: F821

df = spark.sql(f"SELECT * FROM {TABELA_FEATURES} VERSION AS OF {VERSAO_FEATURES}").toPandas()  # noqa: F821
assert len(df) == hist.count(), "o join com o gabarito mudou o número de linhas"
assert (rotulo_suspeito(df["padrao"]) == df["suspeito"]).all()  # falha se algum sinistro ficou sem padrão
treino, teste = dividir_temporal(df)
assert set(treino["conjunto"]) == {"treino"} and set(teste["conjunto"]) == {"teste"}
print(f"features_treino versão {VERSAO_FEATURES}: {len(treino)} treino, {len(teste)} teste")
display(df.groupby(["padrao", "conjunto"]).size().unstack("conjunto").reset_index())  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Treino (LightGBM) e métricas
# MAGIC
# MAGIC Métricas da spec 6.1: AUC, e precisão e recall nos 10% mais suspeitos. Métricas de negócio (spec 6.3):
# MAGIC - `suspeitos_abaixo_limiar`: fração dos suspeitos com score < 0,2, que escapariam do bloqueio do fast track;
# MAGIC - `legitimos_abaixo_limiar`: fração dos legítimos que seguem elegíveis ao fast track.

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experimento)
dataset = mlflow.data.load_delta(table_name=TABELA_FEATURES, version=VERSAO_FEATURES, name="features_treino")

Xtr, Xte = montar_features(treino), montar_features(teste)
with mlflow.start_run(run_name="lightgbm_sem_clima_bruto") as run:
    RUN_ID = run.info.run_id
    mlflow.log_params({**PARAMS_LGBM, "corte_teste": CORTE_TESTE, "limiar_fast_track": LIMIAR_FAST_TRACK,
                       "fracao_topo": FRACAO_TOPO, "features": ",".join(FEATURES), "com_clima_bruto": False,
                       "contrato_features": VERSAO_CONTRATO_FEATURES,
                       "features_treino_tabela": TABELA_FEATURES, "features_treino_versao": VERSAO_FEATURES,
                       "n_treino": len(treino), "n_teste": len(teste)})
    mlflow.log_input(dataset, context="treino")
    mlflow.log_input(dataset, context="teste")
    mlflow.set_tags({"fase": "3", "decisao": "D-021", "alvo": "suspeito = padrao != legitimo_*"})
    modelo = treinar(Xtr, treino["suspeito"])
    score_tr, score_te = modelo.predict_proba(Xtr)[:, 1], modelo.predict_proba(Xte)[:, 1]
    METRICAS = metricas(treino["suspeito"], score_tr, "treino_") | metricas(teste["suspeito"], score_te, "teste_")
    mlflow.log_metrics(METRICAS)
    tabela_padrao_teste = por_padrao(teste["padrao"], score_te)
    mlflow.log_table(tabela_padrao_teste, "por_padrao_teste.json")

display(pd.DataFrame([{"metrica": k, "valor": round(v, 4)} for k, v in METRICAS.items()]))  # noqa: F821
display(tabela_padrao_teste)  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Artefatos: ROC, PR, matriz de confusão no corte do fast track e SHAP
# MAGIC
# MAGIC Os valores SHAP vêm do próprio LightGBM (`pred_contrib=True`, TreeSHAP exato, D-021) e estão na escala do logito.

# COMMAND ----------

def _figura_roc(y, s):
    fpr, tpr, _ = roc_curve(y, s)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(fpr, tpr, label=f"AUC = {METRICAS['teste_auc']:.3f}")
    ax.plot([0, 1], [0, 1], "--", color="grey")
    ax.set(xlabel="Taxa de falsos positivos", ylabel="Taxa de verdadeiros positivos", title="Curva ROC (teste out–dez/2025)")
    ax.legend(loc="lower right")
    return fig


def _figura_pr(y, s):
    precisao, recall, _ = precision_recall_curve(y, s)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot(recall, precisao, label=f"AP = {METRICAS['teste_ap']:.3f}")
    ax.set(xlabel="Recall", ylabel="Precisão", title="Curva precisão × recall (teste)")
    ax.legend(loc="lower left")
    return fig


def _figura_confusao(y, s):
    m = confusion_matrix(y, (s >= LIMIAR_FAST_TRACK).astype(int))
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ax.imshow(m, cmap="Blues")
    for (i, j), v in np.ndenumerate(m):
        ax.text(j, i, str(v), ha="center", va="center")
    ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["score < 0,2", "score ≥ 0,2"], yticklabels=["legítimo", "suspeito"],
           title="Matriz de confusão no corte do fast track")
    return fig, m


contrib = contribuicoes(modelo.booster_, Xte).drop(columns="base")
importancia = contrib.abs().mean().sort_values()


def _figura_importancia():
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh([ROTULOS[f] for f in importancia.index], importancia.to_numpy())
    ax.set(xlabel="média de |SHAP| (logito)", title="Importância das features (teste)")
    fig.tight_layout()
    return fig


def _figura_dispersao():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, f in enumerate(importancia.index):
        valor = Xte[f].cat.codes.astype(float) if hasattr(Xte[f], "cat") else Xte[f].astype(float)
        cor = (valor - valor.min()) / (valor.max() - valor.min()) if valor.max() > valor.min() else valor * 0
        jitter = np.random.default_rng(i).uniform(-0.3, 0.3, len(valor))
        ax.scatter(contrib[f], i + jitter, c=cor.fillna(0.5), cmap="coolwarm", s=3, alpha=0.6)
    ax.set_yticks(range(len(importancia)), [ROTULOS[f] for f in importancia.index])
    ax.axvline(0, color="grey", lw=0.8)
    ax.set(xlabel="SHAP (logito): > 0 aumenta a suspeita", title="SHAP por sinistro (cor: valor da feature, azul = baixo)")
    fig.tight_layout()
    return fig


fig_conf, matriz = _figura_confusao(teste["suspeito"], score_te)
with mlflow.start_run(run_id=RUN_ID):
    mlflow.log_figure(_figura_roc(teste["suspeito"], score_te), "curva_roc.png")
    mlflow.log_figure(_figura_pr(teste["suspeito"], score_te), "curva_pr.png")
    mlflow.log_figure(fig_conf, "matriz_confusao_limiar_0_2.png")
    mlflow.log_figure(_figura_importancia(), "shap_importancia.png")
    mlflow.log_figure(_figura_dispersao(), "shap_dispersao.png")
    mlflow.log_table(contrib.sample(min(500, len(contrib)), random_state=0).round(4), "shap_valores_teste.json")
plt.close("all")
print("Matriz de confusão (linhas: legítimo, suspeito; colunas: score < 0,2, score ≥ 0,2):")
print(matriz)
display(pd.DataFrame({"feature": [ROTULOS[f] for f in importancia.index[::-1]],  # noqa: F821
                      "media_abs_shap": importancia.to_numpy()[::-1].round(4)}))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Registro no Unity Catalog (*models from code*)
# MAGIC
# MAGIC - O modelo servido recebe as colunas da silver como estão e devolve `score_suspeita` e `fatores_suspeita`.
# MAGIC - As regras de features viajam junto (`code_paths`), para que o treino e o score usem o mesmo código.
# MAGIC - Antes de seguir, o modelo carregado do UC precisa reproduzir o score do booster.

# COMMAND ----------

pasta = Path(tempfile.mkdtemp())
modelo.booster_.save_model(str(pasta / "booster.txt"))
(pasta / "config.json").write_text(json.dumps({"features": list(Xtr.columns), "com_clima_bruto": False}), encoding="utf-8")
with mlflow.start_run(run_id=RUN_ID):
    info = mlflow.pyfunc.log_model(
        name="modelo",
        python_model=str(Path(ml.__file__).with_name("modelo_pyfunc.py")),
        artifacts={"booster": str(pasta / "booster.txt"), "config": str(pasta / "config.json")},
        code_paths=[str(Path(regras.__file__).parent)],
        signature=assinatura(),
        input_example=preparar_entrada(teste.head(5)),
        pip_requirements=[f"mlflow=={mlflow.__version__}", f"lightgbm=={lgb.__version__}",
                          f"pandas=={pd.__version__}", f"numpy=={np.__version__}"],
        registered_model_name=NOME_MODELO,
    )
VERSAO_MODELO = str(info.registered_model_version)
carregado = mlflow.pyfunc.load_model(f"models:/{NOME_MODELO}/{VERSAO_MODELO}")
saida_teste = carregado.predict(preparar_entrada(teste))
assert np.allclose(saida_teste["score_suspeita"].to_numpy(), score_te), "o modelo do UC não reproduz o score do treino"
print(f"registrado: {NOME_MODELO} versão {VERSAO_MODELO}; score do UC = score do booster em {len(teste)} sinistros")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Checagem fora do tempo: avisos do evento de 2026 (lote 1)
# MAGIC
# MAGIC - Estes avisos passaram pelo pipeline real: OCR dos PDFs, extração por IA e cruzamentos.
# MAGIC - O modelo usado é o **carregado do UC**.
# MAGIC - O gabarito do evento serve só para medir; nunca é usado no treino.

# COMMAND ----------

gab_ev = spark.read.csv(f"{GABARITO}/gabarito_evento_2026.csv", header=True).select("id_aviso", "padrao")  # noqa: F821
evento = (spark.table(f"{SILVER}.sinistros_enriquecidos")  # noqa: F821
          .select("id_aviso", "data_aviso", *COLUNAS_ENTRADA, *COLUNAS_CLIMA_BRUTO)
          .join(gab_ev, "id_aviso", "left").toPandas())
evento["suspeito"] = rotulo_suspeito(evento["padrao"])
saida_ev = carregado.predict(preparar_entrada(evento))
evento = evento.assign(score_suspeita=saida_ev["score_suspeita"].to_numpy(), fatores_suspeita=saida_ev["fatores_suspeita"].to_numpy())
METRICAS_EVENTO = metricas(evento["suspeito"], evento["score_suspeita"], "evento_")
tabela_padrao_evento = por_padrao(evento["padrao"], evento["score_suspeita"])
with mlflow.start_run(run_id=RUN_ID):
    mlflow.log_metrics(METRICAS_EVENTO)
    mlflow.log_table(tabela_padrao_evento, "por_padrao_evento_lote1.json")
display(pd.DataFrame([{"metrica": k, "valor": round(v, 4)} for k, v in METRICAS_EVENTO.items()]))  # noqa: F821
display(tabela_padrao_evento)  # noqa: F821
exemplos = (evento.sort_values("score_suspeita", ascending=False).groupby("padrao").head(1)
            [["id_aviso", "padrao", "score_suspeita", "fatores_suspeita"]].round({"score_suspeita": 3}))
display(exemplos)  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Ablação: e se o clima bruto entrasse no modelo?
# MAGIC
# MAGIC A decisão foi tomada antes, pelo raciocínio de domínio (D-021). Esta ablação só mostra o efeito: é um run
# MAGIC aninhado, sem registro no UC. Ela treina com chuva, rajada e distância até a estação e mede no mesmo teste e no
# MAGIC mesmo lote do evento.

# COMMAND ----------

Xtr_c, Xte_c = montar_features(treino, com_clima_bruto=True), montar_features(teste, com_clima_bruto=True)
Xev_c = montar_features(evento, com_clima_bruto=True)
with mlflow.start_run(run_id=RUN_ID):
    with mlflow.start_run(run_name="ablacao_com_clima_bruto", nested=True):
        mlflow.log_params({**PARAMS_LGBM, "com_clima_bruto": True, "features_treino_versao": VERSAO_FEATURES})
        mlflow.log_input(dataset, context="treino")
        ablacao = treinar(Xtr_c, treino["suspeito"])
        METRICAS_ABLACAO = (metricas(teste["suspeito"], ablacao.predict_proba(Xte_c)[:, 1], "teste_")
                            | metricas(evento["suspeito"], ablacao.predict_proba(Xev_c)[:, 1], "evento_"))
        mlflow.log_metrics(METRICAS_ABLACAO)
        tabela_ablacao_evento = por_padrao(evento["padrao"], ablacao.predict_proba(Xev_c)[:, 1])
        mlflow.log_table(tabela_ablacao_evento, "por_padrao_evento_lote1.json")
comparacao = pd.DataFrame([{"metrica": k, "modelo_registrado": round((METRICAS | METRICAS_EVENTO)[k], 4),
                            "ablacao_com_clima_bruto": round(v, 4)}
                           for k, v in METRICAS_ABLACAO.items() if not k.endswith(("_n", "_n_suspeitos"))])
display(comparacao)  # noqa: F821
display(tabela_padrao_evento.merge(tabela_ablacao_evento, on=["padrao", "n"], suffixes=("_registrado", "_ablacao")))  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Portão de promoção (spec 6.1)
# MAGIC
# MAGIC A versão nova só recebe `champion` se tiver AUC **maior** que o do `champion` atual no mesmo teste. Senão,
# MAGIC recebe `challenger`. A primeira versão vira `champion`. Se o contrato das features mudou (a definição de alguma
# MAGIC feature mudou), o `champion` atual receberia entradas com outro significado: o AUC dele não é comparável, e a
# MAGIC versão nova assume (D-021).

# COMMAND ----------

client = MlflowClient(registry_uri="databricks-uc")
try:
    atual = client.get_model_version_by_alias(NOME_MODELO, "champion")
except MlflowException:
    atual = None
auc_atual = None
contrato_igual = atual is None or (atual.tags or {}).get("contrato_features") == VERSAO_CONTRATO_FEATURES
if atual is not None and str(atual.version) != VERSAO_MODELO and contrato_igual:
    modelo_atual = mlflow.pyfunc.load_model(f"models:/{NOME_MODELO}@champion")
    auc_atual = metricas(teste["suspeito"], modelo_atual.predict(preparar_entrada(teste))["score_suspeita"])["auc"]
ALIAS = decidir_promocao(METRICAS["teste_auc"], auc_atual, contrato_igual=contrato_igual)
client.set_registered_model_alias(NOME_MODELO, ALIAS, VERSAO_MODELO)
for chave, valor in {"teste_auc": f"{METRICAS['teste_auc']:.4f}", "evento_auc": f"{METRICAS_EVENTO['evento_auc']:.4f}",
                     "corte_teste": CORTE_TESTE, "features_treino_versao": str(VERSAO_FEATURES), "alias_decidido": ALIAS,
                     "contrato_features": VERSAO_CONTRATO_FEATURES,
                     "champion_anterior": "nenhum" if atual is None else f"v{atual.version}",
                     "auc_champion_anterior": ("não comparável (outro contrato de features)" if not contrato_igual
                                               else "nenhum" if auc_atual is None else f"{auc_atual:.4f}")}.items():
    client.set_model_version_tag(NOME_MODELO, VERSAO_MODELO, chave, valor)
client.update_registered_model(NOME_MODELO, description=(
    "Score de suspeita de sinistros patrimoniais em eventos climáticos (LightGBM). Entrada: colunas de "
    "silver.sinistros_enriquecidos; saída: score_suspeita (0 a 1) e fatores_suspeita. Score ≥ 0,2 bloqueia o fast "
    "track (spec 6.3). Alias champion = versão em uso; challenger = candidata que não superou o AUC do champion."))
client.update_model_version(NOME_MODELO, VERSAO_MODELO, description=(
    f"Treino jan–set/2025 e teste out–dez/2025 (features_treino v{VERSAO_FEATURES}). AUC teste "
    f"{METRICAS['teste_auc']:.3f}; AUC no lote 1 do evento {METRICAS_EVENTO['evento_auc']:.3f}. Run {RUN_ID}."))
print(f"versão {VERSAO_MODELO} → alias '{ALIAS}' (champion anterior: {None if atual is None else atual.version}; "
      f"mesmo contrato de features: {contrato_igual}; AUC dele no mesmo teste: {auc_atual})")

# COMMAND ----------

resultado = {
    "modelo": NOME_MODELO, "versao": VERSAO_MODELO, "alias": ALIAS, "run_id": RUN_ID,
    "features_treino_versao": VERSAO_FEATURES,
    **{k: round(v, 4) for k, v in (METRICAS | METRICAS_EVENTO).items()},
    "ablacao_teste_auc": round(METRICAS_ABLACAO["teste_auc"], 4),
    "ablacao_evento_auc": round(METRICAS_ABLACAO["evento_auc"], 4),
    "ablacao_evento_suspeitos_abaixo_limiar": round(METRICAS_ABLACAO["evento_suspeitos_abaixo_limiar"], 4),
    "ablacao_evento_legitimos_abaixo_limiar": round(METRICAS_ABLACAO["evento_legitimos_abaixo_limiar"], 4),
}
print(json.dumps(resultado, ensure_ascii=False, indent=2))
dbutils.notebook.exit(json.dumps(resultado, ensure_ascii=False))  # noqa: F821

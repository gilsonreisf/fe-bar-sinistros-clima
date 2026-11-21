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
# MAGIC Cada score acima do limiar traz os fatores que mais pesaram, em português, para o regulador e para o parecer.
# MAGIC
# MAGIC **Dados.**
# MAGIC - `silver.historico_enriquecido`: 20 mil sinistros regulados em 2025, com as **mesmas features** do evento,
# MAGIC   calculadas pelas mesmas regras do pipeline.
# MAGIC - Rótulo: `restrito/gabarito/gabarito_historico_2025.csv`. Alvo `suspeito` = padrão diferente de `legitimo_*`.
# MAGIC
# MAGIC **Validação.**
# MAGIC - Split temporal: treino de jan a set e teste de out a dez/2025.
# MAGIC - Checagem fora do tempo nos lotes de validação do evento de 2026 (parâmetro `lotes_validacao`, padrão: lote 1).
# MAGIC - Os demais lotes são o teste final, na fase 5.
# MAGIC
# MAGIC **Decisões (D-021):**
# MAGIC - o clima bruto fica fora do modelo (no histórico ele se confunde com a fonte da evidência, porque não há
# MAGIC   Defesa Civil em 2025); uma ablação mostra o efeito;
# MAGIC - SHAP pelo próprio LightGBM (TreeSHAP exato);
# MAGIC - participação do prestador point-in-time e suavizada.
# MAGIC
# MAGIC **Leitura honesta das métricas.**
# MAGIC - Os padrões sintéticos foram plantados com sinais claros. Cinco dos sete padrões suspeitos saem de regras simples
# MAGIC   (sem cobertura, evidência contrária, apólice com menos de 30 dias, laudo com dano anterior e preço ≥ 30% acima
# MAGIC   da tabela). Por isso o notebook mede também essa **linha de base de regras** no mesmo teste.
# MAGIC - O ganho do modelo está no que regra fixa não pega (prestador concentrado) e no **ranking** para a fila.
# MAGIC - No lote 1, só os orçamentos inflados e os danos preexistentes dependem do OCR e da extração por IA; a evidência
# MAGIC   climática vem de joins estruturados.
# MAGIC - Com dados reais, o desempenho seria menor, e a calibração viria da PoC.

# COMMAND ----------

import json
import tempfile
from importlib.metadata import version as versao_pacote
from pathlib import Path

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from pyspark.sql import functions as F
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_curve

import ml
import regras
from ml.treino import (CORTE_TESTE, FRACAO_TOPO, LIMIAR_FAST_TRACK, PARAMS_LGBM, PISO_AUC, TETO_SUSPEITOS_ABAIXO_LIMIAR,
                       assinatura, contribuicoes, decidir_promocao, dividir_temporal, metricas, metricas_fast_track,
                       passa_piso, por_padrao, regra_base, treinar)
from regras.features import (COLUNAS_CLIMA_BRUTO, COLUNAS_ENTRADA, COLUNAS_PROIBIDAS, FEATURES, ROTULOS,
                             VERSAO_CONTRATO_FEATURES, montar_features, preparar_entrada, rotulo_suspeito)

dbutils.widgets.text("lotes_validacao", "1")  # noqa: F821 (dbutils é injetado pelo Databricks)
for nome in ("catalogo", "schema_silver", "schema_ml", "experimento"):
    dbutils.widgets.text(nome, "")  # noqa: F821
catalogo, schema_silver, schema_ml, experimento = (dbutils.widgets.get(n) for n in  # noqa: F821
                                                   ("catalogo", "schema_silver", "schema_ml", "experimento"))
LOTES_VALIDACAO = sorted({int(x) for x in dbutils.widgets.get("lotes_validacao").split(",") if x.strip()})  # noqa: F821
assert all((catalogo, schema_silver, schema_ml, experimento)) and LOTES_VALIDACAO, "parâmetros do job ausentes"
SILVER, ML = f"{catalogo}.{schema_silver}", f"{catalogo}.{schema_ml}"
NOME_MODELO = f"{ML}.modelo_suspeita"
TABELA_FEATURES = f"{ML}.features_treino"
GABARITO = f"/Volumes/{catalogo}/{schema_ml}/restrito/gabarito"
VERSOES = {p: versao_pacote(p) for p in ("mlflow", "lightgbm", "scikit-learn", "matplotlib", "pandas", "numpy")}
print(f"modelo: {NOME_MODELO} | features: {TABELA_FEATURES} | experimento: {experimento} | "
      f"lotes de validação: {LOTES_VALIDACAO}")
print("versões:", VERSOES)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Dados de treino: histórico enriquecido + rótulo do gabarito restrito
# MAGIC
# MAGIC Duas checagens de segurança:
# MAGIC - as colunas de entrada existem com o mesmo nome nas duas tabelas silver (treino e evento);
# MAGIC - nenhuma coluna que vaza o rótulo entra nas features.
# MAGIC
# MAGIC O resultado vai para `ml.features_treino`, uma tabela Delta versionada, para o `log_input` do MLflow. As linhas
# MAGIC são lidas em ordem fixa (`id_sinistro`) e o LightGBM roda em modo determinístico: a mesma versão Delta dá o mesmo
# MAGIC modelo.

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

df = spark.sql(f"SELECT * FROM {TABELA_FEATURES} VERSION AS OF {VERSAO_FEATURES} ORDER BY id_sinistro").toPandas()  # noqa: F821
assert len(df) == hist.count(), "o join com o gabarito mudou o número de linhas"
assert (rotulo_suspeito(df["padrao"]) == df["suspeito"]).all()  # falha se algum sinistro ficou sem padrão
treino, teste = dividir_temporal(df)
assert set(treino["conjunto"]) == {"treino"} and set(teste["conjunto"]) == {"teste"}
print(f"features_treino versão {VERSAO_FEATURES}: {len(treino)} treino, {len(teste)} teste")
display(df.groupby(["padrao", "conjunto"]).size().unstack("conjunto").reset_index())  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Treino (LightGBM), métricas e linha de base de regras
# MAGIC
# MAGIC Métricas da spec 6.1: AUC, e precisão e recall nos 10% mais suspeitos. Como a prevalência passa de 10%, o recall
# MAGIC nos 10% do topo tem um teto (`recall_top10_teto`). Métricas de negócio (spec 6.3):
# MAGIC - `suspeitos_abaixo_limiar`: fração dos suspeitos com score < 0,2, que escapariam do bloqueio do fast track;
# MAGIC - `legitimos_abaixo_limiar`: fração dos legítimos que seguem elegíveis ao fast track;
# MAGIC - `ft_*`: o mesmo, só na população que concorre ao fast track (≤ R$ 5 mil, com cobertura e evidência forte).
# MAGIC
# MAGIC A **linha de base** é o OU das regras simples. Ela é medida com as mesmas métricas, com score 0 ou 1.

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experimento)
consulta = f"SELECT * FROM {TABELA_FEATURES} VERSION AS OF {VERSAO_FEATURES} WHERE conjunto = '{{}}' ORDER BY id_sinistro"
datasets = {c: mlflow.data.from_spark(spark.sql(consulta.format(c)), table_name=TABELA_FEATURES,  # noqa: F821
                                      version=str(VERSAO_FEATURES), name=f"features_treino_{c}")
            for c in ("treino", "teste")}

Xtr, Xte = montar_features(treino), montar_features(teste)
with mlflow.start_run(run_name="lightgbm_sem_clima_bruto") as run:
    RUN_ID = run.info.run_id
    mlflow.log_params({**PARAMS_LGBM, "corte_teste": CORTE_TESTE, "limiar_fast_track": LIMIAR_FAST_TRACK,
                       "fracao_topo": FRACAO_TOPO, "features": ",".join(FEATURES), "com_clima_bruto": False,
                       "contrato_features": VERSAO_CONTRATO_FEATURES, "piso_auc": PISO_AUC,
                       "teto_suspeitos_abaixo_limiar": TETO_SUSPEITOS_ABAIXO_LIMIAR,
                       "features_treino_tabela": TABELA_FEATURES, "features_treino_versao": VERSAO_FEATURES,
                       "lotes_validacao": ",".join(map(str, LOTES_VALIDACAO)),
                       "n_treino": len(treino), "n_teste": len(teste),
                       **{f"versao_{p}": v for p, v in VERSOES.items()}})
    for contexto, ds in datasets.items():
        mlflow.log_input(ds, context=contexto)
    mlflow.set_tags({"fase": "3", "decisao": "D-021", "alvo": "suspeito = padrao != legitimo_*"})
    modelo = treinar(Xtr, treino["suspeito"])
    score_tr, score_te = modelo.predict_proba(Xtr)[:, 1], modelo.predict_proba(Xte)[:, 1]
    regra_te = regra_base(teste)
    METRICAS = (metricas(treino["suspeito"], score_tr, "treino_") | metricas(teste["suspeito"], score_te, "teste_")
                | metricas_fast_track(teste, teste["suspeito"], score_te, "teste_"))
    METRICAS_REGRA = (metricas(teste["suspeito"], regra_te, "regra_teste_")
                      | metricas_fast_track(teste, teste["suspeito"], regra_te, "regra_teste_"))
    mlflow.log_metrics(METRICAS | METRICAS_REGRA)
    tabela_padrao_teste = por_padrao(teste["padrao"], score_te).merge(
        por_padrao(teste["padrao"], regra_te)[["padrao", "pct_acima_limiar"]].rename(
            columns={"pct_acima_limiar": "pct_bloqueado_pela_regra"}), on="padrao")
    mlflow.log_table(tabela_padrao_teste, "por_padrao_teste.json")

display(pd.DataFrame([{"metrica": k.removeprefix("teste_"), "modelo": round(v, 4),  # noqa: F821
                       "regra_base": round(METRICAS_REGRA.get(f"regra_{k}", float("nan")), 4)}
                      for k, v in METRICAS.items() if k.startswith("teste_")]))
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
# MAGIC - O modelo servido recebe as colunas de entrada da silver, tipadas por `preparar_entrada`, e devolve
# MAGIC   `score_suspeita` e `fatores_suspeita`.
# MAGIC - O `features.py` do treino vai como artefato e é carregado por caminho, com nome de módulo único. Assim, o
# MAGIC   modelo usa o próprio código mesmo num processo que já importou `regras`.
# MAGIC - Antes de seguir, o modelo carregado do UC precisa reproduzir o score do booster.

# COMMAND ----------

pasta = Path(tempfile.mkdtemp())
modelo.booster_.save_model(str(pasta / "booster.txt"))
(pasta / "config.json").write_text(json.dumps({"features": list(Xtr.columns), "com_clima_bruto": False}), encoding="utf-8")
with mlflow.start_run(run_id=RUN_ID):
    info = mlflow.pyfunc.log_model(
        name="modelo",
        python_model=str(Path(ml.__file__).with_name("modelo_pyfunc.py")),
        artifacts={"booster": str(pasta / "booster.txt"), "config": str(pasta / "config.json"),
                   "features": str(Path(regras.__file__).with_name("features.py"))},
        signature=assinatura(),
        input_example=preparar_entrada(teste.head(5)),
        pip_requirements=[f"mlflow=={VERSOES['mlflow']}", f"lightgbm=={VERSOES['lightgbm']}",
                          f"pandas=={VERSOES['pandas']}", f"numpy=={VERSOES['numpy']}"],
        registered_model_name=NOME_MODELO,
    )
VERSAO_MODELO = str(info.registered_model_version)
carregado = mlflow.pyfunc.load_model(f"models:/{NOME_MODELO}/{VERSAO_MODELO}")
saida_teste = carregado.predict(preparar_entrada(teste))
assert np.allclose(saida_teste["score_suspeita"].to_numpy(), score_te), "o modelo do UC não reproduz o score do treino"
print(f"registrado: {NOME_MODELO} versão {VERSAO_MODELO}; score do UC = score do booster em {len(teste)} sinistros")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Checagem fora do tempo: lotes de validação do evento de 2026
# MAGIC
# MAGIC - Estes avisos passaram pelo pipeline real: OCR dos PDFs, extração por IA e cruzamentos.
# MAGIC - O modelo usado é o **carregado do UC**.
# MAGIC - Só entram os lotes de validação (`lotes_validacao`); os demais são o teste final da fase 5 e não são tocados.
# MAGIC - O gabarito do evento serve só para medir; nunca é usado no treino.

# COMMAND ----------

gab_ev = spark.read.csv(f"{GABARITO}/gabarito_evento_2026.csv", header=True).select("id_aviso", "padrao")  # noqa: F821
lote = (spark.table(f"{SILVER}.avisos")  # noqa: F821
        .select("id_aviso", F.regexp_extract("_arquivo", r"avisos_lote_([0-9]+)", 1).cast("int").alias("lote")))
evento = (spark.table(f"{SILVER}.sinistros_enriquecidos")  # noqa: F821
          .select("id_aviso", "data_aviso", *COLUNAS_ENTRADA, *COLUNAS_CLIMA_BRUTO)
          .join(lote, "id_aviso").where(F.col("lote").isin(LOTES_VALIDACAO))
          .join(gab_ev, "id_aviso", "left").orderBy("id_aviso").toPandas())
METRICAS_EVENTO, tabela_padrao_evento = {}, pd.DataFrame(columns=["padrao", "n"])
if evento.empty:
    print(f"Nenhum aviso dos lotes {LOTES_VALIDACAO} no pipeline ainda: checagem fora do tempo pulada.")
else:
    evento["suspeito"] = rotulo_suspeito(evento["padrao"])
    saida_ev = carregado.predict(preparar_entrada(evento))
    evento = evento.assign(score_suspeita=saida_ev["score_suspeita"].to_numpy(),
                           fatores_suspeita=saida_ev["fatores_suspeita"].to_numpy())
    regra_ev = regra_base(evento)
    METRICAS_EVENTO = (metricas(evento["suspeito"], evento["score_suspeita"], "evento_")
                       | metricas_fast_track(evento, evento["suspeito"], evento["score_suspeita"], "evento_"))
    METRICAS_REGRA_EVENTO = (metricas(evento["suspeito"], regra_ev, "regra_evento_")
                             | metricas_fast_track(evento, evento["suspeito"], regra_ev, "regra_evento_"))
    tabela_padrao_evento = por_padrao(evento["padrao"], evento["score_suspeita"]).merge(
        por_padrao(evento["padrao"], regra_ev)[["padrao", "pct_acima_limiar"]].rename(
            columns={"pct_acima_limiar": "pct_bloqueado_pela_regra"}), on="padrao")
    with mlflow.start_run(run_id=RUN_ID):
        mlflow.log_metrics(METRICAS_EVENTO | METRICAS_REGRA_EVENTO)
        mlflow.log_table(tabela_padrao_evento, "por_padrao_evento_validacao.json")
    display(pd.DataFrame([{"metrica": k.removeprefix("evento_"), "modelo": round(v, 4),  # noqa: F821
                           "regra_base": round(METRICAS_REGRA_EVENTO.get(f"regra_{k}", float("nan")), 4)}
                          for k, v in METRICAS_EVENTO.items()]))
    display(tabela_padrao_evento)  # noqa: F821
    exemplos = (evento.sort_values("score_suspeita", ascending=False).groupby("padrao").head(1)
                [["id_aviso", "padrao", "score_suspeita", "fatores_suspeita"]].round({"score_suspeita": 3}))
    display(exemplos)  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Ablação: e se o clima bruto entrasse no modelo?
# MAGIC
# MAGIC A decisão foi tomada antes, pelo raciocínio de domínio (D-021). Esta ablação só mostra o efeito: é um run
# MAGIC aninhado, sem registro no UC. Ela treina com chuva, rajada e distância até a estação e mede no mesmo teste e nos
# MAGIC mesmos lotes de validação.

# COMMAND ----------

Xtr_c, Xte_c = montar_features(treino, com_clima_bruto=True), montar_features(teste, com_clima_bruto=True)
with mlflow.start_run(run_id=RUN_ID):
    with mlflow.start_run(run_name="ablacao_com_clima_bruto", nested=True):
        mlflow.log_params({**PARAMS_LGBM, "com_clima_bruto": True, "features_treino_versao": VERSAO_FEATURES})
        mlflow.log_input(datasets["treino"], context="treino")
        ablacao = treinar(Xtr_c, treino["suspeito"])
        METRICAS_ABLACAO = metricas(teste["suspeito"], ablacao.predict_proba(Xte_c)[:, 1], "teste_")
        if not evento.empty:
            score_ablacao_ev = ablacao.predict_proba(montar_features(evento, com_clima_bruto=True))[:, 1]
            METRICAS_ABLACAO |= metricas(evento["suspeito"], score_ablacao_ev, "evento_")
            mlflow.log_table(por_padrao(evento["padrao"], score_ablacao_ev), "por_padrao_evento_validacao.json")
        mlflow.log_metrics(METRICAS_ABLACAO)
comparacao = pd.DataFrame([{"metrica": k, "modelo_registrado": round((METRICAS | METRICAS_EVENTO)[k], 4),
                            "ablacao_com_clima_bruto": round(v, 4)}
                           for k, v in METRICAS_ABLACAO.items() if not k.endswith(("_n", "_n_suspeitos"))])
display(comparacao)  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Portão de promoção (spec 6.1)
# MAGIC
# MAGIC - **Piso absoluto:** AUC de teste ≥ 0,80 e no máximo 10% dos suspeitos do teste abaixo de 0,2. Sem ele, a versão
# MAGIC   nunca vira `champion`.
# MAGIC - **Comparação:** com o mesmo contrato de features, a versão nova só vira `champion` com AUC **maior** que o do
# MAGIC   `champion` atual no mesmo teste. Senão, vira `challenger`.
# MAGIC - **Outro contrato:** se a definição de alguma feature mudou, o `champion` atual receberia entradas com outro
# MAGIC   significado. O AUC dele não é comparável, e a versão nova assume se passar no piso (D-021).
# MAGIC - **Aliases:** são lidos da lista do modelo registrado, sem engolir erro de permissão ou rede. Ao promover, o
# MAGIC   `challenger` antigo é removido.

# COMMAND ----------

client = MlflowClient(registry_uri="databricks-uc")
brutos = client.get_registered_model(NOME_MODELO).aliases or {}  # dict {alias: versão} (ou lista, em versões antigas)
aliases = {str(k): str(v) for k, v in (brutos.items() if isinstance(brutos, dict)
                                       else ((a.alias, a.version) for a in brutos))}
atual = client.get_model_version(NOME_MODELO, aliases["champion"]) if "champion" in aliases else None
contrato_igual = atual is None or (atual.tags or {}).get("contrato_features") == VERSAO_CONTRATO_FEATURES
auc_atual = None
if atual is not None and str(atual.version) != VERSAO_MODELO and contrato_igual:
    modelo_atual = mlflow.pyfunc.load_model(f"models:/{NOME_MODELO}/{atual.version}")
    auc_atual = metricas(teste["suspeito"], modelo_atual.predict(preparar_entrada(teste))["score_suspeita"])["auc"]
PASSOU_PISO = passa_piso(METRICAS)
ALIAS = decidir_promocao(METRICAS["teste_auc"], auc_atual, contrato_igual=contrato_igual, passou_piso=PASSOU_PISO)
client.set_registered_model_alias(NOME_MODELO, ALIAS, VERSAO_MODELO)
if ALIAS == "champion" and aliases.get("challenger") not in (None, VERSAO_MODELO):
    client.delete_registered_model_alias(NOME_MODELO, "challenger")  # candidata antiga deixa de valer
tags = {"teste_auc": f"{METRICAS['teste_auc']:.4f}", "corte_teste": CORTE_TESTE,
        "features_treino_versao": str(VERSAO_FEATURES), "alias_decidido": ALIAS, "passou_piso": str(PASSOU_PISO),
        "contrato_features": VERSAO_CONTRATO_FEATURES, "lotes_validacao": ",".join(map(str, LOTES_VALIDACAO)),
        "champion_anterior": "nenhum" if atual is None else f"v{atual.version}",
        "auc_champion_anterior": ("não comparável (outro contrato de features)" if not contrato_igual
                                  else "nenhum" if auc_atual is None else f"{auc_atual:.4f}")}
if METRICAS_EVENTO:
    tags["evento_validacao_auc"] = f"{METRICAS_EVENTO['evento_auc']:.4f}"
for chave, valor in tags.items():
    client.set_model_version_tag(NOME_MODELO, VERSAO_MODELO, chave, valor)
client.update_registered_model(NOME_MODELO, description=(
    "Score de suspeita de sinistros patrimoniais em eventos climáticos (LightGBM). Entrada: colunas de "
    "silver.sinistros_enriquecidos tipadas por regras.features.preparar_entrada; saída: score_suspeita (0 a 1) e "
    "fatores_suspeita. Score ≥ 0,2 bloqueia o fast track (spec 6.3). Alias champion = versão em uso; challenger = "
    "candidata que não superou o champion ou o piso."))
client.update_model_version(NOME_MODELO, VERSAO_MODELO, description=(
    f"Treino jan–set/2025 e teste out–dez/2025 (features_treino v{VERSAO_FEATURES}, contrato "
    f"{VERSAO_CONTRATO_FEATURES}). AUC teste {METRICAS['teste_auc']:.3f}"
    + (f"; AUC nos lotes de validação {LOTES_VALIDACAO} do evento {METRICAS_EVENTO['evento_auc']:.3f}"
       if METRICAS_EVENTO else "") + f". Run {RUN_ID}."))
print(f"versão {VERSAO_MODELO} → alias '{ALIAS}' (piso: {PASSOU_PISO}; champion anterior: "
      f"{None if atual is None else atual.version}; mesmo contrato: {contrato_igual}; AUC dele no mesmo teste: {auc_atual})")

# COMMAND ----------

resultado = {
    "modelo": NOME_MODELO, "versao": VERSAO_MODELO, "alias": ALIAS, "run_id": RUN_ID,
    "features_treino_versao": VERSAO_FEATURES, "lotes_validacao": LOTES_VALIDACAO, "passou_piso": PASSOU_PISO,
    **{k: round(v, 4) for k, v in (METRICAS | METRICAS_REGRA | METRICAS_EVENTO).items()},
    **{f"ablacao_{k}": round(v, 4) for k, v in METRICAS_ABLACAO.items() if k.endswith(("auc", "abaixo_limiar"))},
}
print(json.dumps(resultado, ensure_ascii=False, indent=2))
dbutils.notebook.exit(json.dumps(resultado, ensure_ascii=False))  # noqa: F821

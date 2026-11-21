# Databricks notebook source
# MAGIC %md
# MAGIC # Parecer prévio por IA: avaliação, portão de qualidade, registro e endpoint
# MAGIC
# MAGIC **Problema de negócio.** O regulador gasta a maior parte do tempo lendo orçamento, laudo, apólice e dados do
# MAGIC clima para chegar a uma recomendação que, na maioria dos casos, é previsível. O **parecer prévio** faz essa
# MAGIC leitura e entrega ao regulador:
# MAGIC - a recomendação (`pagar_integral`, `pagar_parcial`, `recusar` ou `investigar`);
# MAGIC - o valor sugerido;
# MAGIC - os motivos e as cláusulas.
# MAGIC
# MAGIC A decisão continua com o regulador: a IA nunca recusa sozinha.
# MAGIC
# MAGIC **Como funciona (D-022).**
# MAGIC - O Claude Sonnet aplica as regras às evidências (`silver.entrada_parecer` + score do `modelo_suspeita@champion`)
# MAGIC   e escolhe a recomendação e a **base** do valor.
# MAGIC - O código valida o JSON (com uma nova tentativa) e **calcula o valor**: franquia, LMI e itens excluídos.
# MAGIC
# MAGIC **O que este notebook faz.**
# MAGIC 1. Dataset estratificado dos lotes de validação do evento, com o gabarito como expectativa, salvo como MLflow
# MAGIC    Evaluation Dataset no UC.
# MAGIC 2. Prompts v1 (básico) e v2 (regras explícitas e exemplos) versionados no UC (tabela Delta, porque o
# MAGIC    Prompt Registry não está habilitado no workspace; D-022).
# MAGIC 3. `mlflow.genai.evaluate()` dos dois prompts, com métricas de código e juízes LLM (`Correctness` e `Guidelines`).
# MAGIC 4. Portão de qualidade: o alias `producao` do prompt só muda se `recomendacao_correta` não piorar.
# MAGIC 5. Registro de `ml.parecer_sinistro` (*models from code*, com o prompt de produção congelado) e publicação do
# MAGIC    endpoint com AI Gateway (inference table e usage tracking) e tracing.
# MAGIC
# MAGIC **Leitura honesta.**
# MAGIC - O modelo não aceita `temperature`, então há variação entre execuções.
# MAGIC - O dataset é pequeno (até 25 casos por padrão).
# MAGIC - Diferenças de poucos pontos entre v1 e v2 estão dentro do ruído.

# COMMAND ----------

import json
import os
import tempfile
from importlib.metadata import version as versao_pacote
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from databricks.sdk import WorkspaceClient
from mlflow import MlflowClient
from mlflow.genai.scorers import Correctness, Guidelines, scorer
from mlflow.models.resources import DatabricksServingEndpoint
from pyspark.sql import functions as F

import parecer
from parecer import avaliacao as av
from parecer.endpoint import api_do_workspace, config_endpoint, publicar_endpoint
from parecer.esquema import RECOMENDACOES
from parecer.gerar import chamar_llm_databricks, gerar_parecer, juntar_score
from parecer.modelo_pyfunc import assinatura_parecer
from parecer.prompts import PROMPTS
from regras.features import COLUNAS_ENTRADA, preparar_entrada

PARAMETROS = {"catalogo": "", "schema_silver": "", "schema_ml": "", "experimento": "", "endpoint_llm": "",
              "endpoint_parecer": "", "lotes_validacao": "1", "max_por_padrao": "25", "publicar": "sim"}
for nome, padrao in PARAMETROS.items():
    dbutils.widgets.text(nome, padrao)  # noqa: F821 (dbutils é injetado pelo Databricks)
P = {nome: dbutils.widgets.get(nome) for nome in PARAMETROS}  # noqa: F821
assert all(P.values()), f"parâmetros do job ausentes: {[k for k, v in P.items() if not v]}"
SILVER, ML = f"{P['catalogo']}.{P['schema_silver']}", f"{P['catalogo']}.{P['schema_ml']}"
LOTES = sorted({int(x) for x in P["lotes_validacao"].split(",") if x.strip()})
# publicar = "nao": só avalia (ex.: comparar outro LLM no mesmo dataset), sem mexer no alias, no modelo nem no endpoint
PUBLICAR = P["publicar"].strip().lower() == "sim"
SUFIXO_RUN = "" if PUBLICAR else f"_{P['endpoint_llm'].removeprefix('databricks-')}"
NOME_PROMPT, NOME_MODELO = f"{ML}.prompt_parecer", f"{ML}.parecer_sinistro"
NOME_DATASET = f"{ML}.avaliacao_parecer_dataset"
GABARITO = f"/Volumes/{P['catalogo']}/{P['schema_ml']}/restrito/gabarito"
VERSOES = {p: versao_pacote(p) for p in ("mlflow", "databricks-sdk", "pandas", "numpy")}
os.environ.setdefault("MLFLOW_GENAI_EVAL_MAX_WORKERS", "8")  # paralelismo moderado no FMAPI (pay-per-token)
mlflow.set_registry_uri("databricks-uc")
EXPERIMENTO_ID = mlflow.set_experiment(P["experimento"]).experiment_id
print(f"prompt: {NOME_PROMPT} | modelo: {NOME_MODELO} | dataset: {NOME_DATASET} | LLM: {P['endpoint_llm']} | "
      f"endpoint: {P['endpoint_parecer']} | lotes: {LOTES}")
print("versões:", VERSOES)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Dataset de avaliação
# MAGIC
# MAGIC - **Casos:** sinistros dos lotes de validação, com a entrada do parecer e o score do `modelo_suspeita@champion`.
# MAGIC - **Amostra:** estratificada, com até `max_por_padrao` casos por padrão.
# MAGIC - **Expectativas, só do gabarito restrito:** recomendação esperada, valor devido, fatos esperados (juiz
# MAGIC   `Correctness`) e a cláusula que um parecer correto cita. O gabarito nunca entra na entrada do parecer.

# COMMAND ----------

lote = (spark.table(f"{SILVER}.avisos")  # noqa: F821
        .select("id_aviso", F.regexp_extract("_arquivo", r"avisos_lote_([0-9]+)", 1).cast("int").alias("lote")))
gab = (spark.read.csv(f"{GABARITO}/gabarito_evento_2026.csv", header=True)  # noqa: F821
       .select("id_aviso", "padrao", "decisao_esperada", F.col("valor_devido").cast("double").alias("valor_devido")))
casos = (spark.table(f"{SILVER}.entrada_parecer")  # noqa: F821
         .join(spark.table(f"{SILVER}.sinistros_enriquecidos").select("id_aviso", "cobertura_necessaria", *COLUNAS_ENTRADA),  # noqa: F821
               "id_aviso")
         .join(lote, "id_aviso").where(F.col("lote").isin(LOTES))
         .join(gab, "id_aviso").orderBy("id_aviso").toPandas())
assert not casos.empty, f"nenhum sinistro dos lotes {LOTES} no pipeline"
suspeita = mlflow.pyfunc.load_model(f"models:/{ML}.modelo_suspeita@champion")
saida_suspeita = suspeita.predict(preparar_entrada(casos))
casos["score_suspeita"] = saida_suspeita["score_suspeita"].to_numpy()
casos["fatores_suspeita"] = saida_suspeita["fatores_suspeita"].to_numpy()
amostra = av.amostra_estratificada(casos, "padrao", int(P["max_por_padrao"]), seed=42)
registros = [{"inputs": {"entrada": juntar_score(json.loads(r.entrada_json), r.score_suspeita, r.fatores_suspeita)},
              "expectations": av.expectativas(r.padrao, r.decisao_esperada, r.valor_devido, r.cobertura_necessaria)}
             for r in amostra.itertuples()]

if not PUBLICAR:  # comparação de LLM: usa os mesmos casos, sem recriar o dataset de produção
    dataset = registros
try:  # recriado a cada execução publicada: o dataset reflete os lotes de validação atuais
    mlflow.genai.datasets.get_dataset(name=NOME_DATASET)
    existe = True
except Exception as e:  # noqa: BLE001 (o código do erro de "não existe" varia; qualquer outro erro reaparece no create)
    existe, motivo = False, f"{type(e).__name__}: {str(e)[:120]}"
if existe and PUBLICAR:
    mlflow.genai.datasets.delete_dataset(name=NOME_DATASET)
if PUBLICAR:
    # no Databricks, create_dataset não aceita tags (a governança é do UC): a descrição vai como COMMENT da tabela
    dataset = mlflow.genai.datasets.create_dataset(name=NOME_DATASET, experiment_id=[EXPERIMENTO_ID])
    dataset.merge_records(registros)
    spark.sql(f"COMMENT ON TABLE {NOME_DATASET} IS 'Avaliação do parecer prévio: {len(registros)} casos estratificados "  # noqa: F821
              f"dos lotes de validação {P['lotes_validacao']} do evento, com expectativas do gabarito (spec 6.4).'")
print(f"{len(registros)} casos de {len(casos)} sinistros dos lotes {LOTES} → {NOME_DATASET}")
display(amostra.groupby("padrao").size().rename("casos").reset_index())  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Prompts versionados no UC
# MAGIC
# MAGIC O Prompt Registry do MLflow não está habilitado neste workspace (`FEATURE_DISABLED`; D-022). Os prompts ficam
# MAGIC numa tabela Delta do UC (`ml.prompt_parecer`), com as mesmas operações:
# MAGIC - versão nova só quando o texto muda (sha256);
# MAGIC - alias de produção;
# MAGIC - métrica de qualidade por versão;
# MAGIC - o histórico Delta da tabela é a trilha de auditoria.

# COMMAND ----------

ESQUEMA_PROMPTS = ("versao BIGINT, rotulo STRING, template STRING, sha256 STRING, mensagem STRING, criado_em STRING, "
                   "recomendacao_correta DOUBLE, producao BOOLEAN")


def _ler_prompts() -> pd.DataFrame:
    if not spark.catalog.tableExists(NOME_PROMPT):  # noqa: F821
        return av.tabela_prompts_vazia()
    return spark.table(NOME_PROMPT).toPandas()[av.COLUNAS_PROMPTS]  # noqa: F821


def _gravar_prompts(tabela: pd.DataFrame) -> None:
    (spark.createDataFrame(tabela[av.COLUNAS_PROMPTS], ESQUEMA_PROMPTS)  # noqa: F821
     .write.mode("overwrite").saveAsTable(NOME_PROMPT))
    spark.sql(f"COMMENT ON TABLE {NOME_PROMPT} IS 'Versões do prompt do parecer prévio (uma linha por versão; producao = "  # noqa: F821
              "alias de produção). Histórico Delta = auditoria (D-022).'")


TABELA_PROMPTS = _ler_prompts()
VERSOES_PROMPT = {}
agora = pd.Timestamp.now(tz="UTC").isoformat()
for chave, texto in PROMPTS.items():
    mensagem = f"Parecer prévio {chave}: " + ("básico" if chave == "v1" else "regras explícitas, ordem e exemplos")
    TABELA_PROMPTS, VERSOES_PROMPT[chave], nova = av.registrar_versao(TABELA_PROMPTS, texto, chave, mensagem, agora)
    print(f"{chave}: versão {VERSOES_PROMPT[chave]} ({'nova' if nova else 'reaproveitada'})")
if PUBLICAR:
    _gravar_prompts(TABELA_PROMPTS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Avaliação dos dois prompts (`mlflow.genai.evaluate`)
# MAGIC
# MAGIC **Métricas de código:**
# MAGIC - `recomendacao_correta`: recomendação igual à do gabarito;
# MAGIC - `json_valido`: o parecer passou na validação;
# MAGIC - `padrao_identificado`: os motivos citam o fato que caracteriza o padrão;
# MAGIC - `cita_clausula`: cita a cláusula esperada;
# MAGIC - `valor_dentro_tolerancia`: ±10% do devido, só nos casos com pagamento esperado, calculado fora dos scorers para
# MAGIC   não misturar tipos.
# MAGIC
# MAGIC **Juízes LLM:**
# MAGIC - `Correctness`: os fatos esperados estão no parecer;
# MAGIC - `Guidelines`: português formal, não recusar sem evidência objetiva, citar cobertura ou evidência, tom
# MAGIC   respeitoso.
# MAGIC
# MAGIC Cada caso gera um trace.

# COMMAND ----------

@scorer(name="recomendacao_correta")
def s_recomendacao(outputs, expectations):
    return av.recomendacao_correta(outputs, expectations)


@scorer(name="json_valido")
def s_json(outputs):
    return av.json_valido(outputs)


@scorer(name="padrao_identificado")
def s_padrao(outputs, expectations):
    return av.padrao_identificado(outputs, expectations)


@scorer(name="cita_clausula")
def s_clausula(outputs, expectations):
    return av.cita_clausula(outputs, expectations)


DIRETRIZES = Guidelines(name="diretrizes_parecer", guidelines=[
    "A resposta está em português formal.",
    "Não recomenda recusar sem citar a ausência de cobertura ou outra evidência objetiva dos dados do sinistro.",
    "Os motivos citam a cobertura, a evidência climática ou os documentos que fundamentam a recomendação.",
    "O tom é respeitoso com o segurado e não faz acusações de fraude; descreve fatos.",
])
SCORERS = [s_recomendacao, s_json, s_padrao, s_clausula, Correctness(), DIRETRIZES]
chamar = chamar_llm_databricks(P["endpoint_llm"])


def _tabela(resultado) -> pd.DataFrame:
    df = resultado.result_df
    resposta = df["response"].apply(lambda r: r if isinstance(r, dict) else {})
    t = pd.DataFrame({
        "id_aviso": df["request"].apply(lambda r: r["entrada"]["aviso"].get("id_aviso")),
        "padrao": df["padrao/value"], "esperado": df["recomendacao_esperada/value"],
        "obtido": resposta.apply(lambda r: r.get("recomendacao")),
        "valor_devido": df["valor_devido/value"].astype(float),
        "valor_sugerido": resposta.apply(lambda r: r.get("valor_sugerido")).astype(float),
        "status": resposta.apply(lambda r: r.get("status_parecer")),
        "dias_desde_contratacao": df["request"].apply(lambda r: (r["entrada"].get("apolice") or {}).get("dias_desde_contratacao")),
        "motivos": resposta.apply(lambda r: " | ".join(r.get("motivos") or [])[:300]),
        "trace_id": df["trace_id"]})
    t["correto"] = t["esperado"] == t["obtido"]
    return t


def _figura_confusao(t: pd.DataFrame, titulo: str):
    m = pd.crosstab(t["esperado"], t["obtido"]).reindex(index=RECOMENDACOES, columns=RECOMENDACOES, fill_value=0)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(m.to_numpy(), cmap="Blues")
    for (i, j), v in np.ndenumerate(m.to_numpy()):
        ax.text(j, i, str(v), ha="center", va="center")
    ax.set(xticks=range(4), yticks=range(4), xticklabels=RECOMENDACOES, yticklabels=RECOMENDACOES,
           xlabel="recomendação do parecer", ylabel="recomendação esperada (gabarito)", title=titulo)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    fig.tight_layout()
    return fig, m


RESULTADOS, TABELAS, RUNS = {}, {}, {}
for chave, versao in VERSOES_PROMPT.items():
    template = PROMPTS[chave]

    def predict_fn(entrada, _template=template, _versao=str(versao)):
        return gerar_parecer(entrada, _template, chamar, _versao)

    with mlflow.start_run(run_name=f"prompt_{chave}_versao_{versao}{SUFIXO_RUN}") as run:
        RUNS[chave] = run.info.run_id
        mlflow.log_params({"prompt": NOME_PROMPT, "prompt_versao": versao, "prompt_rotulo": chave,
                           "llm": P["endpoint_llm"], "casos": len(registros), "dataset": NOME_DATASET,
                           "lotes_validacao": P["lotes_validacao"], **{f"versao_{k}": v for k, v in VERSOES.items()}})
        mlflow.log_text(template, f"prompt_{chave}_v{versao}.txt")  # o texto avaliado fica junto do run
        resultado = mlflow.genai.evaluate(data=dataset, predict_fn=predict_fn, scorers=SCORERS)
        t = _tabela(resultado)
        pagamentos = t[t["esperado"].str.startswith("pagar")]
        extras = {"valor_dentro_tolerancia_pagamentos": float(np.mean([
                      av.valor_dentro_tolerancia(v, d) for v, d in zip(pagamentos["valor_sugerido"], pagamentos["valor_devido"])]))
                  if len(pagamentos) else float("nan"),
                  "casos_pagamento_esperado": float(len(pagamentos))}
        mlflow.log_metrics(extras)
        por_padrao = (t.groupby("padrao").agg(casos=("correto", "size"), acuracia=("correto", "mean"))
                      .round(3).reset_index())
        erros = t[~t["correto"]].drop(columns=["correto"])
        fig, matriz = _figura_confusao(t, f"Prompt {chave} (versão {versao})")
        mlflow.log_figure(fig, "matriz_confusao_recomendacoes.png")
        mlflow.log_table(por_padrao, "acuracia_por_padrao.json")
        mlflow.log_table(erros, "erros.json")
        mlflow.log_table(t.drop(columns=["motivos"]), "resultados.json")
        plt.close("all")
    RESULTADOS[chave] = {**{k: float(v) for k, v in resultado.metrics.items()}, **extras}
    TABELAS[chave] = {"por_padrao": por_padrao, "erros": erros, "matriz": matriz, "tabela": t}
    if PUBLICAR:  # a métrica gravada no prompt é sempre a do LLM de produção
        TABELA_PROMPTS = av.gravar_metrica(TABELA_PROMPTS, versao, RESULTADOS[chave]["recomendacao_correta/mean"])

    print(f"prompt {chave} (v{versao}): " + ", ".join(f"{k}={v:.3f}" for k, v in sorted(RESULTADOS[chave].items())))

comparacao = pd.DataFrame(RESULTADOS).round(3).rename_axis("metrica").reset_index()
display(comparacao)  # noqa: F821
display(TABELAS["v1"]["por_padrao"].merge(TABELAS["v2"]["por_padrao"], on=["padrao", "casos"], suffixes=("_v1", "_v2")))  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ### Erros do prompt v2
# MAGIC
# MAGIC Os casos em que o parecer v2 diverge do gabarito, com os motivos. Apólices com menos de 30 dias vão para
# MAGIC `investigar` pela cláusula CG-2.4 (análise de contratação recente), mesmo quando o gabarito diz que o sinistro é
# MAGIC legítimo. Essa divergência é de política, não de leitura.

# COMMAND ----------

erros_v2 = TABELAS["v2"]["erros"]
display(erros_v2[["id_aviso", "padrao", "esperado", "obtido", "dias_desde_contratacao", "motivos"]])  # noqa: F821
print("Matriz de confusão v2 (linhas: esperado; colunas: obtido):")
print(TABELAS["v2"]["matriz"].to_string())
politica = erros_v2[(erros_v2["obtido"] == "investigar") & (pd.to_numeric(erros_v2["dias_desde_contratacao"]) < 30)]
print(f"{len(erros_v2)} divergências no v2; {len(politica)} delas são apólices com menos de 30 dias (CG-2.4).")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Portão de qualidade do prompt (spec 6.4)
# MAGIC
# MAGIC O candidato é a versão com a maior `recomendacao_correta`; no empate, o v2, mais explícito. O alias `producao`
# MAGIC só vai para o candidato se a métrica dele for maior ou igual à da versão de produção atual. Se a versão atual foi
# MAGIC avaliada agora, vale a métrica desta execução; senão, a que ficou gravada na tag da versão.

# COMMAND ----------

if not PUBLICAR:
    resultado = {"dataset": NOME_DATASET, "casos": len(registros), "llm": P["endpoint_llm"], "versoes_prompt": VERSOES_PROMPT,
                 "runs": RUNS, "publicar": False,
                 "metricas": {c: {k: round(v, 4) for k, v in m.items()} for c, m in RESULTADOS.items()}}
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    dbutils.notebook.exit(json.dumps(resultado, ensure_ascii=False))  # noqa: F821

metrica = {c: RESULTADOS[c]["recomendacao_correta/mean"] for c in VERSOES_PROMPT}
candidato = max(VERSOES_PROMPT, key=lambda c: (metrica[c], c == "v2"))
atual = av.versao_producao(TABELA_PROMPTS)
avaliadas = {v: c for c, v in VERSOES_PROMPT.items()}
if atual is None:
    metrica_atual = None
elif int(atual["versao"]) in avaliadas:
    metrica_atual = metrica[avaliadas[int(atual["versao"])]]
else:
    metrica_atual = float(atual["recomendacao_correta"])
PROMOVER = metrica_atual is None or not metrica_atual == metrica_atual or metrica[candidato] >= metrica_atual
if PROMOVER:
    TABELA_PROMPTS = av.definir_producao(TABELA_PROMPTS, VERSOES_PROMPT[candidato])
_gravar_prompts(TABELA_PROMPTS)
PRODUCAO = av.versao_producao(TABELA_PROMPTS)
print(f"candidato {candidato} (v{VERSOES_PROMPT[candidato]}, {metrica[candidato]:.3f}); produção anterior: "
      f"{None if atual is None else atual['versao']} ({metrica_atual}); promovido: {PROMOVER}; "
      f"produção agora: v{PRODUCAO['versao']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Registro do modelo `ml.parecer_sinistro` e publicação do endpoint
# MAGIC
# MAGIC - O modelo leva o prompt de produção **congelado**.
# MAGIC - Declara o LLM em `resources`: o endpoint chama o Foundation Model API com passthrough de credenciais.
# MAGIC - O endpoint é criado ou atualizado com scale-to-zero, AI Gateway (inference table e usage tracking) e tracing
# MAGIC   no experimento do parecer.
# MAGIC - O teste do endpoint publicado fica em `scripts/testar_endpoint_parecer.py`.

# COMMAND ----------

pasta = Path(tempfile.mkdtemp())
(pasta / "config.json").write_text(json.dumps({
    "endpoint_llm": P["endpoint_llm"], "nome_prompt": NOME_PROMPT, "versao_prompt": str(PRODUCAO['versao']),
    "template": PRODUCAO['template']}, ensure_ascii=False), encoding="utf-8")
exemplo = pd.DataFrame({"entrada_json": [amostra.iloc[0].entrada_json], "score_suspeita": [float(amostra.iloc[0].score_suspeita)],
                        "fatores_suspeita": [amostra.iloc[0].fatores_suspeita]})
with mlflow.start_run(run_name=f"registro_parecer_prompt_v{PRODUCAO['versao']}") as run:
    RUN_REGISTRO = run.info.run_id
    info = mlflow.pyfunc.log_model(
        name="parecer", python_model=str(Path(parecer.__file__).with_name("modelo_pyfunc.py")),
        artifacts={"config": str(pasta / "config.json")}, code_paths=[str(Path(parecer.__file__).parent)],
        signature=assinatura_parecer(), input_example=exemplo,
        pip_requirements=[f"mlflow=={VERSOES['mlflow']}", f"databricks-sdk=={VERSOES['databricks-sdk']}",
                          f"pandas=={VERSOES['pandas']}", f"numpy=={VERSOES['numpy']}"],
        resources=[DatabricksServingEndpoint(endpoint_name=P["endpoint_llm"])],
        registered_model_name=NOME_MODELO)
VERSAO_MODELO = str(info.registered_model_version)
cliente = MlflowClient(registry_uri="databricks-uc")
cliente.set_registered_model_alias(NOME_MODELO, "producao", VERSAO_MODELO)
for chave, valor in {"prompt": NOME_PROMPT, "versao_prompt": str(PRODUCAO['versao']), "llm": P["endpoint_llm"],
                     "recomendacao_correta": f"{metrica[avaliadas.get(int(PRODUCAO['versao']), candidato)]:.4f}",
                     "dataset": NOME_DATASET}.items():
    cliente.set_model_version_tag(NOME_MODELO, VERSAO_MODELO, chave, valor)
cliente.update_registered_model(NOME_MODELO, description=(
    "Parecer prévio de sinistros patrimoniais (Claude Sonnet via Foundation Model API). Entrada: entrada_json de "
    "silver.entrada_parecer + score e fatores do modelo de suspeita. Saída: recomendação, valor sugerido (calculado em "
    "código), motivos, cláusulas, confiança, status e trace. Alias producao = versão servida."))
saida_registrado = mlflow.pyfunc.load_model(f"models:/{NOME_MODELO}/{VERSAO_MODELO}").predict(exemplo)
print(f"registrado: {NOME_MODELO} versão {VERSAO_MODELO} com o prompt v{PRODUCAO['versao']}; teste: "
      f"{saida_registrado.iloc[0][['recomendacao', 'valor_sugerido', 'status_parecer']].to_dict()}")

w = WorkspaceClient()
ACAO_ENDPOINT = publicar_endpoint(api_do_workspace(w), P["endpoint_parecer"],
                                  config_endpoint(NOME_MODELO, VERSAO_MODELO, EXPERIMENTO_ID, P["catalogo"], P["schema_ml"]))
print(f"endpoint {P['endpoint_parecer']}: {ACAO_ENDPOINT} com {NOME_MODELO} v{VERSAO_MODELO} (a prontidão é conferida por "
      "scripts/testar_endpoint_parecer.py)")

# COMMAND ----------

resultado = {"dataset": NOME_DATASET, "casos": len(registros), "prompt": NOME_PROMPT,
             "versoes_prompt": VERSOES_PROMPT, "prompt_producao": int(PRODUCAO['versao']), "promovido": PROMOVER,
             "modelo": NOME_MODELO, "versao_modelo": VERSAO_MODELO, "endpoint": P["endpoint_parecer"],
             "acao_endpoint": ACAO_ENDPOINT, "runs": RUNS, "run_registro": RUN_REGISTRO,
             "metricas": {c: {k: round(v, 4) for k, v in m.items()} for c, m in RESULTADOS.items()}}
print(json.dumps(resultado, ensure_ascii=False, indent=2))
dbutils.notebook.exit(json.dumps(resultado, ensure_ascii=False))  # noqa: F821

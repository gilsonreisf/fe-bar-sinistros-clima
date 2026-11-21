"""Silver: clima diário por estação e evidência climática de cada aviso.

As regras são as mesmas do gerador (src/regras), executadas no pipeline com applyInPandas: nada é reimplementado.
"""
import pandas as pd
from pyspark import pipelines as dp
from pyspark.sql import functions as F

from regras.clima import JANELA_DIAS, agregar_diario
from regras.sinistro import ESQUEMA_EVIDENCIA, calcular_evidencia_grupo

CATALOGO = spark.conf.get("catalogo")  # noqa: F821 (spark é injetado pelo pipeline)
BRONZE = f"{CATALOGO}.{spark.conf.get('schema_bronze')}"  # noqa: F821
SILVER = f"{CATALOGO}.{spark.conf.get('schema_silver')}"  # noqa: F821
ESQUEMA_CLIMA_DIA = ("codigo_estacao STRING, data DATE, horas_chuva BIGINT, chuva_mm DOUBLE, chuva_max_hora_mm DOUBLE, "
                     "horas_rajada BIGINT, rajada_max_ms DOUBLE, queda_temp_max_c DOUBLE, granizo_provavel BOOLEAN")


def _agregar_estacao(horario: pd.DataFrame) -> pd.DataFrame:
    diario = agregar_diario(horario.assign(data=pd.to_datetime(horario["data"]).dt.date))
    diario["granizo_provavel"] = diario["granizo_provavel"].astype(object).where(diario["granizo_provavel"].notna(), None)
    return diario


@dp.materialized_view(name=f"{SILVER}.clima_estacao_dia",
                      comment="Clima diário por estação do INMET (dias com menos de 12 h válidas ficam ausentes).")
def clima_estacao_dia():
    horario = spark.read.table(f"{BRONZE}.clima_inmet").select(  # noqa: F821
        "codigo_estacao", F.to_date("data").alias("data"), F.col("hora_utc").cast("int").alias("hora_utc"),
        *[F.col(c).cast("double").alias(c) for c in ("chuva_mm", "rajada_ms", "temp_c")])
    return horario.groupBy("codigo_estacao").applyInPandas(_agregar_estacao, ESQUEMA_CLIMA_DIA)


@dp.materialized_view(name=f"{SILVER}.evidencia_climatica",
                      comment="Evidência climática de cada aviso: INMET a até 30 km ou Defesa Civil no município (D-015).")
def evidencia_climatica():
    avisos = spark.read.table(f"{SILVER}.avisos").select(  # noqa: F821
        "id_aviso", "codigo_ibge", "lat", "lon", "data_ocorrencia", "causa_declarada")
    estacoes = spark.read.table(f"{BRONZE}.estacoes_inmet").select(  # noqa: F821
        F.col("codigo_estacao").cast("string").alias("codigo_estacao"),
        F.col("lat").cast("double").alias("lat_estacao"), F.col("lon").cast("double").alias("lon_estacao"))
    clima = spark.read.table(f"{SILVER}.clima_estacao_dia").join(estacoes, "codigo_estacao")  # noqa: F821
    janela = avisos.join(
        clima,
        (clima["data"] >= F.date_sub(avisos["data_ocorrencia"], JANELA_DIAS))
        & (clima["data"] <= F.date_add(avisos["data_ocorrencia"], JANELA_DIAS)),
        "left")
    ocorrencias = spark.read.table(f"{SILVER}.ocorrencias_defesa_civil").alias("d")  # noqa: F821
    registro = (avisos.alias("a")
                .join(ocorrencias,
                      (F.col("a.codigo_ibge") == F.col("d.codigo_ibge"))
                      & (F.col("a.data_ocorrencia") >= F.date_sub(F.col("d.data_inicio"), JANELA_DIAS))
                      & (F.col("a.data_ocorrencia") <= F.date_add(F.col("d.data_fim"), JANELA_DIAS)),
                      "left")
                .groupBy(F.col("a.id_aviso").alias("id_aviso"))
                .agg(F.max(F.col("d.codigo_ibge").isNotNull()).alias("registro_defesa_civil")))
    return (janela.join(registro, "id_aviso", "left")
            .groupBy("id_aviso").applyInPandas(calcular_evidencia_grupo, ESQUEMA_EVIDENCIA))

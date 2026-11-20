"""Bronze: um Auto Loader por pasta do Volume (uma entidade por pasta; D-018), com metadados de ingestão.

Os dados entram como chegaram. Tipagem, cruzamentos e regras ficam na silver.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

from ambiente import ESQUEMA_AVISOS, PASTAS_LANDING

CATALOGO = spark.conf.get("catalogo")  # noqa: F821 (spark é injetado pelo pipeline)
SCHEMA = spark.conf.get("schema_bronze")  # noqa: F821
VOLUME = spark.conf.get("volume_arquivos")  # noqa: F821


def _registrar(pasta: str, tabela: str, formato: str) -> None:
    @dp.table(name=f"{CATALOGO}.{SCHEMA}.{tabela}", comment=f"Bronze: arquivos de {pasta}/ no Volume, como chegaram (Auto Loader).")
    def _ingestao():
        leitor = spark.readStream.format("cloudFiles").option("cloudFiles.format", formato)  # noqa: F821
        if formato == "csv":
            leitor = leitor.option("header", "true").option("cloudFiles.inferColumnTypes", "true")
        elif formato == "json":
            leitor = leitor.schema(ESQUEMA_AVISOS)
        else:  # binaryFile: os PDFs dos avisos
            leitor = leitor.option("pathGlobFilter", "*.pdf")
        return (leitor.load(f"{VOLUME}/{pasta}/")
                .withColumn("_arquivo", F.col("_metadata.file_path"))
                .withColumn("_ingerido_em", F.current_timestamp()))


for _pasta, (_tabela, _formato) in PASTAS_LANDING.items():
    _registrar(_pasta, _tabela, _formato)

"""Lakebase (Postgres): o schema `operacao` da regulação e as consultas que o app usa (spec 7.1).

- `atribuicoes`: quem está com cada sinistro. "Assumir próximo" é atômico: a PK de `id_aviso` impede dois reguladores
  com o mesmo caso, e `pg_try_advisory_xact_lock` pula o que outro regulador está pegando no mesmo instante (efeito do
  SKIP LOCKED sem precisar travar a synced table, que é somente leitura).
- `decisoes_regulador`: só inserção; `id_decisao` vem do cliente (UUID), então o clique duplo não duplica (spec 10.3).
- `reanalises`: cada "Reanalisar com IA", com o trace.
REPLICA IDENTITY FULL em todas: requisito do Lakehouse Sync, que leva o schema de volta ao UC (histórico SCD2).
"""
from __future__ import annotations

from parecer.esquema import RECOMENDACOES

SCHEMA = "operacao"
_DECISOES = ", ".join(f"'{r}'" for r in RECOMENDACOES)

DDL = [
    f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}",
    f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.atribuicoes (
  id_aviso TEXT PRIMARY KEY,
  regulador TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'em_analise' CHECK (status IN ('em_analise', 'decidido')),
  atribuido_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
)""",
    f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.decisoes_regulador (
  id_decisao UUID PRIMARY KEY,
  id_aviso TEXT NOT NULL,
  regulador TEXT NOT NULL,
  decisao TEXT NOT NULL CHECK (decisao IN ({_DECISOES})),
  valor_aprovado NUMERIC(14, 2) NOT NULL CHECK (valor_aprovado >= 0),
  motivo TEXT,
  recomendacao_ia TEXT,
  valor_sugerido_ia NUMERIC(14, 2),
  concordou_com_ia BOOLEAN NOT NULL,
  versao_modelo TEXT,
  versao_prompt TEXT,
  trace_id TEXT,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
)""",
    f"""CREATE TABLE IF NOT EXISTS {SCHEMA}.reanalises (
  id_reanalise UUID PRIMARY KEY,
  id_aviso TEXT NOT NULL,
  solicitado_por TEXT NOT NULL,
  recomendacao TEXT,
  valor_sugerido NUMERIC(14, 2),
  motivos JSONB,
  status_parecer TEXT,
  versao_prompt TEXT,
  trace_id TEXT,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
)""",
    f"CREATE INDEX IF NOT EXISTS decisoes_por_aviso ON {SCHEMA}.decisoes_regulador (id_aviso)",
    f"ALTER TABLE {SCHEMA}.atribuicoes REPLICA IDENTITY FULL",
    f"ALTER TABLE {SCHEMA}.decisoes_regulador REPLICA IDENTITY FULL",
    f"ALTER TABLE {SCHEMA}.reanalises REPLICA IDENTITY FULL",
]


def consultas(fila: str) -> dict[str, str]:
    """Consultas parametrizadas (psycopg, %(nome)s). `fila` = tabela sincronizada do gold no Postgres."""
    return {
        "assumir_proximo": f"""INSERT INTO {SCHEMA}.atribuicoes (id_aviso, regulador)
SELECT f.id_aviso, %(regulador)s FROM {fila} f
WHERE NOT f.fast_track
  AND NOT EXISTS (SELECT 1 FROM {SCHEMA}.atribuicoes a WHERE a.id_aviso = f.id_aviso)
  AND pg_try_advisory_xact_lock(hashtext(f.id_aviso))
ORDER BY f.prioridade DESC, f.id_aviso
LIMIT 1
ON CONFLICT (id_aviso) DO NOTHING
RETURNING id_aviso""",
        "registrar_decisao": f"""INSERT INTO {SCHEMA}.decisoes_regulador (id_decisao, id_aviso, regulador, decisao, valor_aprovado,
  motivo, recomendacao_ia, valor_sugerido_ia, concordou_com_ia, versao_modelo, versao_prompt, trace_id)
SELECT %(id_decisao)s, f.id_aviso, %(regulador)s, %(decisao)s, %(valor_aprovado)s, %(motivo)s, f.recomendacao_ia,
  f.valor_sugerido, %(decisao)s = f.recomendacao_ia, f.versao_modelo, f.versao_prompt, f.trace_id
FROM {fila} f WHERE f.id_aviso = %(id_aviso)s
ON CONFLICT (id_decisao) DO NOTHING
RETURNING id_decisao""",
        "concluir_atribuicao": f"""UPDATE {SCHEMA}.atribuicoes SET status = 'decidido', atualizado_em = now()
WHERE id_aviso = %(id_aviso)s AND regulador = %(regulador)s""",
        "fila": f"""SELECT f.id_aviso, f.municipio, f.causa_declarada, f.valor_reclamado, f.score_suspeita, f.recomendacao_ia,
  f.valor_sugerido, f.prioridade, a.regulador, a.status
FROM {fila} f LEFT JOIN {SCHEMA}.atribuicoes a ON a.id_aviso = f.id_aviso
WHERE NOT f.fast_track AND (a.status IS NULL OR a.status = 'em_analise')
ORDER BY f.prioridade DESC, f.id_aviso LIMIT %(limite)s""",
    }


def conectar(w, projeto: str, branch: str = "production", endpoint: str = "primary",
             banco: str = "databricks_postgres", usuario: str | None = None, tentativas: int = 5):
    """Conexão com token OAuth (validade de 1 h) e nova tentativa com espera crescente: o compute pode estar acordando
    do scale-to-zero (spec 10.3)."""
    import time

    import psycopg

    caminho = f"projects/{projeto}/branches/{branch}/endpoints/{endpoint}"
    ep = w.postgres.get_endpoint(name=caminho)
    usuario = usuario or w.current_user.me().user_name
    for tentativa in range(1, tentativas + 1):
        token = w.postgres.generate_database_credential(endpoint=caminho).token
        try:
            return psycopg.connect(host=ep.status.hosts.host, dbname=banco, user=usuario, password=token,
                                   sslmode="require", connect_timeout=15)
        except psycopg.OperationalError:
            if tentativa == tentativas:
                raise
            time.sleep(2 ** tentativa)

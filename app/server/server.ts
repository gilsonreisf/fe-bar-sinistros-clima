// Servidor do app de regulação (spec 9): painel e supervisão leem o SQL Warehouse (config/queries, metric views do UC);
// a fila, as decisões e as reanálises são operação transacional no Lakebase (schema `operacao`, D-024); "Reanalisar com
// IA" chama o endpoint do parecer (AI Gateway + tracing, D-022).
import { analytics, createApp, createWorkspaceClient, getWarehouseId, lakebase, server, serving } from '@databricks/appkit';
import type { Application, Request } from 'express';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';

const IDENT = /^[a-z_][a-z0-9_]*$/;
const catalogo = process.env.FE_BAR_CATALOGO ?? '';
const prefixo = process.env.FE_BAR_PREFIXO_SCHEMA ?? '';
if (!IDENT.test(catalogo) || !/^[a-z0-9_]*$/.test(prefixo)) {
  throw new Error('FE_BAR_CATALOGO ou FE_BAR_PREFIXO_SCHEMA inválido (veja app.yaml / .env)');
}
const SCHEMA_GOLD = `${prefixo}gold`;
const SCHEMA_SILVER = `${prefixo}silver`;
const FILA_PG = `${SCHEMA_GOLD}.sinistros_analisados_lb`; // synced table do gold no Postgres (D-024)
const RECOMENDACOES = ['pagar_integral', 'pagar_parcial', 'recusar', 'investigar'] as const;
const ID_AVISO = /^AV-\d{4}-\d{6}$/;

interface AppKitComLakebase {
  lakebase: { query(text: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }> };
  server: { extend(fn: (app: Application) => void): void };
}

/** Quem está usando o app: o Databricks Apps repassa o e-mail do usuário autenticado; localmente, um nome de teste. */
function regulador(req: Request): string {
  const email = req.header('x-forwarded-email') ?? req.header('x-forwarded-preferred-username');
  return email?.trim() || process.env.FE_BAR_REGULADOR_LOCAL || 'regulador_local';
}

// "Assumir próximo" atômico: a PK de id_aviso impede dois reguladores no mesmo caso e o advisory lock pula o caso que
// outro regulador está pegando no mesmo instante (mesma consulta de src/lakebase/operacao.py, testada em 03-lakebase.md).
const SQL_ASSUMIR = `INSERT INTO operacao.atribuicoes (id_aviso, regulador)
SELECT f.id_aviso, $1 FROM ${FILA_PG} f
WHERE NOT f.fast_track
  AND NOT EXISTS (SELECT 1 FROM operacao.atribuicoes a WHERE a.id_aviso = f.id_aviso)
  AND pg_try_advisory_xact_lock(hashtext(f.id_aviso))
ORDER BY f.prioridade DESC, f.id_aviso
LIMIT 1
ON CONFLICT (id_aviso) DO NOTHING
RETURNING id_aviso`;

const SQL_FILA = `SELECT f.id_aviso, f.data_aviso, f.municipio, f.causa_declarada, f.valor_reclamado, f.score_suspeita,
  f.recomendacao_ia, f.valor_sugerido, f.prioridade, f.bloqueios_fast_track, a.regulador, a.status
FROM ${FILA_PG} f LEFT JOIN operacao.atribuicoes a ON a.id_aviso = f.id_aviso
WHERE NOT f.fast_track AND (a.status IS NULL OR a.status = 'em_analise')
ORDER BY f.prioridade DESC, f.id_aviso LIMIT $1`;

// Só inserção, com id_decisao (UUID) vindo do cliente: o clique duplo não duplica a decisão (spec 10.3).
const SQL_DECIDIR = `INSERT INTO operacao.decisoes_regulador (id_decisao, id_aviso, regulador, decisao, valor_aprovado,
  motivo, recomendacao_ia, valor_sugerido_ia, concordou_com_ia, versao_modelo, versao_prompt, trace_id)
SELECT $1, f.id_aviso, $2, $3, $4, $5, f.recomendacao_ia, f.valor_sugerido, $3 = f.recomendacao_ia, f.versao_modelo,
  f.versao_prompt, f.trace_id
FROM ${FILA_PG} f WHERE f.id_aviso = $6
ON CONFLICT (id_decisao) DO NOTHING
RETURNING id_decisao`;

const Decisao = z.object({
  id_decisao: z.string().uuid(),
  decisao: z.enum(RECOMENDACOES),
  valor_aprovado: z.coerce.number().min(0).max(10_000_000),
  motivo: z.string().trim().min(3).max(2000),
});

const Predicao = z.object({
  recomendacao: z.string(),
  valor_sugerido: z.coerce.number(),
  motivos: z.string(),
  status_parecer: z.string(),
  versao_prompt: z.string(),
  trace_id: z.string().optional().default(''),
});

async function entradaDoParecer(idAviso: string) {
  // Mesma entrada do lote (silver.entrada_parecer) com o score do modelo de suspeita; parâmetro ligado, sem concatenar.
  const ws = createWorkspaceClient();
  const r = await ws.statementExecution.executeStatement({
    warehouse_id: await getWarehouseId(),
    statement: `SELECT e.entrada_json, a.score_suspeita, a.fatores_suspeita
      FROM ${catalogo}.${SCHEMA_SILVER}.entrada_parecer e
      JOIN ${catalogo}.${SCHEMA_GOLD}.sinistros_analisados a ON a.id_aviso = e.id_aviso
      WHERE e.id_aviso = :id_aviso`,
    parameters: [{ name: 'id_aviso', value: idAviso, type: 'STRING' }],
    wait_timeout: '30s',
  });
  const linha = r.result?.data_array?.[0];
  if (!linha) return null;
  return { entrada_json: linha[0], score_suspeita: linha[1] === null ? null : Number(linha[1]), fatores_suspeita: linha[2] };
}

function rotas(appkit: AppKitComLakebase) {
  appkit.server.extend((app) => {
    app.get('/api/config', (req, res) => {
      const host = (process.env.DATABRICKS_HOST ?? '').replace(/\/$/, '');
      const genie = process.env.FE_BAR_GENIE_SPACE_ID;
      res.json({
        regulador: regulador(req),
        genieUrl: genie && host ? `${host.startsWith('http') ? host : `https://${host}`}/genie/rooms/${genie}` : null,
      });
    });

    app.get('/api/fila', async (req, res) => {
      const limite = Math.min(Math.max(Number(req.query.limite) || 50, 1), 200);
      try {
        res.json((await appkit.lakebase.query(SQL_FILA, [limite])).rows);
      } catch (err) {
        console.error('[fila] falha ao listar:', err);
        res.status(503).json({ error: 'Fila indisponível no momento (Lakebase). Tente de novo em instantes.' });
      }
    });

    app.post('/api/fila/assumir', async (req, res) => {
      try {
        const { rows } = await appkit.lakebase.query(SQL_ASSUMIR, [regulador(req)]);
        res.json({ id_aviso: rows[0]?.id_aviso ?? null });
      } catch (err) {
        console.error('[fila] falha ao assumir:', err);
        res.status(503).json({ error: 'Não foi possível assumir um sinistro agora.' });
      }
    });

    app.get('/api/sinistros/:id/operacao', async (req, res) => {
      const id = req.params.id;
      if (!ID_AVISO.test(id)) return void res.status(400).json({ error: 'id_aviso inválido' });
      try {
        const [atrib, decisoes, reanalises] = await Promise.all([
          appkit.lakebase.query('SELECT regulador, status, atribuido_em FROM operacao.atribuicoes WHERE id_aviso = $1', [id]),
          appkit.lakebase.query(
            `SELECT id_decisao, regulador, decisao, valor_aprovado, motivo, concordou_com_ia, criado_em
             FROM operacao.decisoes_regulador WHERE id_aviso = $1 ORDER BY criado_em DESC`, [id]),
          appkit.lakebase.query(
            `SELECT id_reanalise, solicitado_por, recomendacao, valor_sugerido, motivos, status_parecer, versao_prompt,
               trace_id, criado_em FROM operacao.reanalises WHERE id_aviso = $1 ORDER BY criado_em DESC LIMIT 5`, [id]),
        ]);
        res.json({ atribuicao: atrib.rows[0] ?? null, decisoes: decisoes.rows, reanalises: reanalises.rows });
      } catch (err) {
        console.error('[operacao] falha ao ler:', err);
        res.status(503).json({ error: 'Operação indisponível no momento (Lakebase).' });
      }
    });

    app.post('/api/sinistros/:id/decisao', async (req, res) => {
      const id = req.params.id;
      const corpo = Decisao.safeParse(req.body);
      if (!ID_AVISO.test(id) || !corpo.success) {
        return void res.status(400).json({ error: 'Decisão inválida: confira a decisão, o valor e o motivo.' });
      }
      const d = corpo.data;
      const quem = regulador(req);
      try {
        const { rows } = await appkit.lakebase.query(SQL_DECIDIR, [d.id_decisao, quem, d.decisao, d.valor_aprovado, d.motivo, id]);
        await appkit.lakebase.query(
          `UPDATE operacao.atribuicoes SET status = 'decidido', atualizado_em = now() WHERE id_aviso = $1 AND regulador = $2`,
          [id, quem]);
        // rows vazio = a mesma decisão já tinha sido gravada (clique duplo) ou o sinistro não está na fila
        res.json({ gravada: rows.length > 0, id_decisao: d.id_decisao });
      } catch (err) {
        console.error('[decisao] falha ao gravar:', err);
        res.status(503).json({ error: 'Não foi possível gravar a decisão. Nada foi registrado; tente de novo.' });
      }
    });

    app.post('/api/sinistros/:id/reanalisar', async (req, res) => {
      const id = req.params.id;
      if (!ID_AVISO.test(id)) return void res.status(400).json({ error: 'id_aviso inválido' });
      try {
        const entrada = await entradaDoParecer(id);
        if (!entrada) return void res.status(404).json({ error: 'Sinistro sem entrada de parecer.' });
        const ws = createWorkspaceClient();
        const r = await ws.servingEndpoints.query({
          name: process.env.DATABRICKS_SERVING_ENDPOINT_NAME ?? '',
          dataframe_records: [entrada],
        });
        const bruto: unknown = Array.isArray(r.predictions) ? r.predictions[0] : r.predictions;
        const p = Predicao.parse(bruto);
        const idReanalise = randomUUID();
        await appkit.lakebase.query(
          `INSERT INTO operacao.reanalises (id_reanalise, id_aviso, solicitado_por, recomendacao, valor_sugerido, motivos,
             status_parecer, versao_prompt, trace_id) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)`,
          [idReanalise, id, regulador(req), p.recomendacao, p.valor_sugerido, p.motivos, p.status_parecer, p.versao_prompt,
            p.trace_id]);
        res.json({ id_reanalise: idReanalise, ...p, motivos: JSON.parse(p.motivos) as unknown });
      } catch (err) {
        console.error('[reanalise] falha:', err);
        res.status(502).json({ error: 'A IA não respondeu agora (o endpoint pode estar acordando). Tente de novo em 1 minuto.' });
      }
    });
  });
}

createApp({
  plugins: [analytics(), lakebase(), server(), serving()],
  onPluginsReady(appkit) {
    rotas(appkit);
    return Promise.resolve();
  },
}).catch(console.error);

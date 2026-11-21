// Servidor do app de regulação (spec 9): painel e supervisão leem o SQL Warehouse (config/queries, metric views do UC);
// a fila, as decisões e as reanálises são operação transacional no Lakebase (schema `operacao`, D-024); "Reanalisar com
// IA" chama o endpoint do parecer (AI Gateway + tracing, D-022).
import { analytics, createApp, createWorkspaceClient, getWarehouseId, lakebase, server, serving } from '@databricks/appkit';
import type { Application, Request } from 'express';
import { randomUUID } from 'node:crypto';
import { Decisao, ID_AVISO, Predicao, consultasLakebase } from './contrato';

const IDENT = /^[a-z_][a-z0-9_]*$/;
const catalogo = process.env.FE_BAR_CATALOGO ?? '';
const prefixo = process.env.FE_BAR_PREFIXO_SCHEMA ?? '';
if (!IDENT.test(catalogo) || !/^[a-z0-9_]*$/.test(prefixo)) {
  throw new Error('FE_BAR_CATALOGO ou FE_BAR_PREFIXO_SCHEMA inválido (veja app.yaml / .env)');
}
const SCHEMA_GOLD = `${prefixo}gold`;
const SCHEMA_SILVER = `${prefixo}silver`;
const FILA_PG = `${SCHEMA_GOLD}.sinistros_analisados_lb`; // synced table do gold no Postgres (D-024)
const SQL = consultasLakebase(FILA_PG);

interface AppKitComLakebase {
  lakebase: { query(text: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }> };
  server: { extend(fn: (app: Application) => void): void };
}

/** Quem está usando o app: o Databricks Apps repassa o e-mail do usuário autenticado; localmente, um nome de teste. */
function regulador(req: Request): string {
  const email = req.header('x-forwarded-email') ?? req.header('x-forwarded-preferred-username');
  return email?.trim() || process.env.FE_BAR_REGULADOR_LOCAL || 'regulador_local';
}

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

/** Na partida, registra no log se a identidade do app lê a fila e o schema operacao (confere as permissões do deploy). */
async function verificarAcesso(appkit: AppKitComLakebase) {
  try {
    const { rows } = await appkit.lakebase.query(
      `SELECT (SELECT count(*) FROM ${FILA_PG}) AS fila, (SELECT count(*) FROM operacao.decisoes_regulador) AS decisoes`);
    console.log(`[verificacao] Lakebase ok: ${JSON.stringify(rows[0])}`);
  } catch (err) {
    console.error('[verificacao] Lakebase sem acesso (rode scripts/permissoes_app.py):', (err as Error).message);
  }
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
        res.json((await appkit.lakebase.query(SQL.fila, [limite])).rows);
      } catch (err) {
        console.error('[fila] falha ao listar:', err);
        res.status(503).json({ error: 'Fila indisponível no momento (Lakebase). Tente de novo em instantes.' });
      }
    });

    app.post('/api/fila/assumir', async (req, res) => {
      try {
        // Na corrida com outro regulador pelo mesmo caso, a PK barra o segundo e ele volta vazio: tenta o próximo
        // (até 3 vezes) em vez de devolver "fila vazia" (medido em evidencias/03-lakebase.md).
        let id: unknown = null;
        for (let tentativa = 0; tentativa < 3 && !id; tentativa++) {
          const { rows } = await appkit.lakebase.query(SQL.assumir, [regulador(req)]);
          id = rows[0]?.id_aviso ?? null;
        }
        res.json({ id_aviso: id });
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
        const { rows } = await appkit.lakebase.query(SQL.decidir, [d.id_decisao, quem, d.decisao, d.valor_aprovado, d.motivo, id]);
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
    void verificarAcesso(appkit);
    return Promise.resolve();
  },
}).catch(console.error);

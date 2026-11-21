// Contrato das rotas do app: validação de entrada e SQL do Lakebase (sem efeitos colaterais, testável).
import { z } from 'zod';

export const RECOMENDACOES = ['pagar_integral', 'pagar_parcial', 'recusar', 'investigar'] as const;
export const ID_AVISO = /^AV-\d{4}-\d{6}$/;

export const Decisao = z.object({
  id_decisao: z.string().uuid(),
  decisao: z.enum(RECOMENDACOES),
  valor_aprovado: z.coerce.number().min(0).max(10_000_000),
  motivo: z.string().trim().min(3).max(2000),
});

export const Predicao = z.object({
  recomendacao: z.string(),
  valor_sugerido: z.coerce.number(),
  motivos: z.string(),
  status_parecer: z.string(),
  versao_prompt: z.string(),
  trace_id: z.string().optional().default(''),
});

/** `fila` = synced table do gold no Postgres (`<prefixo>gold.sinistros_analisados_lb`, D-024). As mesmas consultas de
 * `src/lakebase/operacao.py` (testadas contra o Postgres em evidencias/03-lakebase.md), com parâmetros posicionais. */
export function consultasLakebase(fila: string) {
  return {
    // Candidatos ordenados e materializados; o lock é tentado um a um, na ordem, e para no primeiro livre (revisão #3).
    assumir: `WITH candidatos AS MATERIALIZED (
  SELECT f.id_aviso FROM ${fila} f
  WHERE NOT f.fast_track AND NOT EXISTS (SELECT 1 FROM operacao.atribuicoes a WHERE a.id_aviso = f.id_aviso)
  ORDER BY f.prioridade DESC, f.id_aviso LIMIT 50
), escolhido AS (
  SELECT c.id_aviso FROM candidatos c WHERE pg_try_advisory_xact_lock(hashtext(c.id_aviso)) LIMIT 1
)
INSERT INTO operacao.atribuicoes (id_aviso, regulador)
SELECT id_aviso, $1 FROM escolhido
ON CONFLICT (id_aviso) DO NOTHING
RETURNING id_aviso`,
    assumirEste: `INSERT INTO operacao.atribuicoes (id_aviso, regulador)
SELECT f.id_aviso, $1 FROM ${fila} f WHERE f.id_aviso = $2 AND NOT f.fast_track
ON CONFLICT (id_aviso) DO NOTHING
RETURNING id_aviso`,
    fila: `SELECT f.id_aviso, f.data_aviso, f.municipio, f.causa_declarada, f.valor_reclamado, f.score_suspeita,
  f.recomendacao_ia, f.valor_sugerido, f.prioridade, f.bloqueios_fast_track, a.regulador, a.status
FROM ${fila} f LEFT JOIN operacao.atribuicoes a ON a.id_aviso = f.id_aviso
WHERE NOT f.fast_track AND (a.status IS NULL OR a.status = 'em_analise')
ORDER BY f.prioridade DESC, f.id_aviso LIMIT $1`,
    // Uma instrução (atômica): só quem está com o caso em análise decide; grava a decisão e conclui a atribuição.
    // id_decisao do cliente = clique duplo inofensivo; índice único por id_aviso = uma decisão por sinistro (revisão #2).
    decidir: `WITH atribuido AS (
  SELECT a.id_aviso FROM operacao.atribuicoes a
  WHERE a.id_aviso = $6 AND a.regulador = $2 AND a.status = 'em_analise'
), nova AS (
  INSERT INTO operacao.decisoes_regulador (id_decisao, id_aviso, regulador, decisao, valor_aprovado, motivo,
    recomendacao_ia, valor_sugerido_ia, concordou_com_ia, versao_modelo, versao_prompt, trace_id)
  SELECT $1::uuid, f.id_aviso, $2, $3::text, $4::numeric, $5, f.recomendacao_ia, f.valor_sugerido,
    $3::text = f.recomendacao_ia, f.versao_modelo, f.versao_prompt, f.trace_id
  FROM ${fila} f JOIN atribuido t ON t.id_aviso = f.id_aviso
  WHERE NOT f.fast_track AND $4::numeric <= f.valor_reclamado AND ($3::text <> 'recusar' OR $4::numeric = 0)
  ON CONFLICT DO NOTHING
  RETURNING id_decisao, id_aviso
), concluida AS (
  UPDATE operacao.atribuicoes a SET status = 'decidido', atualizado_em = now()
  FROM nova n WHERE a.id_aviso = n.id_aviso
  RETURNING a.id_aviso
)
SELECT n.id_decisao FROM nova n`,
    // Por que a decisão não foi gravada (mensagem útil ao regulador)
    situacao: `SELECT f.valor_reclamado, a.regulador, a.status,
  (SELECT d.id_decisao FROM operacao.decisoes_regulador d WHERE d.id_aviso = f.id_aviso) AS id_decisao
FROM ${fila} f LEFT JOIN operacao.atribuicoes a ON a.id_aviso = f.id_aviso WHERE f.id_aviso = $1`,
  };
}

/** Motivo de uma decisão não gravada, a partir da situação do caso (função pura, testada). */
export function motivoRecusa(
  s: { valor_reclamado: unknown; regulador: unknown; status: unknown; id_decisao: unknown } | undefined,
  pedido: { id_decisao: string; regulador: string; decisao: string; valor_aprovado: number },
): { motivo: string; mensagem: string } {
  if (!s) return { motivo: 'fora_da_fila', mensagem: 'Este sinistro não está na fila do regulador.' };
  if (s.id_decisao === pedido.id_decisao) return { motivo: 'ja_gravada', mensagem: 'Decisão já registrada.' };
  if (s.id_decisao) return { motivo: 'ja_decidido', mensagem: 'Este sinistro já foi decidido.' };
  if (s.regulador !== pedido.regulador || s.status !== 'em_analise') {
    return { motivo: 'sem_atribuicao', mensagem: 'Assuma o caso antes de decidir.' };
  }
  if (pedido.decisao === 'recusar' && pedido.valor_aprovado !== 0) {
    return { motivo: 'valor_invalido', mensagem: 'Uma recusa não tem valor aprovado.' };
  }
  return { motivo: 'valor_invalido', mensagem: 'O valor aprovado não pode passar do valor reclamado.' };
}

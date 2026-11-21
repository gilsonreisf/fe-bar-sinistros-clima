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

/** `fila` = synced table do gold no Postgres (`<prefixo>gold.sinistros_analisados_lb`, D-024). */
export function consultasLakebase(fila: string) {
  return {
    // "Assumir próximo" atômico: a PK de id_aviso impede dois reguladores no mesmo caso e o advisory lock pula o caso que
    // outro regulador está pegando no mesmo instante (mesma consulta de src/lakebase/operacao.py, testada em 03-lakebase.md).
    assumir: `INSERT INTO operacao.atribuicoes (id_aviso, regulador)
SELECT f.id_aviso, $1 FROM ${fila} f
WHERE NOT f.fast_track
  AND NOT EXISTS (SELECT 1 FROM operacao.atribuicoes a WHERE a.id_aviso = f.id_aviso)
  AND pg_try_advisory_xact_lock(hashtext(f.id_aviso))
ORDER BY f.prioridade DESC, f.id_aviso
LIMIT 1
ON CONFLICT (id_aviso) DO NOTHING
RETURNING id_aviso`,
    fila: `SELECT f.id_aviso, f.data_aviso, f.municipio, f.causa_declarada, f.valor_reclamado, f.score_suspeita,
  f.recomendacao_ia, f.valor_sugerido, f.prioridade, f.bloqueios_fast_track, a.regulador, a.status
FROM ${fila} f LEFT JOIN operacao.atribuicoes a ON a.id_aviso = f.id_aviso
WHERE NOT f.fast_track AND (a.status IS NULL OR a.status = 'em_analise')
ORDER BY f.prioridade DESC, f.id_aviso LIMIT $1`,
    // Só inserção, com id_decisao (UUID) vindo do cliente: o clique duplo não duplica a decisão (spec 10.3).
    decidir: `INSERT INTO operacao.decisoes_regulador (id_decisao, id_aviso, regulador, decisao, valor_aprovado,
  motivo, recomendacao_ia, valor_sugerido_ia, concordou_com_ia, versao_modelo, versao_prompt, trace_id)
SELECT $1, f.id_aviso, $2, $3, $4, $5, f.recomendacao_ia, f.valor_sugerido, $3 = f.recomendacao_ia, f.versao_modelo,
  f.versao_prompt, f.trace_id
FROM ${fila} f WHERE f.id_aviso = $6
ON CONFLICT (id_decisao) DO NOTHING
RETURNING id_decisao`,
  };
}

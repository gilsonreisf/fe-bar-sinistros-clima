import { describe, expect, it } from 'vitest';
import { Decisao, ID_AVISO, Predicao, consultasLakebase, motivoRecusa } from './contrato';

const valida = { id_decisao: '6f1c2b8e-3d4a-4b5c-9d6e-7f8091a2b3c4', decisao: 'recusar', valor_aprovado: '0', motivo: 'Sem cobertura.' };

describe('decisão do regulador', () => {
  it('aceita uma decisão completa e converte o valor', () => {
    const r = Decisao.safeParse(valida);
    expect(r.success && r.data.valor_aprovado).toBe(0);
  });
  it('recusa decisão fora da lista, valor negativo, motivo vazio e id que não é UUID', () => {
    expect(Decisao.safeParse({ ...valida, decisao: 'aprovar' }).success).toBe(false);
    expect(Decisao.safeParse({ ...valida, valor_aprovado: -1 }).success).toBe(false);
    expect(Decisao.safeParse({ ...valida, motivo: '  ' }).success).toBe(false);
    expect(Decisao.safeParse({ ...valida, id_decisao: '1' }).success).toBe(false);
  });
});

describe('rotas', () => {
  it('só aceita id de aviso no formato do projeto (nada de SQL na URL)', () => {
    expect(ID_AVISO.test('AV-2026-000047')).toBe(true);
    expect(ID_AVISO.test("AV-2026-000047' OR 1=1")).toBe(false);
  });
  it('a resposta do endpoint precisa trazer recomendação, valor e status', () => {
    expect(Predicao.safeParse({ recomendacao: 'recusar', valor_sugerido: '0', motivos: '[]', status_parecer: 'ok', versao_prompt: '2' }).success).toBe(true);
    expect(Predicao.safeParse({ recomendacao: 'recusar' }).success).toBe(false);
  });
});

describe('SQL do Lakebase', () => {
  const q = consultasLakebase('p_gold.sinistros_analisados_lb');
  it('usa a fila parametrizada e nunca concatena entrada do usuário', () => {
    for (const sql of Object.values(q)) {
      expect(sql).not.toContain('sinistros_clima');
      expect(sql).toMatch(/\$1/);
    }
    expect(q.assumir).toContain('FROM p_gold.sinistros_analisados_lb f');
  });
  it('assumir trava só o candidato tentado, na ordem de prioridade', () => {
    const [ordenado, depois] = q.assumir.split('), escolhido AS (');
    expect(ordenado).toContain('ORDER BY f.prioridade DESC');
    expect(ordenado).not.toContain('pg_try_advisory_xact_lock');
    expect(depois).toContain('pg_try_advisory_xact_lock');
    expect(q.assumir).toContain('ON CONFLICT (id_aviso) DO NOTHING');
  });
  it('só quem está com o caso decide, numa instrução só, e uma decisão por sinistro', () => {
    expect(q.decidir).toContain("a.regulador = $2 AND a.status = 'em_analise'");
    expect(q.decidir).toContain('UPDATE operacao.atribuicoes');
    expect(q.decidir).toContain('ON CONFLICT DO NOTHING');
    expect(q.decidir).toContain("($3::text <> 'recusar' OR $4::numeric = 0)");
    expect(q.fila).toContain('NOT f.fast_track');
  });
});

describe('decisão não gravada', () => {
  const pedido = { id_decisao: 'x', regulador: 'r1', decisao: 'investigar', valor_aprovado: 10 };
  const sit = { valor_reclamado: 100, regulador: 'r1', status: 'em_analise', id_decisao: null };
  it('explica o motivo ao regulador', () => {
    expect(motivoRecusa(undefined, pedido).motivo).toBe('fora_da_fila');
    expect(motivoRecusa({ ...sit, id_decisao: 'x' }, pedido).motivo).toBe('ja_gravada');
    expect(motivoRecusa({ ...sit, id_decisao: 'y' }, pedido).motivo).toBe('ja_decidido');
    expect(motivoRecusa({ ...sit, regulador: 'r2' }, pedido).motivo).toBe('sem_atribuicao');
    expect(motivoRecusa(sit, { ...pedido, decisao: 'recusar' }).mensagem).toContain('recusa');
  });
});

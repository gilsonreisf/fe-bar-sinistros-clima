// IA sob supervisão: a decisão do regulador ao lado da recomendação da IA. As decisões nascem no Lakebase e voltam ao
// Unity Catalog pelo Lakehouse Sync (gold.regulacao_metrics); as divergências são o insumo do retreino (próximo passo).
import { Card, CardContent, CardHeader, CardTitle, DataTable, useAnalyticsQuery } from '@databricks/appkit-ui/react';
import { Erro, Fonte, Kpi, KpiCarregando, Titulo } from '../components/Comum';
import { fmtBRL, fmtDec, fmtInt, fmtPct, rotuloRecomendacao, texto } from '../lib/formato';

export function SupervisaoPage() {
  const { data, loading, error } = useAnalyticsQuery('supervisao_kpis', {});
  const k = data?.[0];

  return (
    <div className="space-y-6">
      <Titulo
        titulo="IA sob supervisão"
        subtitulo="A IA recomenda, o regulador decide: concordância, divergências e saúde do parecer em lote"
      />
      {error ? <Erro mensagem={error} /> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading || !k ? (
          <KpiCarregando n={4} />
        ) : (
          <>
            <Kpi rotulo="Decisões registradas" valor={fmtInt(k.decisoes)} contexto="pelos reguladores, no app" />
            <Kpi rotulo="Concordância com a IA" valor={fmtPct(k.concordancia)} contexto="decisão igual à recomendação" />
            <Kpi rotulo="Divergências" valor={fmtInt(k.divergencias)} contexto="insumo do retreino do modelo e do prompt" tom="alerta" />
            <Kpi
              rotulo="Aprovado × sugerido"
              valor={fmtBRL(k.valor_aprovado)}
              contexto={`a IA sugeriu ${fmtBRL(k.valor_sugerido_ia)} nesses casos`}
            />
          </>
        )}
      </div>
      <Fonte>
        Fonte: metric view <code>gold.regulacao_metrics</code> sobre <code>operacional.lb_decisoes_regulador_history</code>{' '}
        (Lakehouse Sync do Lakebase, com alguns minutos de atraso).
      </Fonte>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Onde o regulador concorda e onde diverge</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              queryKey="supervisao_matriz"
              parameters={{}}
              pageSize={10}
              transform={(linhas: Array<Record<string, unknown>>) =>
                linhas.map((l) => ({
                  'Recomendação da IA': rotuloRecomendacao(l.recomendacao_ia),
                  'Decisão do regulador': rotuloRecomendacao(l.decisao_regulador),
                  Decisões: fmtInt(l.decisoes),
                }))
              }
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Parecer em lote: versões em produção e pendências</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              queryKey="supervisao_parecer"
              parameters={{}}
              pageSize={10}
              transform={(linhas: Array<Record<string, unknown>>) =>
                linhas.map((l) => ({
                  LLM: texto(l.llm),
                  Prompt: `v${texto(l.versao_prompt)}`,
                  'Modelo de suspeita': `v${texto(l.versao_modelo)}`,
                  Status: texto(l.status_parecer),
                  Avisos: fmtInt(l.avisos),
                  'Confiança média': fmtDec(l.confianca_media),
                }))
              }
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Como o laço de retorno fecha</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-1 text-foreground">
          <p>1. O regulador decide no app; a decisão é gravada no Lakebase com a recomendação da IA ao lado.</p>
          <p>2. O Lakehouse Sync leva cada decisão ao Unity Catalog (histórico SCD2), com governança e lineage.</p>
          <p>3. Esta tela mede a concordância. As divergências viram rótulos para o retreino do modelo de suspeita e para a próxima versão do prompt, que passa pelo mesmo portão de qualidade (próximo passo).</p>
        </CardContent>
      </Card>
    </div>
  );
}

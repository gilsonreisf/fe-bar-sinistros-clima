// Painel do evento (diretoria e coordenação): quanto chegou, quanto já saiu pelo fast track, quanto espera na fila e
// onde está o risco. Fonte: metric view gold.sinistros_metrics (definições únicas no UC; D-025).
import { BarChart, Card, CardContent, CardHeader, CardTitle, DonutChart, useAnalyticsQuery } from '@databricks/appkit-ui/react';
import { Erro, Fonte, Kpi, KpiCarregando, TabelaSimples, Titulo } from '../components/Comum';
import { fmtBRL, fmtInt, fmtPct } from '../lib/formato';

export function PainelPage() {
  const { data, loading, error } = useAnalyticsQuery('painel_kpis', {});
  const k = data?.[0];
  const mun = useAnalyticsQuery('painel_municipios', {});

  return (
    <div className="space-y-6">
      <Titulo
        titulo="Painel do evento"
        subtitulo="Enchentes, vendavais e granizo: avisos recebidos, liberados no fast track e na fila do regulador"
      />

      {error ? <Erro mensagem={error} /> : null}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading || !k ? (
          <KpiCarregando n={8} />
        ) : (
          <>
            <Kpi rotulo="Avisos recebidos" valor={fmtInt(k.avisos)} contexto="todos os lotes do evento" />
            <Kpi rotulo="Exposição (valor reclamado)" valor={fmtBRL(k.valor_reclamado)} contexto="soma pedida pelos segurados" />
            <Kpi
              rotulo="Liberados no fast track"
              valor={fmtPct(k.pct_fast_track)}
              contexto={`${fmtInt(k.fast_track)} sinistros · ${fmtBRL(k.valor_liberado_fast_track)} sugeridos`}
            />
            <Kpi rotulo="Na fila do regulador" valor={fmtInt(k.na_fila)} contexto="fora do fast track, por prioridade" />
            <Kpi
              rotulo="Sinistros suspeitos"
              valor={fmtInt(k.suspeitos)}
              contexto={`score ≥ 0,2 · ${fmtBRL(k.valor_suspeito)} reclamados`}
              tom="alerta"
            />
            <Kpi
              rotulo="Ajuste sugerido pela IA"
              valor={fmtBRL(k.ajuste_ia)}
              contexto="pagamentos parciais e recusas; a decisão é do regulador"
            />
            <Kpi
              rotulo="Pareceres pendentes"
              valor={fmtInt(k.pareceres_pendentes)}
              contexto="sem parecer válido ainda; o job tenta de novo"
            />
            <Kpi
              rotulo="Exposição já liberada"
              valor={fmtPct(Number(k.valor_liberado_fast_track) / Math.max(Number(k.valor_reclamado), 1))}
              contexto="sugerido no fast track ÷ valor reclamado"
            />
          </>
        )}
      </div>
      <Fonte>
        Fonte: metric view <code>gold.sinistros_metrics</code> (Unity Catalog), atualizada a cada lote processado pelo job do
        evento. Valores em reais; recomendações da IA são pareceres prévios.
      </Fonte>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Cerca de metade dos avisos de cada lote sai pelo fast track</CardTitle>
          </CardHeader>
          <CardContent>
            <BarChart
              queryKey="painel_por_lote"
              parameters={{}}
              xKey="lote"
              yKey={['fast_track', 'fila']}
              stacked
              showLegend
              colorPalette="categorical"
              height={280}
              ariaLabel="Avisos por lote: fast track e fila do regulador"
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">O que o parecer prévio recomendou</CardTitle>
          </CardHeader>
          <CardContent>
            <DonutChart
              queryKey="painel_recomendacoes"
              parameters={{}}
              xKey="recomendacao"
              yKey="avisos"
              colorPalette="categorical"
              height={280}
              showLegend
              ariaLabel="Recomendações do parecer prévio"
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Municípios com maior exposição</CardTitle>
        </CardHeader>
        <CardContent>
          <TabelaSimples
            linhas={mun.data}
            carregando={mun.loading}
            erro={mun.error}
            vazio="Os municípios aparecem quando o primeiro lote for analisado."
            chave={(l) => String(l.municipio)}
            colunas={[
              { titulo: 'Município', valor: (l) => l.municipio },
              { titulo: 'Avisos', valor: (l) => fmtInt(l.avisos), direita: true },
              { titulo: 'Valor reclamado', valor: (l) => fmtBRL(l.valor_reclamado), direita: true },
              { titulo: 'Suspeitos', valor: (l) => fmtInt(l.suspeitos), direita: true },
              { titulo: 'Fast track', valor: (l) => fmtPct(l.pct_fast_track), direita: true },
            ]}
          />
        </CardContent>
      </Card>
    </div>
  );
}

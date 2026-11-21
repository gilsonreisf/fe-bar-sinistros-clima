// Detalhe do sinistro: o regulador vê o parecer prévio da IA ao lado das evidências (apólice, clima, documentos e
// suspeita), decide e registra o motivo. A decisão vai ao Lakebase e volta ao UC (laço de retorno, D-024).
import { useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  Alert,
  AlertDescription,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Textarea,
  useAnalyticsQuery,
} from '@databricks/appkit-ui/react';
import { sql } from '@databricks/appkit-ui/js';
import { Bot, Sparkles } from 'lucide-react';
import { Erro, Titulo, Vazio } from '../components/Comum';
import { api, useApi } from '../lib/api';
import {
  ROTULO_RECOMENDACAO,
  fmtBRL,
  fmtData,
  fmtDataHora,
  fmtDec,
  fmtInt,
  fmtPct,
  listaJson,
  numero,
  rotuloMotivo,
  rotuloRecomendacao,
} from '../lib/formato';

interface Operacao {
  atribuicao: { regulador: string; status: string; atribuido_em: string } | null;
  decisoes: Array<{ id_decisao: string; regulador: string; decisao: string; valor_aprovado: string; motivo: string; concordou_com_ia: boolean; criado_em: string }>;
  reanalises: Array<{ id_reanalise: string; solicitado_por: string; recomendacao: string; valor_sugerido: string; motivos: string[] | null; status_parecer: string; versao_prompt: string; trace_id: string; criado_em: string }>;
}

function Linha({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1 text-sm">
      <span className="text-muted-foreground">{rotulo}</span>
      <span className="text-right text-foreground">{children}</span>
    </div>
  );
}

const simNao = (v: unknown) => (v === null || v === undefined ? '—' : v === true || v === 'true' ? 'sim' : 'não');

export function SinistroPage() {
  const { id = '' } = useParams();
  const { data, loading, error } = useAnalyticsQuery('sinistro_detalhe', { id_aviso: sql.string(id) });
  const op = useApi<Operacao>(`/api/sinistros/${encodeURIComponent(id)}/operacao`);
  const s = data?.[0];

  if (loading) return <Skeleton className="h-96 w-full" />;
  if (error) return <Erro mensagem={error} />;
  if (!s) return <Vazio titulo="Sinistro não encontrado" descricao={`Não há análise para ${id}. Volte à fila.`} />;

  const score = numero(s.score_suspeita) ?? 0;
  const decidido = (op.dados?.decisoes.length ?? 0) > 0;

  return (
    <div className="space-y-6">
      <Titulo
        titulo={`Sinistro ${s.id_aviso}`}
        subtitulo={`${s.municipio} · ${s.causa_declarada} · ${s.ramo} · aviso em ${fmtData(s.data_aviso)} · segurado ${s.cpf_segurado ?? '—'}`}
        acoes={
          <div className="flex gap-2 items-center">
            {s.fast_track ? <Badge>fast track</Badge> : <Badge variant="outline">fila do regulador</Badge>}
            <Badge variant={score >= 0.2 ? 'destructive' : 'secondary'}>suspeita {fmtDec(score)}</Badge>
            <Link to="/fila" className="text-sm text-primary underline underline-offset-4">
              voltar à fila
            </Link>
          </div>
        }
      />
      <p className="text-sm text-foreground">“{s.descricao}”</p>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">Parecer prévio da IA: {rotuloRecomendacao(s.recomendacao_ia)}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Reclamado</p>
                <p className="text-lg font-semibold tabular-nums">{fmtBRL(s.valor_reclamado, true)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Sugerido (calculado em código)</p>
                <p className="text-lg font-semibold tabular-nums">{fmtBRL(s.valor_sugerido, true)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Confiança</p>
                <p className="text-lg font-semibold tabular-nums">{fmtPct(s.confianca)}</p>
              </div>
            </div>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              {listaJson(s.motivos).map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-1">
              {listaJson(s.clausulas).map((c) => (
                <Badge key={c} variant="outline">
                  {c}
                </Badge>
              ))}
              {listaJson(s.itens_excluidos).map((i) => (
                <Badge key={i} variant="destructive">
                  excluído: {i}
                </Badge>
              ))}
            </div>
            <Alert>
              <AlertDescription className="text-xs">
                Gerado por IA ({s.llm}, prompt v{s.versao_prompt}; trace <code>{s.trace_id || '—'}</code>). É um parecer
                prévio: confira as evidências ao lado. A decisão é sua.
              </AlertDescription>
            </Alert>
            <Reanalise id={id} historico={op.dados?.reanalises ?? []} aoConcluir={op.recarregar} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Evidências</CardTitle>
          </CardHeader>
          <CardContent className="divide-y">
            <div className="pb-2">
              <Linha rotulo="Cobertura válida">{simNao(s.cobertura_valida)}</Linha>
              <Linha rotulo="Dentro da vigência">{simNao(s.dentro_vigencia)}</Linha>
              <Linha rotulo="Dias desde a contratação">{fmtInt(s.dias_desde_contratacao)}</Linha>
              <Linha rotulo="LMI · franquia">
                {fmtBRL(s.lmi)} · {fmtBRL(s.franquia)}
              </Linha>
            </div>
            <div className="py-2">
              <Linha rotulo="Evidência climática">
                {s.forca_evidencia_climatica} ({s.fonte_evidencia ?? '—'})
              </Linha>
              <Linha rotulo="Defesa Civil">{simNao(s.registro_defesa_civil)}</Linha>
              <Linha rotulo="Chuva · rajada">
                {s.chuva_mm === null ? '—' : `${fmtDec(s.chuva_mm)} mm`} · {s.rajada_max_ms === null ? '—' : `${fmtDec(s.rajada_max_ms)} m/s`}
              </Linha>
              <Linha rotulo="Estação INMET mais próxima">{fmtDec(s.distancia_estacao_km)} km</Linha>
            </div>
            <div className="py-2">
              <Linha rotulo="Orçamento">{fmtBRL(s.valor_orcamento, true)}</Linha>
              <Linha rotulo="Desvio contra a tabela">{fmtPct(s.desvio_preco_pct)}</Linha>
              <Linha rotulo="Menciona dano anterior">{simNao(s.menciona_dano_anterior)}</Linha>
              <Linha rotulo="Prestador no evento (30 dias)">{fmtPct(s.participacao_prestador_30d)}</Linha>
            </div>
            <div className="pt-2 space-y-2">
              <p className="text-xs text-muted-foreground">Fatores da suspeita (modelo v{s.versao_modelo})</p>
              <p className="text-sm">{s.fatores_suspeita || 'sem fatores relevantes'}</p>
              <div className="flex flex-wrap gap-1">
                {[...listaJson(s.bloqueios_fast_track), ...listaJson(s.alertas_qualidade), ...listaJson(s.flags_documento)].map((m, i) => (
                  <Badge key={`${m}-${i}`} variant="outline">
                    {rotuloMotivo(m)}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Decisão do regulador</CardTitle>
        </CardHeader>
        <CardContent>
          {op.erro ? <Erro mensagem={op.erro} /> : null}
          {op.dados?.atribuicao ? (
            <p className="text-sm text-muted-foreground mb-3">
              Com {op.dados.atribuicao.regulador} desde {fmtDataHora(op.dados.atribuicao.atribuido_em)} ({op.dados.atribuicao.status}).
            </p>
          ) : null}
          {decidido ? (
            <div className="space-y-2">
              {op.dados?.decisoes.map((d) => (
                <div key={d.id_decisao} className="text-sm">
                  <Badge variant={d.concordou_com_ia ? 'secondary' : 'destructive'}>
                    {d.concordou_com_ia ? 'concordou com a IA' : 'divergiu da IA'}
                  </Badge>{' '}
                  <strong>{rotuloRecomendacao(d.decisao)}</strong> · {fmtBRL(d.valor_aprovado, true)} · {d.regulador} ·{' '}
                  {fmtDataHora(d.criado_em)} — {d.motivo}
                </div>
              ))}
            </div>
          ) : (
            <FormDecisao
              id={id}
              recomendacao={String(s.recomendacao_ia ?? 'investigar')}
              valorSugerido={numero(s.valor_sugerido) ?? 0}
              aoGravar={op.recarregar}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function FormDecisao({ id, recomendacao, valorSugerido, aoGravar }: { id: string; recomendacao: string; valorSugerido: number; aoGravar: () => void }) {
  // Um id por decisão, criado no cliente: reenvio ou clique duplo não duplica (ON CONFLICT DO NOTHING no Lakebase).
  const idDecisao = useRef(crypto.randomUUID());
  const [decisao, setDecisao] = useState(recomendacao in ROTULO_RECOMENDACAO ? recomendacao : 'investigar');
  const [valor, setValor] = useState(String(valorSugerido.toFixed(2)));
  const [motivo, setMotivo] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar() {
    setEnviando(true);
    setErro(null);
    try {
      await api(`/api/sinistros/${encodeURIComponent(id)}/decisao`, {
        method: 'POST',
        body: JSON.stringify({ id_decisao: idDecisao.current, decisao, valor_aprovado: Number(valor), motivo }),
      });
      aoGravar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  const diverge = decisao !== recomendacao;
  return (
    <div className="grid gap-4 md:grid-cols-4 items-end">
      <div className="space-y-1">
        <Label>Decisão</Label>
        <Select value={decisao} onValueChange={setDecisao}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(ROTULO_RECOMENDACAO).map(([v, r]) => (
              <SelectItem key={v} value={v}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="valor">Valor aprovado (R$)</Label>
        <Input id="valor" inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value.replace(',', '.'))} />
      </div>
      <div className="space-y-1 md:col-span-2">
        <Label htmlFor="motivo">Motivo {diverge ? '(obrigatório: você está divergindo da IA)' : ''}</Label>
        <Textarea id="motivo" rows={2} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
      </div>
      <div className="md:col-span-4 flex items-center gap-3">
        <Button onClick={() => void enviar()} disabled={enviando || motivo.trim().length < 3 || !Number.isFinite(Number(valor))}>
          {enviando ? 'Gravando…' : 'Registrar decisão'}
        </Button>
        {erro ? <span className="text-sm text-destructive">{erro}</span> : null}
      </div>
    </div>
  );
}

function Reanalise({ id, historico, aoConcluir }: { id: string; historico: Operacao['reanalises']; aoConcluir: () => void }) {
  const [rodando, setRodando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function reanalisar() {
    setRodando(true);
    setErro(null);
    try {
      await api(`/api/sinistros/${encodeURIComponent(id)}/reanalisar`, { method: 'POST' });
      aoConcluir();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setRodando(false);
    }
  }

  const ultima = historico[0];
  return (
    <div className="space-y-2 border-t pt-3">
      <div className="flex items-center gap-3">
        <Button variant="outline" onClick={() => void reanalisar()} disabled={rodando}>
          <Sparkles className="h-4 w-4 mr-2" /> {rodando ? 'Reanalisando (5 a 10 s)…' : 'Reanalisar com IA'}
        </Button>
        <span className="text-xs text-muted-foreground">Endpoint do parecer (Claude Sonnet, AI Gateway e tracing)</span>
      </div>
      {erro ? <span className="text-sm text-destructive">{erro}</span> : null}
      {ultima ? (
        <div className="text-sm space-y-1">
          <p>
            <strong>Reanálise de {fmtDataHora(ultima.criado_em)}:</strong> {rotuloRecomendacao(ultima.recomendacao)} ·{' '}
            {fmtBRL(ultima.valor_sugerido, true)} · {ultima.status_parecer} · trace <code>{ultima.trace_id || '—'}</code>
          </p>
          <ul className="list-disc pl-5 text-muted-foreground">
            {listaJson(ultima.motivos).map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

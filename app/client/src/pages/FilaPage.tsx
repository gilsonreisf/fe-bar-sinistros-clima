// Fila do regulador (Lakebase): os sinistros fora do fast track, do mais prioritário para o menos. "Assumir próximo" é
// atômico no Postgres: dois reguladores nunca recebem o mesmo caso (evidencias/03-lakebase.md).
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import {
  Badge,
  Button,
  Card,
  CardContent,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@databricks/appkit-ui/react';
import { Hand, RefreshCw } from 'lucide-react';
import { Erro, Fonte, Titulo, Vazio } from '../components/Comum';
import { api, useApi } from '../lib/api';
import { fmtBRL, fmtData, fmtDec, listaJson, rotuloMotivo, rotuloRecomendacao } from '../lib/formato';

interface ItemFila {
  id_aviso: string;
  data_aviso: string;
  municipio: string;
  causa_declarada: string;
  valor_reclamado: number | string;
  score_suspeita: number | string | null;
  recomendacao_ia: string | null;
  valor_sugerido: number | string | null;
  prioridade: number | string;
  bloqueios_fast_track: string[] | string | null;
  regulador: string | null;
  status: string | null;
}

export function FilaPage() {
  const { dados, erro, carregando, recarregar } = useApi<ItemFila[]>('/api/fila?limite=50');
  const [assumindo, setAssumindo] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const navegar = useNavigate();

  async function assumirProximo() {
    setAssumindo(true);
    setAviso(null);
    try {
      const r = await api<{ id_aviso: string | null }>('/api/fila/assumir', { method: 'POST' });
      if (r.id_aviso) void navegar(`/sinistro/${r.id_aviso}`);
      else setAviso('Não há sinistro livre na fila agora.');
    } catch (e) {
      setAviso(e instanceof Error ? e.message : String(e));
    } finally {
      setAssumindo(false);
    }
  }

  return (
    <div className="space-y-6">
      <Titulo
        titulo="Fila do regulador"
        subtitulo="Ordenada por prioridade: 45% suspeita, 35% valor e 20% tempo de espera do segurado"
        acoes={
          <div className="flex gap-2">
            <Button variant="outline" onClick={recarregar} disabled={carregando}>
              <RefreshCw className="h-4 w-4 mr-2" /> Atualizar
            </Button>
            <Button onClick={() => void assumirProximo()} disabled={assumindo}>
              <Hand className="h-4 w-4 mr-2" /> {assumindo ? 'Assumindo…' : 'Assumir próximo'}
            </Button>
          </div>
        }
      />
      {aviso ? <Erro titulo="Assumir próximo" mensagem={aviso} /> : null}
      {erro ? <Erro mensagem={erro} /> : null}

      <Card>
        <CardContent className="p-0">
          {carregando && !dados ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 8 }, (_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : dados && dados.length === 0 ? (
            <Vazio titulo="Fila vazia" descricao="Todos os sinistros fora do fast track já foram decididos." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sinistro</TableHead>
                  <TableHead>Município · causa</TableHead>
                  <TableHead className="text-right">Reclamado</TableHead>
                  <TableHead className="text-right">Suspeita</TableHead>
                  <TableHead>Parecer da IA</TableHead>
                  <TableHead>Por que não foi ao fast track</TableHead>
                  <TableHead className="text-right">Prioridade</TableHead>
                  <TableHead>Situação</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(dados ?? []).map((s) => {
                  const score = Number(s.score_suspeita ?? 0);
                  return (
                    <TableRow key={s.id_aviso}>
                      <TableCell>
                        <Link className="text-primary underline underline-offset-4" to={`/sinistro/${s.id_aviso}`}>
                          {s.id_aviso}
                        </Link>
                        <div className="text-xs text-muted-foreground">aviso em {fmtData(s.data_aviso)}</div>
                      </TableCell>
                      <TableCell>
                        {s.municipio}
                        <div className="text-xs text-muted-foreground">{s.causa_declarada}</div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{fmtBRL(s.valor_reclamado)}</TableCell>
                      <TableCell className={`text-right tabular-nums ${score >= 0.2 ? 'text-destructive font-medium' : ''}`}>
                        {fmtDec(s.score_suspeita)}
                      </TableCell>
                      <TableCell>
                        {rotuloRecomendacao(s.recomendacao_ia)}
                        <div className="text-xs text-muted-foreground">{fmtBRL(s.valor_sugerido)}</div>
                      </TableCell>
                      <TableCell className="max-w-64">
                        <div className="flex flex-wrap gap-1">
                          {listaJson(s.bloqueios_fast_track).slice(0, 3).map((m) => (
                            <Badge key={m} variant="outline">
                              {rotuloMotivo(m)}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{fmtDec(s.prioridade)}</TableCell>
                      <TableCell>
                        {s.regulador ? <Badge variant="secondary">com {s.regulador}</Badge> : <Badge variant="outline">livre</Badge>}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <Fonte>
        Fonte: Lakebase (Postgres), synced table do gold atualizada a cada lote e schema <code>operacao</code> com as
        atribuições. Mostra os 50 primeiros da fila.
      </Fonte>
    </div>
  );
}

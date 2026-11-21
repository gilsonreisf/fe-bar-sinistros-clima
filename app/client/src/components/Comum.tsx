import type { ReactNode } from 'react';
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Card,
  CardContent,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@databricks/appkit-ui/react';
import { AlertTriangle } from 'lucide-react';

/** Número de topo: rótulo, valor, contexto (unidade/período/comparação) e, se houver, um destaque semântico. */
export function Kpi({ rotulo, valor, contexto, tom }: { rotulo: string; valor: ReactNode; contexto?: ReactNode; tom?: 'alerta' }) {
  return (
    <Card>
      <CardContent className="p-4 space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{rotulo}</p>
        <p className={`text-2xl font-semibold tabular-nums ${tom === 'alerta' ? 'text-destructive' : 'text-foreground'}`}>{valor}</p>
        {contexto ? <p className="text-xs text-muted-foreground">{contexto}</p> : null}
      </CardContent>
    </Card>
  );
}

export function KpiCarregando({ n = 4 }: { n?: number }) {
  return (
    <>
      {Array.from({ length: n }, (_, i) => (
        <Skeleton key={i} className="h-24 w-full" />
      ))}
    </>
  );
}

export function Erro({ titulo = 'Não foi possível carregar', mensagem }: { titulo?: string; mensagem: string }) {
  return (
    <Alert variant="destructive">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>{titulo}</AlertTitle>
      <AlertDescription>{mensagem}</AlertDescription>
    </Alert>
  );
}

export function Vazio({ titulo, descricao }: { titulo: string; descricao: string }) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle>{titulo}</EmptyTitle>
        <EmptyDescription>{descricao}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

/** Procedência do número: de onde vem e com que frequência muda (todo KPI mostra a fonte). */
export function Fonte({ children }: { children: ReactNode }) {
  return <p className="text-xs text-muted-foreground">{children}</p>;
}

export function Titulo({ titulo, subtitulo, acoes }: { titulo: string; subtitulo?: ReactNode; acoes?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">{titulo}</h2>
        {subtitulo ? <p className="text-sm text-muted-foreground">{subtitulo}</p> : null}
      </div>
      {acoes}
    </div>
  );
}

export interface Coluna<L> {
  titulo: string;
  valor: (linha: L) => ReactNode;
  direita?: boolean;
}

/** Tabela pequena (até algumas dezenas de linhas já agregadas no SQL), com carregamento, erro e vazio. */
export function TabelaSimples<L>({ linhas, colunas, carregando, erro, vazio, chave }: {
  linhas: L[] | null | undefined;
  colunas: Coluna<L>[];
  carregando: boolean;
  erro: string | null;
  vazio: string;
  chave: (linha: L, i: number) => string;
}) {
  if (erro) return <Erro mensagem={erro} />;
  if (carregando || !linhas) return <Skeleton className="h-48 w-full" />;
  if (linhas.length === 0) return <Vazio titulo="Sem dados ainda" descricao={vazio} />;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {colunas.map((c) => (
            <TableHead key={c.titulo} className={c.direita ? 'text-right' : ''}>
              {c.titulo}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {linhas.map((l, i) => (
          <TableRow key={chave(l, i)}>
            {colunas.map((c) => (
              <TableCell key={c.titulo} className={c.direita ? 'text-right tabular-nums' : ''}>
                {c.valor(l)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

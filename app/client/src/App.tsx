import { createBrowserRouter, RouterProvider, NavLink, Outlet } from 'react-router';
import { useState } from 'react';
import {
  Button,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  useIsMobile,
} from '@databricks/appkit-ui/react';
import { Menu } from 'lucide-react';
import { MessageSquareText } from 'lucide-react';
import { FilaPage } from './pages/FilaPage';
import { PainelPage } from './pages/PainelPage';
import { SinistroPage } from './pages/SinistroPage';
import { SupervisaoPage } from './pages/SupervisaoPage';
import { useApi, type Config } from './lib/api';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive
      ? 'bg-primary text-primary-foreground'
      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  }`;

const mobileNavLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
    isActive
      ? 'bg-primary text-primary-foreground'
      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  }`;

type NavLinkClassFn = (props: { isActive: boolean }) => string;

function NavLinks({ className, linkClass, onClick }: { className?: string; linkClass: NavLinkClassFn; onClick?: () => void }) {
  return (
    <nav className={className}>
      <NavLink to="/" end className={linkClass} onClick={onClick}>
        Painel do evento
      </NavLink>
      <NavLink to="/fila" className={linkClass} onClick={onClick}>
        Fila do regulador
      </NavLink>
      <NavLink to="/supervisao" className={linkClass} onClick={onClick}>
        IA sob supervisão
      </NavLink>
    </nav>
  );
}

function Layout() {
  const isMobile = useIsMobile();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b px-4 md:px-6 py-3 flex items-center gap-4">
        <h1 className="text-lg font-semibold text-foreground">Regulação de sinistros climáticos</h1>
        {/* Desktop nav — hidden below md breakpoint */}
        <NavLinks className="hidden md:flex gap-1" linkClass={navLinkClass} />
        <Cabecalho />
        {/* Mobile nav — visible below md breakpoint */}
        <div className="ml-auto md:hidden">
          {/* Gate on isMobile so the portaled sheet can't linger on desktop
              (replaces a set-state-in-effect reset). */}
          <Sheet open={mobileNavOpen && isMobile} onOpenChange={setMobileNavOpen}>
            <Button variant="ghost" size="icon" onClick={() => setMobileNavOpen(true)}>
              <Menu className="h-5 w-5" />
              <span className="sr-only">Abrir navegação</span>
            </Button>
            <SheetContent side="left">
              <SheetHeader>
                <SheetTitle>Navegação</SheetTitle>
              </SheetHeader>
              <NavLinks className="flex flex-col gap-1" linkClass={mobileNavLinkClass} onClick={() => setMobileNavOpen(false)} />
            </SheetContent>
          </Sheet>
        </div>
      </header>

      <main className="flex-1 p-4 md:p-6">
        <Outlet />
      </main>
    </div>
  );
}

/** Quem está usando (identidade repassada pelo Databricks Apps) e o atalho para o Genie da diretoria. */
function Cabecalho() {
  const { dados } = useApi<Config>('/api/config');
  return (
    <div className="ml-auto hidden md:flex items-center gap-3 text-sm">
      {dados?.genieUrl ? (
        <a
          href={dados.genieUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary underline underline-offset-4"
        >
          <MessageSquareText className="h-4 w-4" /> Perguntar ao Genie
        </a>
      ) : null}
      {dados ? <span className="text-muted-foreground">{dados.regulador}</span> : null}
    </div>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <PainelPage /> },
      { path: '/fila', element: <FilaPage /> },
      { path: '/sinistro/:id', element: <SinistroPage /> },
      { path: '/supervisao', element: <SupervisaoPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}

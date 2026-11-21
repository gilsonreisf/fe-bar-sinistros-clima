import { useCallback, useEffect, useState } from 'react';

export class ErroApi extends Error {}

export async function api<T>(caminho: string, init?: RequestInit): Promise<T> {
  const r = await fetch(caminho, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  const corpo: unknown = await r.json().catch(() => null);
  if (!r.ok) {
    const msg = corpo && typeof corpo === 'object' && 'error' in corpo ? String(corpo.error) : `Erro ${r.status}`;
    throw new ErroApi(msg);
  }
  return corpo as T;
}

interface Resultado<T> {
  chave: string;
  dados: T | null;
  erro: string | null;
}

/** GET com estados de carregamento e erro, e recarga manual. Carregando = ainda sem resposta para a chave atual. */
export function useApi<T>(caminho: string | null) {
  const [versao, setVersao] = useState(0);
  const [res, setRes] = useState<Resultado<T>>({ chave: '', dados: null, erro: null });
  const chave = caminho ? `${caminho}#${versao}` : '';
  const recarregar = useCallback(() => setVersao((v) => v + 1), []);

  useEffect(() => {
    if (!caminho) return;
    let ativo = true;
    api<T>(caminho)
      .then((dados) => ativo && setRes({ chave, dados, erro: null }))
      .catch((e: unknown) => ativo && setRes((r) => ({ chave, dados: r.dados, erro: e instanceof Error ? e.message : String(e) })));
    return () => {
      ativo = false;
    };
  }, [caminho, chave]);

  return { dados: res.dados, erro: res.erro, carregando: Boolean(caminho) && res.chave !== chave, recarregar };
}

export interface Config {
  regulador: string;
  genieUrl: string | null;
}

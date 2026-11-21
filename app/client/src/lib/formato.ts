// Formatação pt-BR. Os valores do SQL podem chegar como texto (DECIMAL/BIGINT): sempre converter antes.
const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const brlCentavos = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 });

/** Texto de um valor vindo do SQL ou da API (string, número, booleano ou estrutura). */
export const texto = (v: unknown): string =>
  v === null || v === undefined ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v as string | number | boolean);

export const numero = (v: unknown): number | null => (v === null || v === undefined || v === '' ? null : Number(v));
export const fmtBRL = (v: unknown, centavos = false) => {
  const n = numero(v);
  return n === null ? '—' : (centavos ? brlCentavos : brl).format(n);
};
export const fmtInt = (v: unknown) => {
  const n = numero(v);
  return n === null ? '—' : inteiro.format(n);
};
export const fmtDec = (v: unknown) => {
  const n = numero(v);
  return n === null ? '—' : decimal.format(n);
};
/** v é uma fração (0,55 → 55,0%). */
export const fmtPct = (v: unknown) => {
  const n = numero(v);
  return n === null ? '—' : `${(n * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`;
};
export const fmtData = (v: unknown) => (v ? new Date(texto(v)).toLocaleDateString('pt-BR', { timeZone: 'UTC' }) : '—');
export const fmtDataHora = (v: unknown) => (v ? new Date(texto(v)).toLocaleString('pt-BR') : '—');

export const listaJson = (v: unknown): string[] => {
  if (Array.isArray(v)) return v.map(String);
  if (typeof v !== 'string' || !v) return [];
  try {
    const x: unknown = JSON.parse(v);
    return Array.isArray(x) ? x.map(String) : [];
  } catch {
    return [];
  }
};

export const ROTULO_RECOMENDACAO: Record<string, string> = {
  pagar_integral: 'Pagar integral',
  pagar_parcial: 'Pagar parcial',
  recusar: 'Recusar',
  investigar: 'Investigar',
};
export const rotuloRecomendacao = (v: unknown) => ROTULO_RECOMENDACAO[texto(v)] ?? (v ? texto(v) : 'sem parecer');
export const rotuloMotivo = (v: string) => v.replaceAll('_', ' ');

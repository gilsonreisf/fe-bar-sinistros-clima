import { describe, expect, it } from 'vitest';
import { fmtBRL, fmtPct, listaJson, rotuloRecomendacao, texto, verdadeiro } from './formato';

describe('formatação pt-BR', () => {
  it('valores do SQL chegam como texto e são convertidos', () => {
    expect(fmtBRL('1234.5', true)).toMatch(/R\$\s1\.234,50/);
    expect(fmtPct('0.543')).toBe('54,3%');
    expect(fmtBRL(null)).toBe('—');
  });
  it('booleano do SQL em texto: "false" não é verdadeiro', () => {
    expect(verdadeiro('false')).toBe(false);
    expect(verdadeiro('true')).toBe(true);
    expect(verdadeiro(true)).toBe(true);
  });
  it('listas em JSON e rótulos', () => {
    expect(listaJson('["a","b"]')).toEqual(['a', 'b']);
    expect(listaJson('não é json')).toEqual([]);
    expect(rotuloRecomendacao('pagar_parcial')).toBe('Pagar parcial');
    expect(rotuloRecomendacao(null)).toBe('sem parecer');
    expect(texto({ a: 1 })).toBe('{"a":1}');
  });
});

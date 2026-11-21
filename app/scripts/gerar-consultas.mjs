// Gera config/queries/*.sql a partir de consultas/*.sql, preenchendo ${catalogo} e ${schema_<camada>} com
// FE_BAR_CATALOGO e FE_BAR_PREFIXO_SCHEMA (mesma regra do módulo `ambiente` do projeto; D-016). Assim nenhum nome de
// catálogo fica fixo no código. Sem as variáveis (ex.: build no runtime do app), mantém os arquivos já gerados.
import { readdirSync, readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = join(dirname(fileURLToPath(import.meta.url)), '..');
const origem = join(raiz, 'consultas');
const destino = join(raiz, 'config', 'queries');
const catalogo = process.env.FE_BAR_CATALOGO;
const prefixo = process.env.FE_BAR_PREFIXO_SCHEMA ?? '';
const IDENT = /^[a-z_][a-z0-9_]*$/;

if (!catalogo) {
  const ja = existsSync(destino) && readdirSync(destino).some((f) => f.endsWith('.sql'));
  if (ja) {
    console.log('[consultas] FE_BAR_CATALOGO ausente: mantendo as consultas já geradas');
    process.exit(0);
  }
  console.error('[consultas] defina FE_BAR_CATALOGO (e, se usar, FE_BAR_PREFIXO_SCHEMA) no .env do app');
  process.exit(1);
}
if (!IDENT.test(catalogo) || !/^[a-z0-9_]*$/.test(prefixo)) {
  console.error('[consultas] catálogo ou prefixo inválido');
  process.exit(1);
}
const vars = { catalogo };
for (const c of ['landing', 'bronze', 'silver', 'gold', 'ml', 'operacional']) vars[`schema_${c}`] = `${prefixo}${c}`;

mkdirSync(destino, { recursive: true });
for (const f of readdirSync(origem).filter((n) => n.endsWith('.sql'))) {
  const sql = readFileSync(join(origem, f), 'utf8').replace(/\$\{([a-z_]+)\}/g, (m, nome) => {
    if (!(nome in vars)) throw new Error(`${f}: placeholder sem valor: ${nome}`);
    return vars[nome];
  });
  writeFileSync(join(destino, f), sql);
}
console.log(`[consultas] ${readdirSync(origem).length} consultas geradas para ${catalogo} (prefixo '${prefixo}')`);

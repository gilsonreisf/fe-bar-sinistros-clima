# Plano de implementação: fases 0 (ambiente) e 1 (dados)

> **Para agentes executores:** sub-skill obrigatória: use `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para implementar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** deixar o ambiente Databricks pronto e verificado, e produzir, com testes, todos os dados do caso (públicos e sintéticos), já carregados no Volume do UC e prontos para o pipeline da fase 2.

**Arquitetura:**
- Três pacotes Python locais, gerenciados com uv:
  - `ambiente`: nomes do catálogo, dos schemas e dos volumes, lidos de variáveis de ambiente (D-016);
  - `regras`: regras de negócio compartilhadas (clima e evidência), usadas pelo gerador e depois pelo pipeline;
  - `dados_sinteticos`: leitores dos dados públicos, gerador sintético e PDFs.
- Scripts em `scripts/` preparam os dados públicos, executam SQL no warehouse, verificam os recursos do workspace e publicam os lotes do evento no Volume.
- A geração roda localmente, com seed fixa. Os arquivos sobem para `/Volumes/<catálogo>/<schema landing>/arquivos/...` pela CLI e pelo SDK.

**Stack:** Python 3.12, uv, pandas, numpy, Faker (pt_BR), reportlab, pypdf (testes), databricks-sdk, Databricks CLI v1.25+, FEVM (workspace serverless na AWS).

**Spec:** `docs/specs/2026-11-20-regulacao-sinistros-climaticos-design.md`. Seções principais: 4 (dados), 4.3 (regras climáticas) e 12 (verificações).
**Roadmap:** `docs/planos/2026-11-20-roadmap.md`.

## Restrições globais
- **Idioma:** todo código, comentário, mensagem, documento e nome de objeto em **português**. Identificadores sem acento (ex.: `apolice`, `regulacao`).
- **Nenhum cliente real** é citado. A seguradora é "Vértice Seguros (fictícia)".
- **Dados:** somente sintéticos ou públicos. CPF no formato válido, gerado pelo Faker (fictício).
- **Profile da CLI e do SDK:** `fe-bar`. Variáveis de ambiente: `DATABRICKS_CONFIG_PROFILE=fe-bar` e `FE_BAR_WAREHOUSE_ID=<id>`.
- **UC (parametrizado, D-016):** nenhum nome de catálogo ou schema fica fixo no código. O catálogo vem de `FE_BAR_CATALOGO` (padrão `sinistros_clima`; no FEVM, `fe_bar_sinistros_catalog`) e os schemas `landing`, `bronze`, `silver`, `gold`, `ml` e `operacional` recebem o prefixo opcional `FE_BAR_PREFIXO_SCHEMA` (padrão vazio). Volumes: `<catálogo>.<landing>.arquivos` e `<catálogo>.<ml>.restrito`. Python lê os nomes do módulo `ambiente`; os `.sql` usam os placeholders `${catalogo}` e `${schema_<camada>}`; o bundle usa as variáveis `catalogo` e `prefixo_schema`.
- **Compute:** apenas serverless.
- **Seed global:** `20260920`.
- **Limiares climáticos de referência (spec 4.3):**
  - chuva ≥ 10 mm/h;
  - rajada ≥ 15 m/s;
  - queda de temperatura ≥ 4 °C em até 2 h;
  - alagamento com chuva diária ≥ 50 mm;
  - raio de 30 km;
  - janela de D−1 a D+1.
- **Evidência climática (D-015):** `forte` quando o INMET (a até 30 km, com sinal) **ou** a Defesa Civil (registro no município dentro da janela) confirmam; `contraria` quando há estação válida a até 30 km sem sinal **e** não há registro da Defesa Civil; nos demais casos, `fraca`.
- **Commits:** terminam com a linha `Co-authored-by: Isaac <no-reply@databricks.com>`. Autor: `-c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com"`. **Nenhum push** sem autorização do autor.
- **Organização:** depois de cada tarefa, atualizar a tabela de status do `README.md` quando mudar e registrar decisões novas em `docs/decisoes-e-tradeoffs.md`. No fim de cada fase, atualizar a memória do projeto.

## Foco de revisão
1. **Linhas do INMET com célula vazia, `-9999`, decimal com vírgula (`,2`) ou estação sem uma variável inteira** devem virar ausência (NaN), nunca zero. Teste em `testes/test_inmet.py::test_valores_ausentes_viram_nan`.
2. **Sinistro cuja estação válida mais próxima está a mais de 30 km, ou não mede uma das variáveis da causa,** deve ser classificado como `fraca`, nunca `contraria`. Teste em `testes/test_regras_clima.py::test_variavel_fora_do_raio_e_fraca`.
3. **A mesma apólice não pode ter dois avisos no evento**, e todo aviso precisa de apólice vigente na data de ocorrência. Teste em `testes/test_sinistros.py::test_apolices_unicas_e_vigentes`.
4. **O texto do PDF com acentos e valores em formato brasileiro** ("R$ 1.925,00") precisa sobreviver à extração de texto. Teste em `testes/test_documentos.py::test_pdf_orcamento_texto_extraivel`.
5. **Rodar `simular_evento.py` duas vezes** não pode duplicar nem pular lotes. Teste em `testes/test_simular_evento.py::test_publicacao_idempotente`.

---

## FASE 0: AMBIENTE

### Tarefa 0.1: Criar o workspace FEVM e o profile `fe-bar`

**Arquivos:**
- Criar: `.env.exemplo`
- Modificar: `README.md` (seção "Ambiente")

**Interfaces:**
- Produz: o profile `fe-bar` em `~/.databrickscfg`, a URL do workspace e o ID do SQL Warehouse serverless em `FE_BAR_WAREHOUSE_ID`.

- [ ] **Passo 1: autenticar o MCP do FEVM.** O usuário roda `/mcp`, seleciona `fe-vending-machine` e escolhe **Authenticate**. Se a primeira chamada devolver `-32042`, o usuário abre uma vez `https://gtm-ai-agent.cloud.databricks.com/explore/data/mcp-services/gtm_ai_agent_7474646471015793/ai_agent_resources/gtm_ai_fevm_mcp?o=7474646471015793`, faz o login e tenta de novo.

- [ ] **Passo 2: criar o deployment pela skill `fe-ai-tools:fevm`** com os seguintes parâmetros:
  - nuvem **AWS**, região **us-west-2**;
  - tipo **Serverless**, canal **Stable**;
  - nome `fe-bar-sinistros`;
  - maior duração permitida.

  O servidor do FEVM pede confirmação: **mostrar os parâmetros ao usuário e esperar o OK**.
  Esperado: a URL do workspace (`https://<algo>.cloud.databricks.com`).

- [ ] **Passo 3: criar o profile da CLI.**

Comando: `databricks auth login --host <URL_DO_WORKSPACE> --profile fe-bar`
Esperado: o navegador abre, o login é concluído e aparece `Profile fe-bar was successfully saved`.

- [ ] **Passo 4: verificar o acesso.**

Comando: `databricks current-user me -p fe-bar -o json | python3 -c "import json,sys;print(json.load(sys.stdin)['userName'])"`
Esperado: `gilson.reis@databricks.com`

- [ ] **Passo 5: descobrir o SQL Warehouse serverless.**

Comando: `databricks warehouses list -p fe-bar -o json | python3 -c "import json,sys;[print(w['id'],w['name'],w.get('enable_serverless_compute')) for w in json.load(sys.stdin)]"`
Esperado: pelo menos uma linha com `True`. Anotar o `id`.

- [ ] **Passo 6: criar o `.env.exemplo`** (o `.env` real fica fora do git):

```bash
# Copie para .env e preencha. O .env NÃO é versionado.
DATABRICKS_CONFIG_PROFILE=fe-bar
FE_BAR_WAREHOUSE_ID=<id do SQL Warehouse serverless>
```

Criar também o `.env` local com os valores reais.

- [ ] **Passo 7: adicionar ao `README.md`, depois da tabela de status,** a seção:

```markdown
## Ambiente

- Workspace: FEVM serverless (AWS us-west-2), acessado pelo profile `fe-bar` da Databricks CLI.
- Variáveis locais: copie `.env.exemplo` para `.env` e preencha o ID do SQL Warehouse.
```

- [ ] **Passo 8: commit.**

```bash
git add .env.exemplo README.md
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "chore: ambiente FEVM e variáveis locais

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 0.2: Projeto Python (uv + pytest)

**Arquivos:**
- Criar: `pyproject.toml`, `.python-version`, `src/regras/__init__.py`, `src/dados_sinteticos/__init__.py`, `testes/test_ambiente.py`
- Modificar: `.gitignore`

**Interfaces:**
- Produz: os pacotes importáveis `regras` e `dados_sinteticos`. O comando `uv run pytest` roda a suíte.

- [ ] **Passo 1: criar o `pyproject.toml`:**

```toml
[project]
name = "fe-bar-sinistros-clima"
version = "0.1.0"
description = "FE Bar: regulação inteligente de sinistros em eventos climáticos (dados sintéticos e públicos)"
requires-python = ">=3.11,<3.13"
dependencies = [
    "pandas>=2.2",
    "numpy>=1.26",
    "faker>=30",
    "reportlab>=4.2",
    "databricks-sdk>=0.81",
]

[dependency-groups]
dev = ["pytest>=8", "pypdf>=5"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/regras", "src/dados_sinteticos"]

[tool.pytest.ini_options]
pythonpath = ["scripts"]
testpaths = ["testes"]
```

- [ ] **Passo 2: fixar o Python e criar os pacotes.**

```bash
uv python pin 3.12
mkdir -p src/regras src/dados_sinteticos testes
printf '"""Regras de negócio compartilhadas (clima, evidência)."""\n' > src/regras/__init__.py
printf '"""Leitores de dados públicos e gerador de dados sintéticos."""\n' > src/dados_sinteticos/__init__.py
```

- [ ] **Passo 3: escrever o teste de ambiente** (`testes/test_ambiente.py`):

```python
def test_pacotes_importaveis():
    import dados_sinteticos
    import regras

    assert regras.__doc__ and dados_sinteticos.__doc__
```

- [ ] **Passo 4: acrescentar ao `.gitignore`:**

```gitignore

# Saídas locais do gerador e dados públicos brutos (grandes)
_saida/
dados/brutos/
```

- [ ] **Passo 5: instalar e rodar.**

Comando: `uv sync && uv run pytest -q`
Esperado: `1 passed`

- [ ] **Passo 6: commit.**

```bash
git add pyproject.toml .python-version uv.lock src testes .gitignore
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "chore: projeto Python com uv e pytest

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 0.3: Executor de SQL e criação do catálogo

> **Revisão na execução (D-016):** o `CREATE CATALOG` falhou por falta de permissão no metastore do FEVM. Por decisão do autor, os nomes passaram a ser parametrizados: módulo `src/ambiente` (com `testes/test_config_ambiente.py`), `aplicar_variaveis(sql, variaveis)` no executor, e o SQL dividido em `00_catalogo_opcional.sql` e `01_schemas_e_volumes.sql`.

**Arquivos:**
- Criar: `src/ambiente/__init__.py`, `scripts/executar_sql.py`, `src/governanca/00_catalogo_opcional.sql`, `src/governanca/01_schemas_e_volumes.sql`, `testes/test_config_ambiente.py`, `testes/test_executar_sql.py`

**Interfaces:**
- Produz:
  - `dividir_comandos(sql: str) -> list[str]`
  - `executar(w: WorkspaceClient, warehouse_id: str, comando: str) -> tuple[list[str], list[list[str]]]`
  - `aplicar_variaveis(sql: str, variaveis: dict[str, str]) -> str`, que troca `${nome}` e falha se faltar valor;
  - `ambiente.carregar_ambiente(env=os.environ) -> Ambiente`, com `catalogo`, `schema(camada)`, `volume_arquivos`, `volume_restrito` e `variaveis_sql()`;
  - CLI: `uv run python scripts/executar_sql.py <arquivo.sql>`, que lê `FE_BAR_WAREHOUSE_ID`, `DATABRICKS_CONFIG_PROFILE`, `FE_BAR_CATALOGO` e `FE_BAR_PREFIXO_SCHEMA`.

- [ ] **Passo 1: escrever o teste que falha** (`testes/test_executar_sql.py`):

```python
from executar_sql import dividir_comandos


def test_divide_por_ponto_e_virgula_no_fim_da_linha_e_ignora_comentarios():
    sql = """-- comentário
CREATE SCHEMA IF NOT EXISTS a.b
  COMMENT 'x; y';
CREATE VOLUME IF NOT EXISTS a.b.c;

SELECT 1
"""
    assert dividir_comandos(sql) == [
        "CREATE SCHEMA IF NOT EXISTS a.b\n  COMMENT 'x; y'",
        "CREATE VOLUME IF NOT EXISTS a.b.c",
        "SELECT 1",
    ]
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_executar_sql.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'executar_sql'`

- [ ] **Passo 3: implementar** `scripts/executar_sql.py`:

```python
"""Executa um arquivo .sql no SQL Warehouse, um comando por vez, e imprime os resultados.

Uso: uv run python scripts/executar_sql.py <arquivo.sql>
Requer as variáveis DATABRICKS_CONFIG_PROFILE e FE_BAR_WAREHOUSE_ID (veja .env.exemplo).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


def dividir_comandos(sql: str) -> list[str]:
    """Divide o SQL em comandos terminados por ';' no fim da linha, ignorando linhas de comentário."""
    comandos, atual = [], []
    for linha in sql.splitlines():
        if linha.strip().startswith("--"):
            continue
        atual.append(linha)
        if linha.rstrip().endswith(";"):
            comando = "\n".join(atual).strip().rstrip(";").strip()
            if comando:
                comandos.append(comando)
            atual = []
    resto = "\n".join(atual).strip()
    if resto:
        comandos.append(resto)
    return comandos


def executar(w: WorkspaceClient, warehouse_id: str, comando: str) -> tuple[list[str], list[list[str]]]:
    """Executa um comando e devolve (colunas, linhas). Levanta RuntimeError se falhar."""
    r = w.statement_execution.execute_statement(statement=comando, warehouse_id=warehouse_id, wait_timeout="50s")
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        erro = r.status.error.message if r.status.error else ""
        raise RuntimeError(f"{r.status.state.value}: {erro}\n--- comando ---\n{comando[:500]}")
    colunas = [c.name for c in r.manifest.schema.columns] if r.manifest and r.manifest.schema and r.manifest.schema.columns else []
    linhas = r.result.data_array if r.result and r.result.data_array else []
    return colunas, linhas


def main(caminho: str) -> None:
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    warehouse_id = os.environ["FE_BAR_WAREHOUSE_ID"]
    for i, comando in enumerate(dividir_comandos(Path(caminho).read_text(encoding="utf-8")), start=1):
        print(f"[{i}] {comando.splitlines()[0][:100]}")
        colunas, linhas = executar(w, warehouse_id, comando)
        if colunas:
            print("    " + " | ".join(colunas))
            for linha in linhas[:50]:
                print("    " + " | ".join("" if v is None else str(v) for v in linha))


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_executar_sql.py -q`
Esperado: `1 passed`

- [ ] **Passo 5: criar** `src/governanca/00_catalogo_opcional.sql` (só onde houver CREATE CATALOG):

```sql
-- Opcional: cria o catálogo onde o usuário tem CREATE CATALOG no metastore.
-- No FEVM não há essa permissão; lá o catálogo já vem criado com o workspace (D-016).
CREATE CATALOG IF NOT EXISTS ${catalogo}
  COMMENT 'FE Bar: regulação inteligente de sinistros em eventos climáticos. Dados sintéticos e públicos.';
```

e `src/governanca/01_schemas_e_volumes.sql`:

```sql
-- Schemas e volumes do projeto (idempotente). O catálogo precisa existir (veja 00_catalogo_opcional.sql).
-- Os nomes vêm do módulo `ambiente` (FE_BAR_CATALOGO e FE_BAR_PREFIXO_SCHEMA).
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_landing}
  COMMENT 'Arquivos brutos recebidos (avisos, documentos, apólices, clima, referências).';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_bronze}
  COMMENT 'Dados ingeridos como chegaram, com metadados de ingestão.';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_silver}
  COMMENT 'Dados limpos, tipados, extraídos dos documentos e cruzados com apólice e clima.';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_gold}
  COMMENT 'Sinistros analisados, fila de regulação, KPIs e metric views.';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_ml}
  COMMENT 'Modelos, prompts, features, gabarito e avaliações.';
CREATE SCHEMA IF NOT EXISTS ${catalogo}.${schema_operacional}
  COMMENT 'Histórico das tabelas operacionais do Lakebase (Lakehouse Sync).';
CREATE VOLUME IF NOT EXISTS ${catalogo}.${schema_landing}.arquivos
  COMMENT 'Arquivos brutos: avisos/, documentos/, apolices/, clima/, referencias/, historico/.';
CREATE VOLUME IF NOT EXISTS ${catalogo}.${schema_ml}.restrito
  COMMENT 'Gabarito dos dados sintéticos. Acesso restrito; nunca lido pelo pipeline de features.';
SHOW SCHEMAS IN ${catalogo};
```

- [ ] **Passo 6: aplicar.**

Comando: `set -a; source .env; set +a; uv run python scripts/executar_sql.py src/governanca/01_schemas_e_volumes.sql`
Esperado: 9 comandos executados, e o último lista os 6 schemas mais `information_schema`.

Em um workspace com permissão de CREATE CATALOG, rode antes `00_catalogo_opcional.sql`. No FEVM, use o catálogo criado com o workspace (D-016).

- [ ] **Passo 7: commit.**

```bash
git add pyproject.toml src/ambiente scripts/executar_sql.py src/governanca testes/test_config_ambiente.py testes/test_executar_sql.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: nomes de catálogo e schemas parametrizados, executor de SQL e criação dos schemas

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 0.4: Verificação dos recursos do workspace (spec, seção 12)

**Arquivos:**
- Criar: `scripts/verificar_recursos.py`, `testes/test_verificar_recursos.py`, `evidencias/00a-verificacoes-ambiente.md` (gerado)
- Modificar: `docs/decisoes-e-tradeoffs.md`

**Interfaces:**
- Consome: `executar_sql.executar`.
- Produz:
  - `Verificacao` (dataclass com `item`, `status` e `detalhe`);
  - `renderizar_markdown(verificacoes: list[Verificacao], quando: str) -> str`.

- [ ] **Passo 1: escrever o teste que falha** (`testes/test_verificar_recursos.py`):

```python
from verificar_recursos import Verificacao, renderizar_markdown


def test_renderiza_tabela_markdown():
    md = renderizar_markdown(
        [Verificacao("Modelos fundacionais", "ok", "databricks-claude-sonnet-x"),
         Verificacao("ABAC", "indisponivel", "erro de sintaxe")],
        quando="2026-11-20 10:00",
    )
    assert "# Verificações do ambiente" in md
    assert "| Modelos fundacionais | ✅ ok | databricks-claude-sonnet-x |" in md
    assert "| ABAC | ❌ indisponivel | erro de sintaxe |" in md
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_verificar_recursos.py -q`
Esperado: FALHA com `ModuleNotFoundError`

- [ ] **Passo 3: implementar** `scripts/verificar_recursos.py`:

```python
"""Verifica no workspace os recursos de que a spec depende (seção 12) e grava a evidência em Markdown.

Uso: uv run python scripts/verificar_recursos.py
"""
from __future__ import annotations

import io
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from databricks.sdk import WorkspaceClient

from ambiente import Ambiente, carregar_ambiente
from executar_sql import executar

ICONES = {"ok": "✅", "parcial": "⚠️", "indisponivel": "❌"}
RECURSOS_DAB = ["pipelines", "jobs", "apps", "model_serving_endpoints", "experiments", "registered_models",
                "postgres_projects", "postgres_synced_tables", "synced_database_tables", "database_instances",
                "genie_spaces", "dashboards", "volumes", "schemas"]


@dataclass
class Verificacao:
    item: str
    status: str  # ok | parcial | indisponivel
    detalhe: str


def renderizar_markdown(verificacoes: list[Verificacao], quando: str) -> str:
    linhas = ["# Verificações do ambiente", "", f"Executado em {quando} pelo script `scripts/verificar_recursos.py`.", "",
              "| Item | Status | Detalhe |", "|---|---|---|"]
    linhas += [f"| {v.item} | {ICONES.get(v.status, '')} {v.status} | {v.detalhe} |" for v in verificacoes]
    return "\n".join(linhas) + "\n"


def _pdf_teste() -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 750, "Orçamento de teste: Telha cerâmica colonial, 35 m², R$ 1.925,00")
    c.save()
    return buf.getvalue()


def checar_modelos(w) -> Verificacao:
    nomes = sorted(e.name for e in w.serving_endpoints.list() if "claude" in e.name and "sonnet" in e.name)
    return Verificacao("Modelo fundacional Claude Sonnet (parecer)", "ok" if nomes else "indisponivel", ", ".join(nomes) or "nenhum endpoint")


def checar_ai_parse_document(w, wh, amb: Ambiente) -> Verificacao:
    caminho = f"{amb.volume_arquivos}/_verificacao/teste.pdf"
    w.files.upload(caminho, io.BytesIO(_pdf_teste()), overwrite=True)
    try:
        _, linhas = executar(w, wh, f"SELECT CAST(ai_parse_document(content) AS STRING) FROM READ_FILES('{caminho}', format => 'binaryFile')")
        texto = linhas[0][0] if linhas else ""
        return Verificacao("ai_parse_document", "ok" if "Telha" in texto else "parcial", f"{len(texto)} caracteres extraídos")
    except RuntimeError as e:
        return Verificacao("ai_parse_document", "indisponivel", str(e).splitlines()[0][:200])


def checar_abac(w, wh, amb: Ambiente) -> Verificacao:
    try:
        executar(w, wh, f"SHOW POLICIES ON SCHEMA {amb.catalogo}.{amb.schema('landing')}")
        return Verificacao("Políticas ABAC", "ok", "SHOW POLICIES executou")
    except RuntimeError as e:
        return Verificacao("Políticas ABAC", "indisponivel", str(e).splitlines()[0][:200])


def checar_lakebase(w) -> Verificacao:
    try:
        n = len(list(w.postgres.list_projects()))
    except Exception as e:  # noqa: BLE001 - a evidência registra qualquer falha
        return Verificacao("Lakebase (postgres API)", "indisponivel", str(e)[:200])
    cdf = hasattr(w.postgres, "create_cdf_config")
    return Verificacao("Lakebase (postgres API) e Lakehouse Sync", "ok" if cdf else "parcial",
                       f"{n} projetos; API de CDF (Lakehouse Sync) {'presente' if cdf else 'ausente'} no SDK; ativação real na fase 6")


def checar_dab() -> Verificacao:
    saida = subprocess.run(["databricks", "bundle", "schema"], capture_output=True, text=True, check=True).stdout
    props = json.loads(saida)
    texto = json.dumps(props)
    presentes = [r for r in RECURSOS_DAB if f'"{r}"' in texto]
    ausentes = [r for r in RECURSOS_DAB if r not in presentes]
    return Verificacao("Recursos suportados pelo DAB", "ok", f"presentes: {', '.join(presentes)}; ausentes: {', '.join(ausentes) or 'nenhum'}")


def checar_warehouse(w, wh) -> Verificacao:
    x = w.warehouses.get(wh)
    return Verificacao("SQL Warehouse", "ok" if x.enable_serverless_compute else "parcial", f"{x.name} (serverless={x.enable_serverless_compute})")


def main() -> None:
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    wh = os.environ["FE_BAR_WAREHOUSE_ID"]
    amb = carregar_ambiente()
    verificacoes = [checar_warehouse(w, wh), checar_modelos(w), checar_ai_parse_document(w, wh, amb),
                    checar_abac(w, wh, amb), checar_lakebase(w), checar_dab()]
    md = renderizar_markdown(verificacoes, datetime.now().strftime("%Y-%m-%d %H:%M"))
    destino = Path("evidencias/00a-verificacoes-ambiente.md")
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
```

- [ ] **Passo 4: rodar o teste e ver passar.**

Comando: `uv run pytest testes/test_verificar_recursos.py -q`
Esperado: `1 passed`

- [ ] **Passo 5: executar as verificações no workspace.**

Comando: `set -a; source .env; set +a; uv run python scripts/verificar_recursos.py`
Esperado: a tabela impressa e gravada em `evidencias/00a-verificacoes-ambiente.md`.

- [ ] **Passo 6: registrar as decisões resultantes** em `docs/decisoes-e-tradeoffs.md`, como **D-016** (ou o próximo número livre), aplicando as regras da seção 12 da spec:
  - o modelo Claude Sonnet escolhido;
  - ABAC ou funções de máscara e filtro;
  - quais recursos vão no DAB e quais vão no `provisionar.py`;
  - se o `ai_parse_document` está funcionando.

  Mostrar o resumo ao usuário.

- [ ] **Passo 7: commit.**

```bash
git add scripts/verificar_recursos.py testes/test_verificar_recursos.py evidencias/00a-verificacoes-ambiente.md docs/decisoes-e-tradeoffs.md
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: verificação dos recursos do workspace e decisões resultantes

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 0.5: Esqueleto do bundle (DAB)

**Arquivos:**
- Criar: `databricks.yml`, `recursos/README.md`

**Interfaces:**
- Produz: o bundle `sinistros_clima`, com o target `dev` e as variáveis `catalogo`, `prefixo_schema` e `warehouse_id`, que os recursos das fases seguintes usam (nenhum recurso cita nome de catálogo ou schema fixo; D-016).

- [ ] **Passo 1: criar o `databricks.yml`:**

```yaml
bundle:
  name: sinistros_clima

include:
  - recursos/*.yml

variables:
  catalogo:
    description: Catálogo do Unity Catalog do projeto
    default: sinistros_clima
  prefixo_schema:
    description: Prefixo opcional dos schemas (vazio = sem prefixo)
    default: ""
  warehouse_id:
    description: ID do SQL Warehouse serverless

targets:
  dev:
    default: true
    workspace:
      profile: fe-bar
      root_path: /Workspace/Users/${workspace.current_user.userName}/.bundle/${bundle.name}/${bundle.target}
    variables:
      catalogo: fe_bar_sinistros_catalog  # catálogo criado pelo FEVM (D-016)
```

- [ ] **Passo 2: criar o `recursos/README.md`:**

```markdown
# Recursos do bundle

Um arquivo YAML por recurso (pipeline, jobs, app, endpoint, experimentos), incluídos por `databricks.yml`.
O que o DAB não suporta é criado por `scripts/provisionar.py` (veja D-013 e as verificações em `evidencias/00a-verificacoes-ambiente.md`).
```

- [ ] **Passo 3: validar.**

Comando: `databricks bundle validate -t dev --var warehouse_id=$FE_BAR_WAREHOUSE_ID`
Esperado: `Validation OK!`

- [ ] **Passo 4: commit.**

```bash
git add databricks.yml recursos/README.md
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "chore: esqueleto do bundle com target dev

Co-authored-by: Isaac <no-reply@databricks.com>"
```

- [ ] **Passo 5: fechar a fase 0.**
  - Atualizar o `README.md`, trocando a linha `Build` por `| Build: fase 0 (ambiente) | ✅ Concluída |` e mantendo as demais.
  - Atualizar a memória `fe-bar-caso-sinistros-climaticos.md` com a URL do workspace, o profile `fe-bar` e as decisões da tarefa 0.4.
  - Fazer o commit.

---

## FASE 1: DADOS

### Tarefa 1.1: Regras climáticas compartilhadas (`regras.clima`)

**Arquivos:**
- Criar: `src/regras/clima.py`, `testes/test_regras_clima.py`

**Interfaces:**
- Produz:
  - as constantes `LIMIAR_CHUVA_HORA_MM=10.0`, `LIMIAR_RAJADA_MS=15.0`, `LIMIAR_QUEDA_TEMP_C=4.0`, `LIMIAR_CHUVA_DIA_ALAGAMENTO_MM=50.0`, `RAIO_ESTACAO_KM=30.0`, `JANELA_DIAS=1` e `VARIAVEIS_POR_CAUSA`;
  - `haversine_km(lat1, lon1, lat2, lon2) -> float`;
  - `sinal_por_causa(causa: str, valores: dict[str, float | None]) -> bool | None`;
  - `classificar_evidencia(sinal_inmet: bool | None, distancia_km: float | None, registro_defesa_civil: bool) -> tuple[str, str]`, que devolve `(forca, fonte)` com `forca ∈ {forte, fraca, contraria}` e `fonte ∈ {inmet, defesa_civil, ambas, nenhuma}`;
  - `indexar_clima_por_data(clima_diario: pd.DataFrame) -> dict[date, pd.DataFrame]`;
  - `janela_clima(indice: dict, data: date) -> pd.DataFrame`;
  - `evidencia_inmet(lat, lon, causa, janela: pd.DataFrame, estacoes: pd.DataFrame) -> dict`, com as chaves `valores`, `estacoes`, `distancia_km` e `sinal`;
  - colunas esperadas de `clima_diario`: `codigo_estacao`, `data` (date), `chuva_mm`, `chuva_max_hora_mm`, `rajada_max_ms`, `queda_temp_max_c`, `granizo_provavel`;
  - colunas esperadas de `estacoes`: `codigo_estacao`, `nome`, `lat`, `lon`.

- [ ] **Passo 1: escrever os testes que falham** (`testes/test_regras_clima.py`):

```python
from datetime import date

import numpy as np
import pandas as pd
import pytest

from regras.clima import (
    classificar_evidencia, evidencia_inmet, haversine_km, indexar_clima_por_data, janela_clima, sinal_por_causa,
)


def test_haversine_florianopolis_chapeco_aprox_405km():
    assert haversine_km(-27.5954, -48.5480, -27.1004, -52.6152) == pytest.approx(405, abs=20)


@pytest.mark.parametrize("causa,valores,esperado", [
    ("vendaval", {"rajada_max_ms": 16.0}, True),
    ("vendaval", {"rajada_max_ms": 9.0}, False),
    ("vendaval", {"rajada_max_ms": None}, None),
    ("granizo", {"chuva_max_hora_mm": 12.0, "rajada_max_ms": 15.0}, True),
    ("granizo", {"chuva_max_hora_mm": 12.0, "rajada_max_ms": 10.0}, False),
    ("granizo", {"chuva_max_hora_mm": 12.0, "rajada_max_ms": None}, None),
    ("alagamento", {"chuva_mm": 55.0}, True),
    ("alagamento", {"chuva_mm": 20.0}, False),
    ("danos_eletricos", {"chuva_max_hora_mm": None, "rajada_max_ms": 20.0}, True),
    ("danos_eletricos", {"chuva_max_hora_mm": None, "rajada_max_ms": 5.0}, None),
    ("danos_eletricos", {"chuva_max_hora_mm": 1.0, "rajada_max_ms": 5.0}, False),
])
def test_sinal_por_causa(causa, valores, esperado):
    assert sinal_por_causa(causa, valores) is esperado


@pytest.mark.parametrize("sinal,dist,dc,esperado", [
    (True, 10.0, True, ("forte", "ambas")),
    (None, None, True, ("forte", "defesa_civil")),
    (False, 10.0, True, ("forte", "defesa_civil")),
    (True, 10.0, False, ("forte", "inmet")),
    (False, 10.0, False, ("contraria", "inmet")),
    (True, 45.0, False, ("fraca", "nenhuma")),
    (False, 45.0, False, ("fraca", "nenhuma")),
    (None, 10.0, False, ("fraca", "nenhuma")),
])
def test_classificar_evidencia(sinal, dist, dc, esperado):
    assert classificar_evidencia(sinal, dist, dc) == esperado


@pytest.fixture
def estacoes():
    return pd.DataFrame([
        {"codigo_estacao": "A001", "nome": "PERTO", "lat": -27.0, "lon": -52.0},
        {"codigo_estacao": "A002", "nome": "LONGE", "lat": -28.0, "lon": -50.0},
    ])


def _clima(linhas):
    base = {"chuva_mm": np.nan, "chuva_max_hora_mm": np.nan, "rajada_max_ms": np.nan, "queda_temp_max_c": np.nan, "granizo_provavel": pd.NA}
    return pd.DataFrame([{**base, **l} for l in linhas])


def test_evidencia_usa_estacao_valida_mais_proxima_por_variavel(estacoes):
    clima = _clima([
        {"codigo_estacao": "A001", "data": date(2026, 9, 28), "chuva_max_hora_mm": 14.0},  # A001 sem rajada
        {"codigo_estacao": "A002", "data": date(2026, 9, 28), "rajada_max_ms": 20.0, "chuva_max_hora_mm": 3.0},
    ])
    janela = janela_clima(indexar_clima_por_data(clima), date(2026, 9, 28))
    ev = evidencia_inmet(-27.05, -52.0, "granizo", janela, estacoes)
    assert ev["estacoes"] == {"chuva_max_hora_mm": "A001", "rajada_max_ms": "A002"}
    assert ev["valores"]["rajada_max_ms"] == 20.0


def test_variavel_fora_do_raio_e_fraca(estacoes):
    """Foco de revisão 2: a rajada só existe em uma estação a mais de 30 km; o resultado não pode ser 'contraria'."""
    clima = _clima([
        {"codigo_estacao": "A001", "data": date(2026, 9, 28), "chuva_max_hora_mm": 1.0},
        {"codigo_estacao": "A002", "data": date(2026, 9, 28), "rajada_max_ms": 5.0},
    ])
    janela = janela_clima(indexar_clima_por_data(clima), date(2026, 9, 28))
    ev = evidencia_inmet(-27.05, -52.0, "granizo", janela, estacoes)
    assert ev["sinal"] is None
    assert classificar_evidencia(ev["sinal"], ev["distancia_km"], False) == ("fraca", "nenhuma")


def test_janela_inclui_d_menos_1_e_d_mais_1(estacoes):
    clima = _clima([
        {"codigo_estacao": "A001", "data": date(2026, 9, 27), "rajada_max_ms": 18.0},
        {"codigo_estacao": "A001", "data": date(2026, 9, 30), "rajada_max_ms": 30.0},  # fora da janela
    ])
    janela = janela_clima(indexar_clima_por_data(clima), date(2026, 9, 28))
    ev = evidencia_inmet(-27.05, -52.0, "vendaval", janela, estacoes)
    assert ev["valores"]["rajada_max_ms"] == 18.0
    assert ev["sinal"] is True
    assert ev["distancia_km"] < 30
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_regras_clima.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'regras.clima'`

- [ ] **Passo 3: implementar** `src/regras/clima.py`:

```python
"""Regras climáticas compartilhadas pelo gerador sintético e pelo pipeline.

Valores de referência (calibráveis) definidos na spec, seção 4.3, e regra de duas fontes (D-015).
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd

LIMIAR_CHUVA_HORA_MM = 10.0
LIMIAR_RAJADA_MS = 15.0
LIMIAR_QUEDA_TEMP_C = 4.0
LIMIAR_CHUVA_DIA_ALAGAMENTO_MM = 50.0
RAIO_ESTACAO_KM = 30.0
JANELA_DIAS = 1  # D-1 a D+1

VARIAVEIS_POR_CAUSA: dict[str, tuple[str, ...]] = {
    "granizo": ("chuva_max_hora_mm", "rajada_max_ms"),
    "vendaval": ("rajada_max_ms",),
    "alagamento": ("chuva_mm",),
    "danos_eletricos": ("chuva_max_hora_mm", "rajada_max_ms"),
}


def _tem(valor) -> bool:
    return valor is not None and not (isinstance(valor, float) and math.isnan(valor)) and valor is not pd.NA


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def sinal_por_causa(causa: str, valores: dict[str, float | None]) -> bool | None:
    """True: há sinal compatível com a causa. False: há dado e não há sinal. None: falta dado."""
    chuva_dia = valores.get("chuva_mm")
    chuva_hora = valores.get("chuva_max_hora_mm")
    rajada = valores.get("rajada_max_ms")
    if causa == "vendaval":
        return None if not _tem(rajada) else bool(rajada >= LIMIAR_RAJADA_MS)
    if causa == "alagamento":
        return None if not _tem(chuva_dia) else bool(chuva_dia >= LIMIAR_CHUVA_DIA_ALAGAMENTO_MM)
    if causa == "granizo":
        # O INMET não mede granizo: usamos tempestade severa (chuva intensa e rajada forte) como indicador.
        if not (_tem(chuva_hora) and _tem(rajada)):
            return None
        return bool(chuva_hora >= LIMIAR_CHUVA_HORA_MM and rajada >= LIMIAR_RAJADA_MS)
    if causa == "danos_eletricos":
        medidos = [(v, lim) for v, lim in ((chuva_hora, LIMIAR_CHUVA_HORA_MM), (rajada, LIMIAR_RAJADA_MS)) if _tem(v)]
        if any(v >= lim for v, lim in medidos):
            return True
        return False if len(medidos) == 2 else None
    raise ValueError(f"causa desconhecida: {causa}")


def classificar_evidencia(sinal_inmet: bool | None, distancia_km: float | None, registro_defesa_civil: bool) -> tuple[str, str]:
    """Regra de duas fontes (D-015). Devolve (forca, fonte)."""
    perto = _tem(distancia_km) and distancia_km <= RAIO_ESTACAO_KM
    inmet_confirma = perto and sinal_inmet is True
    if registro_defesa_civil and inmet_confirma:
        return "forte", "ambas"
    if registro_defesa_civil:
        return "forte", "defesa_civil"
    if inmet_confirma:
        return "forte", "inmet"
    if perto and sinal_inmet is False:
        return "contraria", "inmet"
    return "fraca", "nenhuma"


def indexar_clima_por_data(clima_diario: pd.DataFrame) -> dict[date, pd.DataFrame]:
    return {d: g for d, g in clima_diario.groupby("data")}


def janela_clima(indice: dict[date, pd.DataFrame], data: date) -> pd.DataFrame:
    partes = [indice[d] for d in (data + timedelta(days=k) for k in range(-JANELA_DIAS, JANELA_DIAS + 1)) if d in indice]
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=["codigo_estacao", "data"])


def evidencia_inmet(lat: float, lon: float, causa: str, janela: pd.DataFrame, estacoes: pd.DataFrame) -> dict:
    """Para cada variável da causa, usa a estação VÁLIDA mais próxima na janela (máximo do período).

    Variáveis cuja estação válida mais próxima está a mais de RAIO_ESTACAO_KM contam como ausentes.
    `distancia_km` é a maior distância entre as variáveis dentro do raio; se nenhuma estiver no raio,
    é a menor distância encontrada (apenas para registro).
    """
    dist = {e.codigo_estacao: haversine_km(lat, lon, e.lat, e.lon) for e in estacoes.itertuples()}
    valores: dict[str, float | None] = {}
    usadas: dict[str, str] = {}
    for var in VARIAVEIS_POR_CAUSA[causa]:
        if var not in janela.columns:
            valores[var] = None
            continue
        por_estacao = janela.dropna(subset=[var]).groupby("codigo_estacao")[var].max()
        por_estacao = por_estacao[por_estacao.index.isin(list(dist))]
        if por_estacao.empty:
            valores[var] = None
            continue
        codigo = min(por_estacao.index, key=lambda c: dist[c])
        valores[var] = float(por_estacao[codigo])
        usadas[var] = codigo
    no_raio = {v: (valores[v] if v in usadas and dist[usadas[v]] <= RAIO_ESTACAO_KM else None) for v in valores}
    dist_no_raio = [dist[usadas[v]] for v in usadas if dist[usadas[v]] <= RAIO_ESTACAO_KM]
    todas = [dist[c] for c in usadas.values()]
    distancia = max(dist_no_raio) if dist_no_raio else (min(todas) if todas else None)
    return {"valores": valores, "estacoes": usadas, "distancia_km": distancia, "sinal": sinal_por_causa(causa, no_raio)}
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_regras_clima.py -q`
Esperado: todos os testes passam (23).

- [ ] **Passo 5: commit.**

```bash
git add src/regras/clima.py testes/test_regras_clima.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: regras climáticas e evidência de duas fontes (INMET + Defesa Civil)

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.2: Leitor do INMET e agregação diária

**Arquivos:**
- Criar: `src/dados_sinteticos/inmet.py`, `testes/test_inmet.py`

**Interfaces:**
- Consome: os limiares de `regras.clima`.
- Produz:
  - `ler_estacao_csv(texto: str) -> tuple[dict, pd.DataFrame]`, em que o dict tem `codigo_estacao`, `nome`, `uf`, `lat` e `lon`, e o DataFrame horário tem `codigo_estacao`, `data` (date), `hora_utc` (int), `chuva_mm`, `rajada_ms` e `temp_c`;
  - `ler_zip_uf(caminho_zip: Path, uf: str = "SC") -> tuple[pd.DataFrame, pd.DataFrame]`, que devolve (estações, horário);
  - `agregar_diario(horario: pd.DataFrame) -> pd.DataFrame`, com o formato de `clima_diario` da tarefa 1.1 mais `horas_chuva` e `horas_rajada`;
  - a constante `MIN_HORAS_VALIDAS = 12`.

- [ ] **Passo 1: escrever os testes que falham** (`testes/test_inmet.py`):

```python
import io
import zipfile
from datetime import date

import numpy as np

from dados_sinteticos.inmet import agregar_diario, ler_estacao_csv, ler_zip_uf

CAB = (
    "REGIAO:;S\nUF:;SC\nESTACAO:;TESTE\nCODIGO (WMO):;A999\nLATITUDE:;-27,10\nLONGITUDE:;-52,60\n"
    "ALTITUDE:;679\nDATA DE FUNDACAO:;01/01/08\n"
    "Data;Hora UTC;PRECIPITAÇÃO TOTAL, HORÁRIO (mm);PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB);"
    "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C);VENTO, RAJADA MAXIMA (m/s);\n"
)


def _csv(linhas):
    return CAB + "\n".join(f"{d};{h:02d}00 UTC;{p};900;{t};{r};" for d, h, p, t, r in linhas) + "\n"


def test_le_metadados_e_numeros_com_virgula():
    est, h = ler_estacao_csv(_csv([("2026/09/28", 0, ",2", "25,5", "10,4")]))
    assert est == {"codigo_estacao": "A999", "nome": "TESTE", "uf": "SC", "lat": -27.10, "lon": -52.60}
    assert h.loc[0, "data"] == date(2026, 9, 28)
    assert h.loc[0, "hora_utc"] == 0
    assert h.loc[0, "chuva_mm"] == 0.2 and h.loc[0, "temp_c"] == 25.5 and h.loc[0, "rajada_ms"] == 10.4


def test_valores_ausentes_viram_nan():
    """Foco de revisão 1: vazio e -9999 são ausência, não zero."""
    _, h = ler_estacao_csv(_csv([("2026/09/28", 0, "", "-9999", ""), ("2026/09/28", 1, "-9999", "", "-9999")]))
    assert h[["chuva_mm", "temp_c", "rajada_ms"]].isna().all().all()


def test_agregado_diario_respeita_minimo_de_horas_validas():
    linhas = [("2026/09/28", hh, "1,0", "20", "5") for hh in range(24)]          # dia completo
    linhas += [("2026/09/29", hh, "1,0" if hh < 5 else "", "20", "") for hh in range(24)]  # 5 h de chuva, sem rajada
    _, h = ler_estacao_csv(_csv(linhas))
    d = agregar_diario(h).set_index("data")
    assert d.loc[date(2026, 9, 28), "chuva_mm"] == 24.0
    assert d.loc[date(2026, 9, 28), "rajada_max_ms"] == 5.0
    assert np.isnan(d.loc[date(2026, 9, 29), "chuva_mm"])
    assert np.isnan(d.loc[date(2026, 9, 29), "rajada_max_ms"])


def test_granizo_provavel_exige_chuva_rajada_e_queda_de_temperatura():
    linhas = [("2026/09/28", hh, "0", "25", "5") for hh in range(24)]
    linhas[15] = ("2026/09/28", 15, "12,0", "25", "16")
    linhas[16] = ("2026/09/28", 16, "3,0", "20", "8")  # queda de 5 °C em 1 h
    _, h = ler_estacao_csv(_csv(linhas))
    d = agregar_diario(h)
    assert bool(d.loc[0, "granizo_provavel"]) is True
    assert d.loc[0, "chuva_max_hora_mm"] == 12.0


def test_le_somente_estacoes_da_uf_no_zip(tmp_path):
    caminho = tmp_path / "2026.zip"
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("INMET_S_SC_A999_TESTE_01-01-2026_A_31-10-2026.CSV", _csv([("2026/09/28", 0, "1", "20", "5")]).encode("latin-1"))
        z.writestr("INMET_S_RS_A801_PORTO ALEGRE_01-01-2026_A_31-10-2026.CSV", _csv([("2026/09/28", 0, "1", "20", "5")]).encode("latin-1"))
    est, h = ler_zip_uf(caminho, "SC")
    assert list(est["codigo_estacao"]) == ["A999"]
    assert len(h) == 1
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_inmet.py -q`
Esperado: FALHA com `ModuleNotFoundError`

- [ ] **Passo 3: implementar** `src/dados_sinteticos/inmet.py`:

```python
"""Leitura dos arquivos horários do INMET (estações automáticas) e agregação diária por estação.

Fonte: https://portal.inmet.gov.br/dadoshistoricos (um .zip por ano, um CSV por estação, latin-1, ';').
O formato tratado aqui é o de 2019 em diante (colunas 'Data' e 'Hora UTC').
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from regras.clima import LIMIAR_CHUVA_HORA_MM, LIMIAR_QUEDA_TEMP_C, LIMIAR_RAJADA_MS

MIN_HORAS_VALIDAS = 12
COL_CHUVA = "PRECIPITAÇÃO TOTAL, HORÁRIO (mm)"
COL_RAJADA = "VENTO, RAJADA MAXIMA (m/s)"
COL_TEMP = "TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)"


def _numero(serie: pd.Series) -> pd.Series:
    valores = pd.to_numeric(serie.str.strip().str.replace(",", ".", regex=False), errors="coerce")
    return valores.where(valores > -9000)


def ler_estacao_csv(texto: str) -> tuple[dict, pd.DataFrame]:
    linhas = texto.splitlines()
    meta = {}
    for linha in linhas[:8]:
        chave, _, valor = linha.partition(":;")
        meta[chave.strip().upper()] = valor.strip()
    inicio = next(i for i, l in enumerate(linhas) if l.startswith("Data;"))
    bruto = pd.read_csv(io.StringIO("\n".join(linhas[inicio:])), sep=";", dtype=str, keep_default_na=False)
    estacao = {
        "codigo_estacao": meta["CODIGO (WMO)"],
        "nome": meta["ESTACAO"],
        "uf": meta["UF"],
        "lat": float(meta["LATITUDE"].replace(",", ".")),
        "lon": float(meta["LONGITUDE"].replace(",", ".")),
    }
    horario = pd.DataFrame({
        "codigo_estacao": estacao["codigo_estacao"],
        "data": pd.to_datetime(bruto["Data"], format="%Y/%m/%d").dt.date,
        "hora_utc": bruto["Hora UTC"].str[:2].astype(int),
        "chuva_mm": _numero(bruto[COL_CHUVA]),
        "rajada_ms": _numero(bruto[COL_RAJADA]),
        "temp_c": _numero(bruto[COL_TEMP]),
    })
    return estacao, horario


def ler_zip_uf(caminho_zip: Path, uf: str = "SC") -> tuple[pd.DataFrame, pd.DataFrame]:
    estacoes, horarios = [], []
    with zipfile.ZipFile(caminho_zip) as z:
        for nome in sorted(z.namelist()):
            if f"_{uf}_" not in Path(nome).name:
                continue
            est, hor = ler_estacao_csv(z.read(nome).decode("latin-1"))
            estacoes.append(est)
            horarios.append(hor)
    return pd.DataFrame(estacoes), pd.concat(horarios, ignore_index=True)


def agregar_diario(horario: pd.DataFrame) -> pd.DataFrame:
    h = horario.sort_values(["codigo_estacao", "data", "hora_utc"]).reset_index(drop=True)
    temp = h.groupby("codigo_estacao")["temp_c"]
    minimo_2h = pd.concat([temp.shift(-1), temp.shift(-2)], axis=1).min(axis=1, skipna=True)
    h["queda_temp_2h_c"] = h["temp_c"] - minimo_2h
    completos = h[["chuva_mm", "rajada_ms", "queda_temp_2h_c"]].notna().all(axis=1)
    granizo = (h["chuva_mm"] >= LIMIAR_CHUVA_HORA_MM) & (h["rajada_ms"] >= LIMIAR_RAJADA_MS) & (h["queda_temp_2h_c"] >= LIMIAR_QUEDA_TEMP_C)
    h["granizo_hora"] = np.where(completos, granizo.astype(float), np.nan)
    d = h.groupby(["codigo_estacao", "data"]).agg(
        horas_chuva=("chuva_mm", "count"),
        chuva_mm=("chuva_mm", "sum"),
        chuva_max_hora_mm=("chuva_mm", "max"),
        horas_rajada=("rajada_ms", "count"),
        rajada_max_ms=("rajada_ms", "max"),
        queda_temp_max_c=("queda_temp_2h_c", "max"),
        granizo_horas=("granizo_hora", "sum"),
        granizo_validas=("granizo_hora", "count"),
    ).reset_index()
    d.loc[d["horas_chuva"] < MIN_HORAS_VALIDAS, ["chuva_mm", "chuva_max_hora_mm"]] = np.nan
    d.loc[d["horas_rajada"] < MIN_HORAS_VALIDAS, "rajada_max_ms"] = np.nan
    valido = d["granizo_validas"] >= MIN_HORAS_VALIDAS
    d["granizo_provavel"] = pd.Series(np.where(valido, d["granizo_horas"] > 0, None), dtype="boolean")
    colunas = ["codigo_estacao", "data", "horas_chuva", "chuva_mm", "chuva_max_hora_mm", "horas_rajada",
               "rajada_max_ms", "queda_temp_max_c", "granizo_provavel"]
    return d[colunas]
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_inmet.py -q`
Esperado: `5 passed`

- [ ] **Passo 5: commit.**

```bash
git add src/dados_sinteticos/inmet.py testes/test_inmet.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: leitor do INMET e agregação diária com indicador de granizo provável

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.3: Dados públicos curados e leitores (`publicos`)

**Arquivos:**
- Criar: `dados/publicos/defesa_civil_sc_2026.csv`, `dados/publicos/FONTES.md`, `src/dados_sinteticos/config.py`, `src/dados_sinteticos/publicos.py`, `testes/test_publicos.py`

**Interfaces:**
- Produz:
  - o módulo `config`, com as constantes usadas por todas as tarefas seguintes (o conteúdo está abaixo);
  - `carregar_municipios_sc(caminho) -> DataFrame[codigo_ibge:int, municipio, lat, lon]`;
  - `carregar_estacoes(caminho) -> DataFrame[codigo_estacao, nome, uf, lat, lon]`;
  - `carregar_clima_diario(caminho) -> DataFrame` (no formato `clima_diario`, com `data` como date);
  - `carregar_defesa_civil(caminho, municipios) -> DataFrame[episodio, data_inicio:date, data_fim:date, municipio, codigo_ibge, moradias_atingidas:Int64, fonte_url, peso]`, com `peso` somando 1;
  - `registro_defesa_civil(dc, codigo_ibge, data) -> bool`, que considera a janela D−1 a D+1 em volta de cada episódio.

- [ ] **Passo 1: criar** `dados/publicos/defesa_civil_sc_2026.csv` (os números e as fontes vêm de `docs/dados/defesa-civil-sc-2026.md`):

```csv
episodio,data_inicio,data_fim,municipio,moradias_atingidas,fonte_url
episodio_1,2026-08-28,2026-09-01,Florianópolis,3749,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Biguaçu,3255,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Ipuaçu,210,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,São José do Cedro,200,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Bom Jesus,81,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Entre Rios,80,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Princesa,58,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Mafra,50,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Campo Erê,35,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Quilombo,32,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Presidente Getúlio,30,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Lages,30,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Ouro Verde,23,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Peritiba,10,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_1,2026-08-28,2026-09-01,Ponte Alta,,https://www.jmlitoral.com.br/2026/09/01/dez-municipios-catarinenses-declaram-situacao-de-emergencia-decorrente-da-chuvas-intensas/
episodio_2,2026-09-27,2026-09-29,Seara,1344,https://omunicipio.com.br/clima/mais-de-duas-mil-casas-sao-danificadas-por-temporais-de-granizo-em-sc/
episodio_2,2026-09-27,2026-09-29,Ponte Serrada,192,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Santiago do Sul,180,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Anita Garibaldi,89,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,São Domingos,80,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Arabutã,76,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Ipumirim,45,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Vargem,30,https://omunicipio.com.br/clima/mais-de-duas-mil-casas-sao-danificadas-por-temporais-de-granizo-em-sc/
episodio_2,2026-09-27,2026-09-29,Formosa do Sul,27,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Brunópolis,10,https://omunicipio.com.br/clima/mais-de-duas-mil-casas-sao-danificadas-por-temporais-de-granizo-em-sc/
episodio_2,2026-09-27,2026-09-29,Faxinal dos Guedes,,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Itá,,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Novo Horizonte,,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Pinhalzinho,,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Quilombo,,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,União do Oeste,,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Vargeão,,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
episodio_2,2026-09-27,2026-09-29,Zortéa,,https://www.blogdoprisco.com.br/boletim-de-ocorrencias-defesa-civil-estadual/amp/
ocorrencia_agosto,2026-08-13,2026-08-14,Bela Vista do Toldo,42,https://www.defesacivil.sc.gov.br/2026/08/14/chuva-forte-deixa-danos-em-municipios-de-santa-catarina-e-risco-de-temporais-segue-alto-ate-sabado/
ocorrencia_agosto,2026-08-13,2026-08-14,Capinzal,5,https://www.defesacivil.sc.gov.br/2026/08/14/chuva-forte-deixa-danos-em-municipios-de-santa-catarina-e-risco-de-temporais-segue-alto-ate-sabado/
```

- [ ] **Passo 2: criar** `dados/publicos/FONTES.md`:

```markdown
# Fontes dos dados públicos

| Arquivo | Fonte | Como foi produzido |
|---|---|---|
| `municipios_sc.csv` | Compilação de dados do IBGE em https://github.com/kelvins/municipios-brasileiros (`csv/municipios.csv`) | `scripts/preparar_dados_publicos.py`: filtra `codigo_uf = 42` (SC) |
| `estacoes_inmet_sc.csv` | INMET, dados históricos das estações automáticas (https://portal.inmet.gov.br/dadoshistoricos, 2025.zip e 2026.zip) | Metadados do cabeçalho de cada CSV de estação de SC |
| `clima_sc_diario_2025.csv`, `clima_sc_diario_2026.csv` | INMET (mesmos arquivos) | `agregar_diario`: soma e máximo da chuva, rajada máxima, queda de temperatura e granizo provável; dias com menos de 12 h válidas ficam ausentes |
| `defesa_civil_sc_2026.csv` | Boletins da Defesa Civil de SC e imprensa (URL em cada linha) | Curadoria manual em 2026-11-20 (veja `docs/dados/defesa-civil-sc-2026.md`) |

Os arquivos horários completos do INMET (`dados/brutos/inmet_sc_horario_AAAA.csv`) não são versionados por causa do tamanho. Eles são recriados pelo script e enviados ao Volume `landing/arquivos/clima/`.
```

- [ ] **Passo 3: criar** `src/dados_sinteticos/config.py`:

```python
"""Parâmetros do gerador sintético. Valores de referência da spec (seção 4), calibráveis."""
from datetime import date

SEED = 20260920

# Volumes padrão (escala 1.0)
N_CORRETORES = 300
N_PRESTADORES = 2_000
N_SEGURADOS = 50_000
N_APOLICES = 60_000
N_HISTORICO = 20_000
N_AVISOS_EVENTO = 8_000
N_LOTES = 10

# Janelas
JANELA_EVENTO_2026 = (date(2026, 8, 1), date(2026, 9, 30))
JANELA_HISTORICO_2025 = (date(2025, 1, 1), date(2025, 12, 31))
INICIO_VIGENCIA_CARTEIRA = (date(2025, 10, 1), date(2026, 7, 31))  # todas vigentes durante o evento

# Coberturas
COBERTURAS = ("incendio", "vendaval_granizo", "danos_eletricos", "alagamento")
PROB_COBERTURA = {"incendio": 1.0, "vendaval_granizo": 0.85, "danos_eletricos": 0.70, "alagamento": 0.25}
LMI_FAIXAS = {"incendio": (150_000, 800_000), "vendaval_granizo": (30_000, 150_000),
              "danos_eletricos": (5_000, 30_000), "alagamento": (20_000, 80_000)}
FRANQUIAS = {"incendio": 0.0, "vendaval_granizo": 1_000.0, "danos_eletricos": 300.0, "alagamento": 1_500.0}
PREMIO_FAIXAS = {"residencial": (600.0, 2_400.0), "empresarial": (2_500.0, 9_000.0)}
CAUSA_COBERTURA = {"granizo": "vendaval_granizo", "vendaval": "vendaval_granizo",
                   "danos_eletricos": "danos_eletricos", "alagamento": "alagamento"}

# Causas e padrões
DIST_CAUSAS = {"granizo": 0.45, "vendaval": 0.30, "danos_eletricos": 0.17, "alagamento": 0.08}
DIST_CAUSAS_SEM_COBERTURA = {"alagamento": 0.50, "granizo": 0.25, "vendaval": 0.25}
CAUSAS_SEM_EVENTO = ("granizo", "vendaval")
DIST_PADROES = {
    "legitimo_simples": 0.60, "legitimo_complexo": 0.25, "sem_evento_climatico": 0.03,
    "orcamento_inflado": 0.04, "sem_cobertura": 0.03, "apolice_recente": 0.02,
    "dano_preexistente": 0.02, "prestador_concentrado": 0.01,
}
PRESTADORES_CONCENTRADOS = ("PR-0001", "PR-0002", "PR-0003")

# Valores
TETO_FAST_TRACK_RS = 5_000.0
COMPLEXO_MEDIANA_RS = 22_000.0
COMPLEXO_SIGMA = 0.6
COMPLEXO_MAX_RS = 140_000.0
LIMIAR_LAUDO_RS = 20_000.0
FATOR_PRECO_NORMAL = (0.90, 1.15)
FATOR_PRECO_INFLADO = (1.40, 2.20)

# Geografia
FRACAO_LEGITIMOS_DEFESA_CIVIL = 0.90
PESO_MINIMO_MUNICIPIO_DC = 20
FRACAO_CARTEIRA_UNIFORME = 0.40
FRACAO_HISTORICO_SEM_ESTACAO = 0.20
CANAIS = {"app": 0.50, "corretor": 0.35, "central": 0.15}
```

- [ ] **Passo 4: escrever os testes que falham** (`testes/test_publicos.py`):

```python
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from dados_sinteticos.publicos import carregar_defesa_civil, registro_defesa_civil

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def municipios():
    nomes = pd.read_csv(RAIZ / "dados/publicos/defesa_civil_sc_2026.csv")["municipio"].unique()
    return pd.DataFrame({"codigo_ibge": range(1, len(nomes) + 1), "municipio": nomes, "lat": -27.0, "lon": -50.0})


def test_defesa_civil_carrega_com_pesos_e_codigos(municipios):
    dc = carregar_defesa_civil(RAIZ / "dados/publicos/defesa_civil_sc_2026.csv", municipios)
    assert dc["peso"].sum() == pytest.approx(1.0)
    assert dc["codigo_ibge"].notna().all()
    seara = dc[dc["municipio"] == "Seara"].iloc[0]
    zortea = dc[dc["municipio"] == "Zortéa"].iloc[0]
    assert seara["peso"] > zortea["peso"] > 0  # sem número publicado recebe peso mínimo


def test_municipio_inexistente_falha(municipios):
    with pytest.raises(ValueError, match="não encontrados"):
        carregar_defesa_civil(RAIZ / "dados/publicos/defesa_civil_sc_2026.csv", municipios[municipios["municipio"] != "Seara"])


def test_registro_considera_janela_de_um_dia(municipios):
    dc = carregar_defesa_civil(RAIZ / "dados/publicos/defesa_civil_sc_2026.csv", municipios)
    seara = int(dc[dc["municipio"] == "Seara"]["codigo_ibge"].iloc[0])
    assert registro_defesa_civil(dc, seara, date(2026, 9, 26))      # D-1 do início
    assert registro_defesa_civil(dc, seara, date(2026, 9, 30))      # D+1 do fim
    assert not registro_defesa_civil(dc, seara, date(2026, 9, 25))
    assert not registro_defesa_civil(dc, seara, date(2026, 8, 29))  # Seara não está no episódio 1
```

- [ ] **Passo 5: rodar e ver falhar.**

Comando: `uv run pytest testes/test_publicos.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'dados_sinteticos.publicos'`

- [ ] **Passo 6: implementar** `src/dados_sinteticos/publicos.py`:

```python
"""Leitores dos dados públicos preparados em dados/publicos/."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from dados_sinteticos.config import PESO_MINIMO_MUNICIPIO_DC
from regras.clima import JANELA_DIAS


def carregar_municipios_sc(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    return df[["codigo_ibge", "municipio", "lat", "lon"]].astype({"codigo_ibge": int})


def carregar_estacoes(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, dtype={"codigo_estacao": str})


def carregar_clima_diario(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype={"codigo_estacao": str})
    df["data"] = pd.to_datetime(df["data"]).dt.date
    df["granizo_provavel"] = df["granizo_provavel"].astype("boolean")
    return df


def carregar_defesa_civil(caminho: Path, municipios: pd.DataFrame) -> pd.DataFrame:
    dc = pd.read_csv(caminho, dtype={"moradias_atingidas": "Int64"})
    dc["data_inicio"] = pd.to_datetime(dc["data_inicio"]).dt.date
    dc["data_fim"] = pd.to_datetime(dc["data_fim"]).dt.date
    dc = dc.merge(municipios[["municipio", "codigo_ibge", "lat", "lon"]], on="municipio", how="left")
    faltando = dc.loc[dc["codigo_ibge"].isna(), "municipio"].unique().tolist()
    if faltando:
        raise ValueError(f"municípios da Defesa Civil não encontrados na base do IBGE: {faltando}")
    dc["codigo_ibge"] = dc["codigo_ibge"].astype(int)
    bruto = dc["moradias_atingidas"].fillna(PESO_MINIMO_MUNICIPIO_DC).astype(float)
    dc["peso"] = bruto / bruto.sum()
    return dc


def registro_defesa_civil(dc: pd.DataFrame, codigo_ibge: int, data: date) -> bool:
    folga = timedelta(days=JANELA_DIAS)
    linhas = dc[dc["codigo_ibge"] == codigo_ibge]
    return bool(((linhas["data_inicio"] - folga <= data) & (data <= linhas["data_fim"] + folga)).any())
```

- [ ] **Passo 7: rodar e ver passar.**

Comando: `uv run pytest testes/test_publicos.py -q`
Esperado: `3 passed`

- [ ] **Passo 8: commit.**

```bash
git add dados/publicos/defesa_civil_sc_2026.csv dados/publicos/FONTES.md src/dados_sinteticos/config.py src/dados_sinteticos/publicos.py testes/test_publicos.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: dados curados da Defesa Civil, configuração do gerador e leitores públicos

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.4: Preparar os dados públicos (INMET e municípios)

**Arquivos:**
- Criar: `scripts/preparar_dados_publicos.py`
- Gerados e versionados: `dados/publicos/municipios_sc.csv`, `dados/publicos/estacoes_inmet_sc.csv`, `dados/publicos/clima_sc_diario_2025.csv`, `dados/publicos/clima_sc_diario_2026.csv`
- Gerados e **não** versionados: `dados/brutos/inmet_2025.zip`, `dados/brutos/inmet_2026.zip`, `dados/brutos/inmet_sc_horario_2025.csv`, `dados/brutos/inmet_sc_horario_2026.csv`

**Interfaces:**
- Consome: `inmet.ler_zip_uf` e `inmet.agregar_diario`.
- Produz: os arquivos acima, lidos pelos carregadores da tarefa 1.3.

- [ ] **Passo 1: implementar** `scripts/preparar_dados_publicos.py`:

```python
"""Baixa e prepara os dados públicos (INMET 2025/2026 de SC e municípios de SC).

Uso: uv run python scripts/preparar_dados_publicos.py
Saídas versionadas em dados/publicos/; arquivos grandes em dados/brutos/ (fora do git).
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import pandas as pd

from dados_sinteticos.inmet import agregar_diario, ler_zip_uf

RAIZ = Path(__file__).resolve().parents[1]
BRUTOS = RAIZ / "dados/brutos"
PUBLICOS = RAIZ / "dados/publicos"
URL_INMET = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
URL_MUNICIPIOS = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
ANOS = (2025, 2026)


def baixar(url: str, destino: Path) -> Path:
    if destino.exists():
        print(f"já existe: {destino.name}")
        return destino
    print(f"baixando {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r:
        destino.write_bytes(r.read())
    return destino


def main() -> None:
    BRUTOS.mkdir(parents=True, exist_ok=True)
    PUBLICOS.mkdir(parents=True, exist_ok=True)

    muni = pd.read_csv(baixar(URL_MUNICIPIOS, BRUTOS / "municipios_brasil.csv"))
    sc = muni[muni["codigo_uf"] == 42].rename(columns={"nome": "municipio", "latitude": "lat", "longitude": "lon"})
    sc[["codigo_ibge", "municipio", "lat", "lon"]].sort_values("municipio").to_csv(PUBLICOS / "municipios_sc.csv", index=False)
    print(f"municípios de SC: {len(sc)}")

    estacoes = []
    for ano in ANOS:
        est, horario = ler_zip_uf(baixar(URL_INMET.format(ano=ano), BRUTOS / f"inmet_{ano}.zip"), "SC")
        estacoes.append(est)
        horario.to_csv(BRUTOS / f"inmet_sc_horario_{ano}.csv", index=False)
        diario = agregar_diario(horario)
        diario.to_csv(PUBLICOS / f"clima_sc_diario_{ano}.csv", index=False)
        print(f"{ano}: {est.shape[0]} estações, {len(horario)} horas, {len(diario)} estação-dias")
    pd.concat(estacoes).drop_duplicates("codigo_estacao").sort_values("codigo_estacao").to_csv(PUBLICOS / "estacoes_inmet_sc.csv", index=False)


if __name__ == "__main__":
    main()
```

- [ ] **Passo 2: executar.**

Comando: `uv run python scripts/preparar_dados_publicos.py`
Esperado:
- `municípios de SC: 295`
- `2025: 24 estações, ...`
- `2026: 23 estações, ...`

- [ ] **Passo 3: conferir que o resultado reproduz a análise de `docs/dados/inmet-cobertura-sc.md`.**

Comando:

```bash
uv run python -c "
import pandas as pd
d = pd.read_csv('dados/publicos/clima_sc_diario_2026.csv', dtype={'codigo_estacao': str})
d = d[(d.data >= '2026-08-01') & (d.data <= '2026-09-30')]
print(d.groupby('codigo_estacao').agg(chuva=('chuva_mm', 'sum'), rajada=('rajada_max_ms', 'max')).loc[['A865', 'A868', 'A895', 'A898']])
"
```

Esperado (por estação):

| Estação | Chuva (mm) | Rajada máxima (m/s) |
|---|---|---|
| A865 | ~540 | 16,6 |
| A868 | ~454 | 14,6 |
| A895 | ~467 | 22,5 |
| A898 | ~523 | 27,6 |

Pequenas diferenças na chuva são esperadas, porque os dias com menos de 12 horas válidas viram ausência.

- [ ] **Passo 4: commit.**

```bash
git add scripts/preparar_dados_publicos.py dados/publicos/
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: preparação dos dados públicos (INMET 2025/2026 e municípios de SC)

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.5: Tabela de preços e prestadores

**Arquivos:**
- Criar: `src/dados_sinteticos/precos.py`, `testes/test_precos.py`

**Interfaces:**
- Produz: `gerar_tabela_precos() -> DataFrame[codigo_item, descricao, unidade, padrao, preco_referencia, causas]`, em que `causas` é uma string separada por `|` (ex.: `"granizo|vendaval"`). São 42 itens-base × 5 padrões = 210 linhas.

- [ ] **Passo 1: escrever o teste que falha** (`testes/test_precos.py`):

```python
from dados_sinteticos.precos import gerar_tabela_precos


def test_tabela_tem_210_itens_unicos_e_cobre_todas_as_causas():
    t = gerar_tabela_precos()
    assert len(t) == 210
    assert t["codigo_item"].is_unique
    for causa in ("granizo", "vendaval", "danos_eletricos", "alagamento"):
        assert t["causas"].str.split("|").apply(lambda cs: causa in cs).sum() >= 15
    assert (t["preco_referencia"] > 0).all()


def test_padrao_premium_mais_caro_que_economico():
    t = gerar_tabela_precos().set_index("codigo_item")
    assert t.loc["TEL-CER-PREMIUM", "preco_referencia"] > t.loc["TEL-CER-ECONOMICO", "preco_referencia"]
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_precos.py -q`
Esperado: FALHA com `ModuleNotFoundError`

- [ ] **Passo 3: implementar** `src/dados_sinteticos/precos.py`:

```python
"""Tabela de preços de referência de itens e serviços (inspirada no SINAPI; valores sintéticos)."""
from __future__ import annotations

import pandas as pd

TELHADO = "granizo|vendaval"
INTERNO = "granizo|vendaval|alagamento"
ELETRICO = "danos_eletricos"
ALAGAMENTO = "alagamento"

# (código, descrição, unidade, preço base em R$, causas)
ITENS_BASE = [
    ("TEL-FIB", "Telha de fibrocimento 6 mm", "m²", 38.0, TELHADO),
    ("TEL-CER", "Telha cerâmica colonial", "m²", 55.0, TELHADO),
    ("TEL-CON", "Telha de concreto", "m²", 62.0, TELHADO),
    ("TEL-MET", "Telha metálica trapezoidal", "m²", 85.0, TELHADO),
    ("TEL-POL", "Telha de policarbonato", "m²", 120.0, TELHADO),
    ("CUM", "Cumeeira", "m", 45.0, TELHADO),
    ("CAL", "Calha de chapa galvanizada", "m", 70.0, TELHADO),
    ("RUF", "Rufo de chapa galvanizada", "m", 48.0, TELHADO),
    ("MAD", "Madeiramento de telhado (reposição)", "m²", 95.0, TELHADO),
    ("MO-TEL", "Mão de obra de retelhamento", "m²", 42.0, TELHADO),
    ("LONA", "Lona de cobertura emergencial", "m²", 9.0, TELHADO),
    ("FORRO-PVC", "Forro de PVC", "m²", 58.0, INTERNO),
    ("FORRO-GES", "Forro de gesso", "m²", 75.0, INTERNO),
    ("VID-COM", "Vidro comum 4 mm", "m²", 110.0, TELHADO),
    ("VID-TEM", "Vidro temperado 8 mm", "m²", 290.0, TELHADO),
    ("JAN", "Janela de alumínio", "un", 780.0, TELHADO),
    ("PORTAO", "Portão metálico basculante", "un", 2900.0, TELHADO),
    ("TOLDO", "Toldo ou cobertura de garagem", "m²", 260.0, TELHADO),
    ("MURO", "Reconstrução de muro de alvenaria", "m²", 180.0, TELHADO),
    ("ANT", "Antena e suporte", "un", 350.0, TELHADO),
    ("PLACA", "Placa solar fotovoltaica (módulo)", "un", 1100.0, TELHADO),
    ("AQ-SOL", "Coletor de aquecedor solar", "un", 1500.0, TELHADO),
    ("CX-AGUA", "Caixa d'água 1.000 L", "un", 680.0, TELHADO),
    ("PINT-EXT", "Pintura externa", "m²", 32.0, TELHADO),
    ("GEL", "Geladeira duplex", "un", 3800.0, ELETRICO),
    ("TV", "Televisor 50 polegadas", "un", 2900.0, ELETRICO),
    ("MAQ", "Máquina de lavar roupas", "un", 2600.0, ELETRICO),
    ("MIC", "Micro-ondas", "un", 750.0, ELETRICO),
    ("COMP", "Computador desktop", "un", 3500.0, ELETRICO),
    ("AR", "Ar-condicionado split 12.000 BTU", "un", 2700.0, ELETRICO),
    ("MOTOR-PORT", "Motor de portão eletrônico", "un", 1300.0, ELETRICO),
    ("BOMBA", "Bomba d'água", "un", 900.0, ELETRICO),
    ("ROT", "Roteador e modem", "un", 420.0, ELETRICO),
    ("QUADRO", "Reparo de quadro elétrico", "un", 650.0, ELETRICO),
    ("FIA", "Reparo de fiação elétrica", "m", 28.0, ELETRICO),
    ("PISO", "Piso cerâmico (reposição)", "m²", 85.0, ALAGAMENTO),
    ("SOFA", "Sofá 3 lugares", "un", 2400.0, ALAGAMENTO),
    ("COLCHAO", "Colchão de casal", "un", 1600.0, ALAGAMENTO),
    ("ARM", "Armário de cozinha", "un", 1900.0, ALAGAMENTO),
    ("LIMP", "Limpeza e higienização pós-alagamento", "m²", 18.0, ALAGAMENTO),
    ("PINT-INT", "Pintura interna", "m²", 26.0, ALAGAMENTO),
    ("PORTA", "Porta de madeira interna", "un", 520.0, ALAGAMENTO),
]
PADROES = {"ECONOMICO": 0.65, "POPULAR": 0.80, "MEDIO": 1.00, "SUPERIOR": 1.25, "PREMIUM": 1.60}


def gerar_tabela_precos() -> pd.DataFrame:
    linhas = [
        {"codigo_item": f"{cod}-{padrao}", "descricao": f"{desc} (padrão {padrao.lower()})", "unidade": un,
         "padrao": padrao.lower(), "preco_referencia": round(preco * fator, 2), "causas": causas}
        for cod, desc, un, preco, causas in ITENS_BASE
        for padrao, fator in PADROES.items()
    ]
    return pd.DataFrame(linhas)
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_precos.py -q`
Esperado: `2 passed`

- [ ] **Passo 5: commit.**

```bash
git add src/dados_sinteticos/precos.py testes/test_precos.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: tabela de preços de referência (210 itens)

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.6: Cadastros (corretores, prestadores, segurados, apólices)

**Arquivos:**
- Criar: `src/dados_sinteticos/cadastros.py`, `testes/test_cadastros.py`

**Interfaces:**
- Consome: `config`.
- Produz:
  - `nova_faker(seed: int) -> Faker`;
  - `gerar_corretores(fk, n) -> DataFrame[id_corretor, nome, registro_susep]`;
  - `gerar_prestadores(fk, n) -> DataFrame[id_prestador, razao_social, cnpj]`;
  - `pesos_carteira(municipios, defesa_civil, fracao_uniforme) -> pd.Series`, indexada por `codigo_ibge` e somando 1;
  - `criar_segurado_avulso(fk, rng, id_segurado, mun, codigo_ibge) -> dict`, com `id_segurado`, `cpf`, `nome`, `telefone`, `email`, `logradouro`, `municipio`, `codigo_ibge`, `uf`, `lat` e `lon`;
  - `gerar_segurados(fk, rng, municipios, pesos, n) -> DataFrame`;
  - `sortear_lmi_franquia(rng, cobertura, ramo) -> tuple[float, float]`;
  - `criar_apolice_avulsa(rng, segurado, id_apolice, inicio, corretores, ramo="residencial", forcar=frozenset(), excluir=frozenset()) -> tuple[dict, list[dict]]`. A apólice tem `id_apolice`, `id_segurado`, `id_corretor`, `ramo`, `codigo_ibge`, `municipio`, `lat`, `lon`, `inicio_vigencia` (ISO), `fim_vigencia` (ISO) e `premio_anual`. Cada cobertura tem `id_apolice`, `cobertura`, `lmi` e `franquia`;
  - `gerar_apolices(rng, segurados, corretores, n, inicio_min, inicio_max) -> tuple[DataFrame, DataFrame]`.

- [ ] **Passo 1: escrever os testes que falham** (`testes/test_cadastros.py`):

```python
from datetime import date

import numpy as np
import pandas as pd
import pytest

from dados_sinteticos import config
from dados_sinteticos.cadastros import (
    criar_apolice_avulsa, gerar_apolices, gerar_corretores, gerar_segurados, nova_faker, pesos_carteira,
)


def _cpf_valido(cpf: str) -> bool:
    d = [int(c) for c in cpf if c.isdigit()]
    if len(d) != 11:
        return False
    for n in (9, 10):
        soma = sum(d[i] * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != d[n]:
            return False
    return True


@pytest.fixture
def base():
    rng = np.random.default_rng(1)
    fk = nova_faker(1)
    municipios = pd.DataFrame({"codigo_ibge": [1, 2], "municipio": ["A", "B"], "lat": [-27.0, -26.0], "lon": [-52.0, -49.0]})
    dc = pd.DataFrame({"codigo_ibge": [2], "peso": [1.0]})
    return rng, fk, municipios, dc


def test_pesos_carteira_somam_1_e_concentram_na_defesa_civil(base):
    _, _, municipios, dc = base
    p = pesos_carteira(municipios, dc, 0.4)
    assert p.sum() == pytest.approx(1.0)
    assert p.loc[2] == pytest.approx(0.2 + 0.6)


def test_segurados_tem_cpf_valido_e_municipio(base):
    rng, fk, municipios, dc = base
    s = gerar_segurados(fk, rng, municipios, pesos_carteira(municipios, dc, 0.4), 200)
    assert len(s) == 200 and s["id_segurado"].is_unique
    assert s["cpf"].map(_cpf_valido).all()
    assert set(s["codigo_ibge"]) <= {1, 2}


def test_apolices_vigencia_um_ano_e_incendio_sempre(base):
    rng, fk, municipios, dc = base
    s = gerar_segurados(fk, rng, municipios, pesos_carteira(municipios, dc, 0.4), 100)
    ap, cob = gerar_apolices(rng, s, gerar_corretores(fk, 5), 120, date(2025, 10, 1), date(2026, 7, 31))
    assert len(ap) == 120 and ap["id_apolice"].is_unique
    assert (ap["ramo"] == "empresarial").sum() == 20
    dias = (pd.to_datetime(ap["fim_vigencia"]) - pd.to_datetime(ap["inicio_vigencia"])).dt.days
    assert (dias == 365).all()
    assert set(cob.loc[cob["cobertura"] == "incendio", "id_apolice"]) == set(ap["id_apolice"])


def test_apolice_avulsa_forca_e_exclui_coberturas(base):
    rng, fk, municipios, _ = base
    seg = {"id_segurado": "SG-1", "codigo_ibge": 1, "municipio": "A", "lat": -27.0, "lon": -52.0}
    ap, cobs = criar_apolice_avulsa(rng, seg, "AP-X", date(2026, 9, 20), gerar_corretores(fk, 2),
                                    forcar=frozenset({"incendio", "alagamento"}), excluir=frozenset({"vendaval_granizo"}))
    tipos = {c["cobertura"] for c in cobs}
    assert {"incendio", "alagamento"} <= tipos and "vendaval_granizo" not in tipos
    assert ap["inicio_vigencia"] == "2026-09-20" and ap["fim_vigencia"] == "2027-09-20"
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_cadastros.py -q`
Esperado: FALHA com `ModuleNotFoundError`

- [ ] **Passo 3: implementar** `src/dados_sinteticos/cadastros.py`:

```python
"""Cadastros sintéticos: corretores, prestadores, segurados e apólices (com coberturas)."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from dados_sinteticos import config


def nova_faker(seed: int) -> Faker:
    fk = Faker("pt_BR")
    fk.seed_instance(seed)
    return fk


def gerar_corretores(fk: Faker, n: int) -> pd.DataFrame:
    return pd.DataFrame([{"id_corretor": f"CR-{i:04d}", "nome": fk.name(),
                          "registro_susep": str(fk.random_number(digits=9, fix_len=True))} for i in range(1, n + 1)])


def gerar_prestadores(fk: Faker, n: int) -> pd.DataFrame:
    return pd.DataFrame([{"id_prestador": f"PR-{i:04d}", "razao_social": fk.company(), "cnpj": fk.cnpj()}
                         for i in range(1, n + 1)])


def pesos_carteira(municipios: pd.DataFrame, defesa_civil: pd.DataFrame, fracao_uniforme: float) -> pd.Series:
    base = pd.Series(fracao_uniforme / len(municipios), index=municipios["codigo_ibge"].to_numpy())
    dc = defesa_civil.groupby("codigo_ibge")["peso"].sum()
    dc = dc / dc.sum() * (1 - fracao_uniforme)
    return base.add(dc, fill_value=0.0)


def criar_segurado_avulso(fk: Faker, rng: np.random.Generator, id_segurado: str, mun, codigo_ibge: int) -> dict:
    return {
        "id_segurado": id_segurado, "cpf": fk.cpf(), "nome": fk.name(), "telefone": fk.cellphone_number(),
        "email": fk.free_email(), "logradouro": fk.street_address(), "municipio": mun["municipio"],
        "codigo_ibge": int(codigo_ibge), "uf": "SC",
        "lat": round(float(mun["lat"]) + float(rng.normal(0, 0.01)), 5),
        "lon": round(float(mun["lon"]) + float(rng.normal(0, 0.01)), 5),
    }


def gerar_segurados(fk: Faker, rng: np.random.Generator, municipios: pd.DataFrame, pesos: pd.Series, n: int) -> pd.DataFrame:
    mun = municipios.set_index("codigo_ibge")
    codigos = rng.choice(pesos.index.to_numpy(), size=n, p=(pesos / pesos.sum()).to_numpy())
    return pd.DataFrame([criar_segurado_avulso(fk, rng, f"SG-{i:06d}", mun.loc[c], c) for i, c in enumerate(codigos, start=1)])


def sortear_lmi_franquia(rng: np.random.Generator, cobertura: str, ramo: str) -> tuple[float, float]:
    lo, hi = config.LMI_FAIXAS[cobertura]
    fator = 3 if ramo == "empresarial" else 1
    lmi = float(round(float(rng.uniform(lo, hi)) * fator, -3))
    franquia = config.FRANQUIAS[cobertura] * (2 if ramo == "empresarial" else 1)
    return lmi, float(franquia)


def criar_apolice_avulsa(rng: np.random.Generator, segurado, id_apolice: str, inicio: date, corretores: pd.DataFrame,
                         ramo: str = "residencial", forcar: frozenset = frozenset(), excluir: frozenset = frozenset()) -> tuple[dict, list[dict]]:
    coberturas = []
    for cobertura, prob in config.PROB_COBERTURA.items():
        if cobertura in excluir:
            continue
        if cobertura in forcar or rng.random() < prob:
            lmi, franquia = sortear_lmi_franquia(rng, cobertura, ramo)
            coberturas.append({"id_apolice": id_apolice, "cobertura": cobertura, "lmi": lmi, "franquia": franquia})
    apolice = {
        "id_apolice": id_apolice, "id_segurado": segurado["id_segurado"],
        "id_corretor": corretores["id_corretor"].iloc[int(rng.integers(0, len(corretores)))], "ramo": ramo,
        "codigo_ibge": int(segurado["codigo_ibge"]), "municipio": segurado["municipio"],
        "lat": float(segurado["lat"]), "lon": float(segurado["lon"]),
        "inicio_vigencia": inicio.isoformat(), "fim_vigencia": (inicio + timedelta(days=365)).isoformat(),
        "premio_anual": round(float(rng.uniform(*config.PREMIO_FAIXAS[ramo])), 2),
    }
    return apolice, coberturas


def gerar_apolices(rng: np.random.Generator, segurados: pd.DataFrame, corretores: pd.DataFrame, n: int,
                   inicio_min: date, inicio_max: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """As primeiras len(segurados) apólices são residenciais (uma por segurado); o restante é empresarial."""
    apolices, coberturas = [], []
    dias = (inicio_max - inicio_min).days
    for i in range(1, n + 1):
        if i <= len(segurados):
            segurado, ramo = segurados.iloc[i - 1], "residencial"
        else:
            segurado, ramo = segurados.iloc[int(rng.integers(0, len(segurados)))], "empresarial"
        inicio = inicio_min + timedelta(days=int(rng.integers(0, dias + 1)))
        ap, cob = criar_apolice_avulsa(rng, segurado, f"AP-{i:07d}", inicio, corretores, ramo=ramo)
        apolices.append(ap)
        coberturas.extend(cob)
    return pd.DataFrame(apolices), pd.DataFrame(coberturas)
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_cadastros.py -q`
Esperado: `4 passed`

- [ ] **Passo 5: commit.**

```bash
git add src/dados_sinteticos/cadastros.py testes/test_cadastros.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: cadastros sintéticos de corretores, prestadores, segurados e apólices

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.7: Textos e PDFs (orçamentos e laudos)

**Arquivos:**
- Criar: `src/dados_sinteticos/documentos.py`, `testes/test_documentos.py`

**Interfaces:**
- Produz:
  - `moeda(valor: float) -> str`, que devolve `"R$ 1.925,00"`;
  - `descrever(rng, causa) -> str`;
  - `texto_laudo(rng, causa, data_vistoria: date, itens: list[dict], padrao: str) -> str`;
  - `gerar_orcamento_pdf(caminho: Path, rng, aviso: dict, itens: list[dict], prestador: dict, nome_segurado: str) -> None`. O `aviso` usa as chaves `id_aviso`, `municipio` e `data_aviso` (ISO); o `prestador` usa `razao_social` e `cnpj`;
  - `gerar_laudo_pdf(caminho: Path, aviso: dict, texto: str) -> None`.
- Cada item é um dict com `seq`, `codigo_item`, `descricao`, `unidade`, `quantidade`, `valor_unitario`, `valor_total`, `preco_referencia` e `preexistente`.

- [ ] **Passo 1: escrever os testes que falham** (`testes/test_documentos.py`):

```python
from datetime import date

import numpy as np
from pypdf import PdfReader

from dados_sinteticos.documentos import gerar_laudo_pdf, gerar_orcamento_pdf, moeda, texto_laudo

ITENS = [
    {"seq": 1, "codigo_item": "TEL-CER-MEDIO", "descricao": "Telha cerâmica colonial (padrão médio)", "unidade": "m²",
     "quantidade": 35, "valor_unitario": 55.0, "valor_total": 1925.0, "preco_referencia": 55.0, "preexistente": False},
    {"seq": 2, "codigo_item": "CAL-MEDIO", "descricao": "Calha de chapa galvanizada (padrão médio)", "unidade": "m",
     "quantidade": 10, "valor_unitario": 70.0, "valor_total": 700.0, "preco_referencia": 70.0, "preexistente": True},
]
AVISO = {"id_aviso": "AV-2026-000001", "municipio": "Seara", "data_aviso": "2026-09-29"}


def _texto(caminho):
    return "\n".join(p.extract_text() for p in PdfReader(caminho).pages)


def test_moeda_formato_brasileiro():
    assert moeda(1925) == "R$ 1.925,00"
    assert moeda(0.5) == "R$ 0,50"


def test_pdf_orcamento_texto_extraivel(tmp_path):
    """Foco de revisão 4: acentos e valores em formato brasileiro sobrevivem à extração."""
    for semente in (1, 2):  # os dois layouts
        caminho = tmp_path / f"orc_{semente}.pdf"
        gerar_orcamento_pdf(caminho, np.random.default_rng(semente), AVISO, ITENS,
                            {"razao_social": "Telhados São João Ltda.", "cnpj": "12.345.678/0001-90"}, "Maria da Conceição")
        texto = _texto(caminho)
        assert "Orçamento" in texto and "Telha cerâmica colonial" in texto
        assert "R$ 2.625,00" in texto  # total
        assert "Conceição" in texto


def test_laudo_preexistente_menciona_dano_anterior(tmp_path):
    texto = texto_laudo(np.random.default_rng(3), "granizo", date(2026, 10, 2), ITENS, "dano_preexistente")
    assert "anterior ao evento" in texto and "Calha" in texto
    caminho = tmp_path / "laudo.pdf"
    gerar_laudo_pdf(caminho, AVISO, texto)
    assert "anterior ao evento" in _texto(caminho)


def test_laudo_regular_nao_menciona_dano_anterior():
    texto = texto_laudo(np.random.default_rng(3), "vendaval", date(2026, 10, 2), ITENS, "legitimo_complexo")
    assert "Não foram observados indícios de danos anteriores" in texto
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_documentos.py -q`
Esperado: FALHA com `ModuleNotFoundError`

- [ ] **Passo 3: implementar** `src/dados_sinteticos/documentos.py`:

```python
"""Textos livres (descrições e laudos) e PDFs de orçamento e laudo de vistoria."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

DESCRICOES = {
    "granizo": ["A chuva de granizo quebrou várias telhas e entrou água na {comodo}.",
                "Pedras de granizo danificaram o telhado e a calha; houve goteiras na {comodo}.",
                "O granizo quebrou o vidro da janela da {comodo} e parte da cobertura da garagem."],
    "vendaval": ["O vento forte arrancou parte do telhado e derrubou o muro dos fundos.",
                 "Durante o temporal, o vendaval levou telhas e danificou o portão da garagem.",
                 "A ventania destelhou a casa e a água estragou o forro da {comodo}."],
    "danos_eletricos": ["Depois da queda de energia no temporal, a {aparelho} não ligou mais.",
                        "Um raio caiu perto de casa e queimou a {aparelho} e o roteador.",
                        "Com a oscilação de energia durante a tempestade, a {aparelho} queimou."],
    "alagamento": ["A água da chuva invadiu a casa e chegou a {altura} cm, estragando móveis.",
                   "A rua alagou e a água entrou na {comodo}, danificando o piso e o sofá.",
                   "Com a chuva forte, a casa foi alagada e perdemos móveis da {comodo}."],
}
COMODOS = ["sala", "cozinha", "garagem", "quarto", "lavanderia"]
APARELHOS = ["geladeira", "televisão", "máquina de lavar", "computador", "bomba d'água"]
CAUSA_TEXTO = {"granizo": "chuva de granizo", "vendaval": "vendaval", "danos_eletricos": "descarga elétrica",
               "alagamento": "alagamento"}
SINAIS_PREEXISTENTES = ["oxidação antiga", "infiltração antiga com bolor", "desgaste e remendos antigos",
                        "fissuras antigas na alvenaria"]


def moeda(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _escolha(rng: np.random.Generator, opcoes: list[str]) -> str:
    return opcoes[int(rng.integers(0, len(opcoes)))]


def descrever(rng: np.random.Generator, causa: str) -> str:
    return _escolha(rng, DESCRICOES[causa]).format(comodo=_escolha(rng, COMODOS), aparelho=_escolha(rng, APARELHOS),
                                                   altura=int(rng.integers(20, 90)))


def texto_laudo(rng: np.random.Generator, causa: str, data_vistoria: date, itens: list[dict], padrao: str) -> str:
    abertura = f"Vistoria realizada em {data_vistoria.strftime('%d/%m/%Y')}."
    if padrao == "dano_preexistente":
        nomes = ", ".join(i["descricao"].split(" (")[0] for i in itens if i["preexistente"])
        return (f"{abertura} Parte dos danos é compatível com {CAUSA_TEXTO[causa]}. Entretanto, observa-se "
                f"{_escolha(rng, SINAIS_PREEXISTENTES)} nos seguintes itens: {nomes}, indicando dano anterior ao evento.")
    return (f"{abertura} Os danos observados são compatíveis com {CAUSA_TEXTO[causa]} ocorrido na data informada. "
            "Não foram observados indícios de danos anteriores.")


def gerar_orcamento_pdf(caminho: Path, rng: np.random.Generator, aviso: dict, itens: list[dict], prestador: dict,
                        nome_segurado: str) -> None:
    estilos = getSampleStyleSheet()
    total = sum(i["valor_total"] for i in itens)
    data = date.fromisoformat(aviso["data_aviso"]).strftime("%d/%m/%Y")
    partes = [Paragraph(f"<b>{prestador['razao_social']}</b> CNPJ {prestador['cnpj']}", estilos["Normal"]),
              Paragraph("Orçamento de reparos", estilos["Title"]),
              Paragraph(f"Cliente: {nome_segurado} | Local: {aviso['municipio']}/SC | Data: {data}", estilos["Normal"]),
              Spacer(1, 12)]
    if rng.random() < 0.5:  # layout 1: tabela
        linhas = [["Item", "Descrição", "Qtd.", "Un.", "Valor unit.", "Total"]]
        linhas += [[str(i["seq"]), i["descricao"], str(i["quantidade"]), i["unidade"], moeda(i["valor_unitario"]),
                    moeda(i["valor_total"])] for i in itens]
        partes.append(Table(linhas))
    else:  # layout 2: texto corrido
        for i in itens:
            partes.append(Paragraph(f"{i['seq']}) {i['quantidade']} {i['unidade']} de {i['descricao']} a "
                                    f"{moeda(i['valor_unitario'])} = {moeda(i['valor_total'])}", estilos["Normal"]))
    partes += [Spacer(1, 12), Paragraph(f"<b>Total do orçamento: {moeda(total)}</b>", estilos["Normal"]),
               Paragraph("Validade: 15 dias. Pagamento a combinar.", estilos["Normal"])]
    SimpleDocTemplate(str(caminho), pagesize=A4, title=f"Orçamento {aviso['id_aviso']}").build(partes)


def gerar_laudo_pdf(caminho: Path, aviso: dict, texto: str) -> None:
    estilos = getSampleStyleSheet()
    partes = [Paragraph("Laudo de vistoria", estilos["Title"]),
              Paragraph(f"Aviso {aviso['id_aviso']} | Local: {aviso['municipio']}/SC", estilos["Normal"]),
              Spacer(1, 12), Paragraph(texto, estilos["Normal"])]
    SimpleDocTemplate(str(caminho), pagesize=A4, title=f"Laudo {aviso['id_aviso']}").build(partes)
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_documentos.py -q`
Esperado: `4 passed`. Se a extração de "Orçamento" falhar no layout de tabela por quebra de célula, ajuste `colWidths` da `Table` para `[30, 220, 40, 30, 80, 80]` e rode de novo.

- [ ] **Passo 5: commit.**

```bash
git add src/dados_sinteticos/documentos.py testes/test_documentos.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: textos livres e PDFs de orçamento e laudo

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.8: Gerador de sinistros (histórico 2025 e evento 2026)

**Arquivos:**
- Criar: `src/dados_sinteticos/sinistros.py`, `testes/conftest.py`, `testes/test_sinistros.py`

**Interfaces:**
- Consome: `regras.clima` (tarefa 1.1), `publicos.registro_defesa_civil` (1.3), `precos.gerar_tabela_precos` (1.5), `cadastros.*` (1.6), `documentos.descrever` e `documentos.texto_laudo` (1.7), `config`.
- Produz:
  - `ContextoGeracao(rng, fk, municipios, estacoes, clima_diario, precos, prestadores, janela, defesa_civil=None)`, com o método `evidencia(codigo_ibge, lat, lon, data, causa) -> tuple[str, str]`;
  - `sortear_padroes(rng, n) -> list[str]`;
  - `gerar_itens(rng, causa, alvo_rs, precos, fator_preco=config.FATOR_PRECO_NORMAL, min_itens=1) -> list[dict]`;
  - `gabarito(padrao, itens, franquia, lmi) -> tuple[str, float, str]`, que devolve `(decisao_esperada, valor_devido, motivo)`;
  - `ResultadoEvento(avisos, itens, gabarito, apolices_extra, coberturas_extra, segurados_extra)`. Colunas:
    - **avisos:** `id_aviso`, `id_apolice`, `cpf_segurado`, `data_ocorrencia`, `data_aviso` (ISO), `causa_declarada`, `descricao`, `valor_reclamado`, `canal`, `codigo_ibge`, `municipio`, `lat`, `lon`, `id_prestador`, `documentos` (lista), `lote`, mais as colunas internas `_nome_segurado`, `_texto_laudo` e `_padrao` (começam com `_` e **não** são publicadas);
    - **gabarito:** `id_aviso`, `padrao`, `decisao_esperada`, `valor_devido`, `motivo`, `forca_evidencia_esperada`, `fonte_evidencia_esperada`;
    - **itens:** `id_aviso` mais os campos de item.
  - `gerar_evento(ctx, segurados, apolices, coberturas, corretores, n, n_lotes) -> ResultadoEvento`;
  - `gerar_historico(ctx, n) -> tuple[DataFrame, DataFrame]`. A primeira tabela (sinistros) tem `id_sinistro`, `data_ocorrencia`, `data_aviso`, `causa_declarada`, `descricao`, `valor_reclamado`, `canal`, `codigo_ibge`, `municipio`, `lat`, `lon`, `id_prestador`, `ramo`, `cobertura_contratada`, `lmi_cobertura`, `franquia`, `inicio_vigencia`, `menciona_preexistente`, `decisao_final`, `motivo_decisao` e `valor_pago`. A segunda tem os itens.

- [ ] **Passo 1: criar a fixture compartilhada** (`testes/conftest.py`):

```python
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from dados_sinteticos.cadastros import gerar_corretores, gerar_prestadores, nova_faker
from dados_sinteticos.precos import gerar_tabela_precos
from dados_sinteticos.sinistros import ContextoGeracao


@pytest.fixture
def mundo():
    """Uma estação (S) com dados completos; o município PERTO fica a ~6 km dela e o LONGE a ~110 km.
    Há sinal severo em 10 a 12/08; nos demais dias de agosto, nenhum sinal. A Defesa Civil registra LONGE de 20 a 22/08."""
    municipios = pd.DataFrame({"codigo_ibge": [1, 2], "municipio": ["PERTO", "LONGE"],
                               "lat": [-27.05, -28.0], "lon": [-52.0, -52.0]})
    estacoes = pd.DataFrame([{"codigo_estacao": "S", "nome": "S", "uf": "SC", "lat": -27.0, "lon": -52.0}])
    linhas = []
    for k in range(31):
        d = date(2026, 8, 1) + timedelta(days=k)
        severo = date(2026, 8, 10) <= d <= date(2026, 8, 12)
        linhas.append({"codigo_estacao": "S", "data": d, "horas_chuva": 24, "chuva_mm": 80.0 if severo else 2.0,
                       "chuva_max_hora_mm": 15.0 if severo else 0.5, "horas_rajada": 24,
                       "rajada_max_ms": 20.0 if severo else 6.0, "queda_temp_max_c": 5.0 if severo else 1.0,
                       "granizo_provavel": severo})
    clima = pd.DataFrame(linhas)
    clima["granizo_provavel"] = clima["granizo_provavel"].astype("boolean")
    dc = pd.DataFrame([{"episodio": "e", "data_inicio": date(2026, 8, 20), "data_fim": date(2026, 8, 22), "municipio": "LONGE",
                        "codigo_ibge": 2, "lat": -28.0, "lon": -52.0, "moradias_atingidas": 100, "fonte_url": "x", "peso": 1.0}])
    fk = nova_faker(7)
    ctx = ContextoGeracao(rng=np.random.default_rng(7), fk=fk, municipios=municipios, estacoes=estacoes,
                          clima_diario=clima, precos=gerar_tabela_precos(), prestadores=gerar_prestadores(fk, 50),
                          janela=(date(2026, 8, 1), date(2026, 8, 31)), defesa_civil=dc)
    return ctx, gerar_corretores(fk, 5)
```

- [ ] **Passo 2: escrever os testes que falham** (`testes/test_sinistros.py`):

```python
from collections import Counter
from datetime import date

import numpy as np
import pandas as pd
import pytest

from dados_sinteticos import config
from dados_sinteticos.cadastros import gerar_apolices, gerar_segurados, pesos_carteira
from dados_sinteticos.precos import gerar_tabela_precos
from dados_sinteticos.sinistros import gabarito, gerar_evento, gerar_historico, gerar_itens, sortear_padroes


def test_sortear_padroes_respeita_proporcoes_exatas():
    c = Counter(sortear_padroes(np.random.default_rng(1), 1000))
    assert c["legitimo_simples"] == 600 and c["orcamento_inflado"] == 40 and c["prestador_concentrado"] == 10
    assert sum(c.values()) == 1000


def test_itens_inflados_ficam_acima_da_referencia():
    itens = gerar_itens(np.random.default_rng(2), "granizo", 8000, gerar_tabela_precos(), fator_preco=config.FATOR_PRECO_INFLADO)
    assert all(i["valor_unitario"] >= 1.4 * i["preco_referencia"] - 0.01 for i in itens)


@pytest.mark.parametrize("padrao,decisao", [("sem_cobertura", "recusar"), ("sem_evento_climatico", "investigar"),
                                            ("orcamento_inflado", "pagar_parcial"), ("legitimo_simples", "pagar_integral")])
def test_gabarito_por_padrao(padrao, decisao):
    itens = [{"valor_total": 3000.0, "quantidade": 10, "preco_referencia": 200.0, "preexistente": False}]
    d, valor, motivo = gabarito(padrao, itens, franquia=1000.0, lmi=50_000.0)
    assert d == decisao and motivo
    if padrao == "orcamento_inflado":
        assert valor == 1000.0  # 10 × 200 − 1000 de franquia
    if padrao == "legitimo_simples":
        assert valor == 2000.0


def test_gabarito_limita_ao_lmi():
    d, valor, _ = gabarito("legitimo_complexo", [{"valor_total": 90_000.0, "quantidade": 1, "preco_referencia": 90_000.0,
                                                  "preexistente": False}], franquia=1000.0, lmi=50_000.0)
    assert (d, valor) == ("pagar_parcial", 50_000.0)


@pytest.fixture
def evento(mundo):
    ctx, corretores = mundo
    pesos = pesos_carteira(ctx.municipios, ctx.defesa_civil, 0.4)
    seg = gerar_segurados(ctx.fk, ctx.rng, ctx.municipios, pesos, 300)
    ap, cob = gerar_apolices(ctx.rng, seg, corretores, 350, date(2025, 10, 1), date(2026, 7, 31))
    return gerar_evento(ctx, seg, ap, cob, corretores, n=200, n_lotes=4), ap, cob


def test_evento_volumes_lotes_e_ids(evento):
    r, _, _ = evento
    assert len(r.avisos) == 200 and r.avisos["id_aviso"].is_unique
    assert sorted(r.avisos["lote"].unique()) == [1, 2, 3, 4]
    assert (r.avisos.sort_values("id_aviso")["data_aviso"].is_monotonic_increasing)
    assert set(r.gabarito["id_aviso"]) == set(r.avisos["id_aviso"])


def test_apolices_unicas_e_vigentes(evento):
    """Foco de revisão 3."""
    r, ap, _ = evento
    todas = pd.concat([ap, r.apolices_extra], ignore_index=True).set_index("id_apolice")
    assert r.avisos["id_apolice"].is_unique
    for a in r.avisos.itertuples():
        p = todas.loc[a.id_apolice]
        assert p.inicio_vigencia <= a.data_ocorrencia <= p.fim_vigencia


def test_padroes_tem_as_caracteristicas_esperadas(evento):
    r, ap, cob = evento
    av = r.avisos.set_index("id_aviso")
    gab = r.gabarito.set_index("id_aviso")
    todas_cob = pd.concat([cob, r.coberturas_extra], ignore_index=True)
    todas_ap = pd.concat([ap, r.apolices_extra], ignore_index=True).set_index("id_apolice")
    for id_aviso, g in gab.iterrows():
        a = av.loc[id_aviso]
        coberturas = set(todas_cob.loc[todas_cob["id_apolice"] == a.id_apolice, "cobertura"])
        if g.padrao == "sem_cobertura":
            assert config.CAUSA_COBERTURA[a.causa_declarada] not in coberturas
        elif g.padrao != "sem_evento_climatico":
            assert config.CAUSA_COBERTURA[a.causa_declarada] in coberturas
        if g.padrao == "apolice_recente":
            dias = (date.fromisoformat(a.data_ocorrencia) - date.fromisoformat(todas_ap.loc[a.id_apolice].inicio_vigencia)).days
            assert 1 <= dias <= 10
        if g.padrao == "prestador_concentrado":
            assert a.id_prestador in config.PRESTADORES_CONCENTRADOS
        if g.padrao == "dano_preexistente":
            assert "anterior ao evento" in a["_texto_laudo"]
            assert any(d.endswith("_laudo.pdf") for d in a.documentos)


def test_evidencia_esperada_por_padrao(evento):
    r, _, _ = evento
    g = r.gabarito
    sem_evento = g[g["padrao"] == "sem_evento_climatico"]
    assert (sem_evento["forca_evidencia_esperada"] == "contraria").mean() >= 0.8
    legit = g[g["padrao"].str.startswith("legitimo")]
    assert (legit["forca_evidencia_esperada"] == "forte").mean() >= 0.9


def test_historico_tem_rotulos_e_snapshot_da_apolice(mundo):
    ctx, _ = mundo
    hist, itens = gerar_historico(ctx, 150)
    assert len(hist) == 150 and hist["id_sinistro"].is_unique
    assert set(hist["decisao_final"]) <= {"pagar_integral", "pagar_parcial", "recusar", "investigar"}
    assert (hist.loc[hist["motivo_decisao"] == "sem_cobertura", "cobertura_contratada"] == False).all()  # noqa: E712
    assert (hist.loc[hist["motivo_decisao"] == "regular", "cobertura_contratada"] == True).all()  # noqa: E712
    assert set(itens["id_sinistro"]) <= set(hist["id_sinistro"])
```

- [ ] **Passo 3: rodar e ver falhar.**

Comando: `uv run pytest testes/test_sinistros.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'dados_sinteticos.sinistros'`

- [ ] **Passo 4: implementar** `src/dados_sinteticos/sinistros.py`:

```python
"""Geração dos sinistros sintéticos: histórico regulado (2025) e avisos do evento (2026).

A geografia e as datas seguem os dados públicos reais (Defesa Civil e INMET; D-015). O gabarito de cada
aviso (padrão, decisão esperada, valor devido) é gerado à parte e nunca é publicado junto com os avisos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from dados_sinteticos import config
from dados_sinteticos.cadastros import criar_apolice_avulsa, criar_segurado_avulso, sortear_lmi_franquia
from dados_sinteticos.documentos import descrever, texto_laudo
from dados_sinteticos.publicos import registro_defesa_civil
from regras.clima import (
    LIMIAR_CHUVA_HORA_MM, LIMIAR_RAJADA_MS, RAIO_ESTACAO_KM, classificar_evidencia, evidencia_inmet, haversine_km,
    indexar_clima_por_data, janela_clima,
)


@dataclass
class ContextoGeracao:
    rng: np.random.Generator
    fk: Faker
    municipios: pd.DataFrame
    estacoes: pd.DataFrame
    clima_diario: pd.DataFrame
    precos: pd.DataFrame
    prestadores: pd.DataFrame
    janela: tuple[date, date]
    defesa_civil: pd.DataFrame | None = None
    _indice: dict = field(default_factory=dict, init=False, repr=False)
    _mun: pd.DataFrame = field(default=None, init=False, repr=False)
    _mun_por_estacao: dict = field(default_factory=dict, init=False, repr=False)
    _dias_com_sinal: pd.DataFrame = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self._indice = indexar_clima_por_data(self.clima_diario)
        self._mun = self.municipios.set_index("codigo_ibge")
        for e in self.estacoes.itertuples():
            dist = self.municipios.apply(lambda m: haversine_km(m.lat, m.lon, e.lat, e.lon), axis=1)
            self._mun_por_estacao[e.codigo_estacao] = self.municipios.loc[dist <= RAIO_ESTACAO_KM, "codigo_ibge"].tolist()
        c = self.clima_diario
        ini, fim = self.janela
        sinal = (c["rajada_max_ms"] >= LIMIAR_RAJADA_MS) | (c["chuva_max_hora_mm"] >= LIMIAR_CHUVA_HORA_MM)
        self._dias_com_sinal = c.loc[sinal & (c["data"] >= ini) & (c["data"] <= fim), ["codigo_estacao", "data"]].reset_index(drop=True)

    def evidencia(self, codigo_ibge: int, lat: float, lon: float, data: date, causa: str) -> tuple[str, str]:
        ev = evidencia_inmet(lat, lon, causa, janela_clima(self._indice, data), self.estacoes)
        dc = self.defesa_civil is not None and registro_defesa_civil(self.defesa_civil, codigo_ibge, data)
        return classificar_evidencia(ev["sinal"], ev["distancia_km"], dc)


@dataclass
class ResultadoEvento:
    avisos: pd.DataFrame
    itens: pd.DataFrame
    gabarito: pd.DataFrame
    apolices_extra: pd.DataFrame
    coberturas_extra: pd.DataFrame
    segurados_extra: pd.DataFrame


def sortear_padroes(rng: np.random.Generator, n: int) -> list[str]:
    contagens = {p: int(np.floor(f * n)) for p, f in config.DIST_PADROES.items()}
    contagens["legitimo_simples"] += n - sum(contagens.values())
    padroes = [p for p, k in contagens.items() for _ in range(k)]
    rng.shuffle(padroes)
    return padroes


def _sortear(rng: np.random.Generator, distribuicao: dict[str, float]) -> str:
    chaves = list(distribuicao)
    return chaves[int(rng.choice(len(chaves), p=np.array(list(distribuicao.values())) / sum(distribuicao.values())))]


def sortear_causa(rng: np.random.Generator, padrao: str) -> str:
    if padrao == "sem_cobertura":
        return _sortear(rng, config.DIST_CAUSAS_SEM_COBERTURA)
    if padrao == "sem_evento_climatico":
        return config.CAUSAS_SEM_EVENTO[int(rng.integers(0, len(config.CAUSAS_SEM_EVENTO)))]
    return _sortear(rng, config.DIST_CAUSAS)


def sortear_alvo(rng: np.random.Generator, padrao: str, franquia: float) -> float:
    complexo = float(min(rng.lognormal(np.log(config.COMPLEXO_MEDIANA_RS), config.COMPLEXO_SIGMA), config.COMPLEXO_MAX_RS))
    simples = float(rng.uniform(franquia + 500, config.TETO_FAST_TRACK_RS * 0.95))
    if padrao == "legitimo_simples":
        return simples
    if padrao in ("legitimo_complexo", "orcamento_inflado", "dano_preexistente"):
        return complexo
    return simples if rng.random() < 0.5 else complexo


def gerar_itens(rng: np.random.Generator, causa: str, alvo_rs: float, precos: pd.DataFrame,
                fator_preco: tuple[float, float] = config.FATOR_PRECO_NORMAL, min_itens: int = 1) -> list[dict]:
    candidatos = precos[precos["causas"].str.split("|").apply(lambda cs: causa in cs)]
    cabem = candidatos[candidatos["preco_referencia"] * fator_preco[1] <= alvo_rs]
    candidatos = cabem if len(cabem) >= min_itens else candidatos.nsmallest(max(min_itens, 3), "preco_referencia")
    k = min(int(rng.integers(min_itens, max(min_itens, 4) + 1)), len(candidatos))
    escolhidos = candidatos.iloc[rng.choice(len(candidatos), size=k, replace=False)]
    pesos = rng.dirichlet(np.ones(k))
    itens = []
    for seq, ((_, item), peso) in enumerate(zip(escolhidos.iterrows(), pesos), start=1):
        unitario = round(float(item.preco_referencia) * float(rng.uniform(*fator_preco)), 2)
        quantidade = max(1, int(round(alvo_rs * peso / unitario)))
        itens.append({"seq": seq, "codigo_item": item.codigo_item, "descricao": item.descricao, "unidade": item.unidade,
                      "quantidade": quantidade, "valor_unitario": unitario, "valor_total": round(quantidade * unitario, 2),
                      "preco_referencia": float(item.preco_referencia), "preexistente": False})
    return itens


def _liquido(valor: float, franquia: float, lmi: float) -> float:
    return round(max(0.0, min(valor - franquia, lmi)), 2)


def gabarito(padrao: str, itens: list[dict], franquia: float, lmi: float) -> tuple[str, float, str]:
    total = sum(i["valor_total"] for i in itens)
    if padrao == "sem_cobertura":
        return "recusar", 0.0, "Causa sem cobertura contratada na apólice"
    if padrao == "sem_evento_climatico":
        return "investigar", 0.0, "Sem evidência do evento climático no local e na data informados"
    if padrao == "apolice_recente":
        return "investigar", _liquido(total, franquia, lmi), "Apólice contratada poucos dias antes do sinistro"
    if padrao == "prestador_concentrado":
        return "investigar", _liquido(total, franquia, lmi), "Prestador com concentração atípica de orçamentos"
    if padrao == "orcamento_inflado":
        referencia = sum(i["quantidade"] * i["preco_referencia"] for i in itens)
        return "pagar_parcial", _liquido(referencia, franquia, lmi), "Orçamento acima da tabela de referência"
    if padrao == "dano_preexistente":
        validos = sum(i["valor_total"] for i in itens if not i["preexistente"])
        return "pagar_parcial", _liquido(validos, franquia, lmi), "Laudo aponta dano preexistente em parte dos itens"
    if total - franquia > lmi:
        return "pagar_parcial", round(lmi, 2), "Valor acima do limite da cobertura (LMI)"
    return "pagar_integral", _liquido(total, franquia, lmi), "Sinistro regular e coberto"


def _itens_do_padrao(rng: np.random.Generator, ctx: ContextoGeracao, padrao: str, causa: str, franquia: float) -> list[dict]:
    alvo = sortear_alvo(rng, padrao, franquia)
    fator = config.FATOR_PRECO_INFLADO if padrao == "orcamento_inflado" else config.FATOR_PRECO_NORMAL
    itens = gerar_itens(rng, causa, alvo, ctx.precos, fator_preco=fator, min_itens=2 if padrao == "dano_preexistente" else 1)
    if padrao == "dano_preexistente":
        k = max(1, len(itens) // 2)
        for i in rng.choice(len(itens), size=k, replace=False):
            itens[int(i)]["preexistente"] = True
    return itens


def _prestador(rng: np.random.Generator, ctx: ContextoGeracao, padrao: str) -> str:
    if padrao == "prestador_concentrado":
        return config.PRESTADORES_CONCENTRADOS[int(rng.integers(0, len(config.PRESTADORES_CONCENTRADOS)))]
    outros = ctx.prestadores.loc[~ctx.prestadores["id_prestador"].isin(config.PRESTADORES_CONCENTRADOS), "id_prestador"]
    return outros.iloc[int(rng.integers(0, len(outros)))]


def sortear_local_legitimo(ctx: ContextoGeracao, causa: str, max_tentativas: int = 500) -> tuple[int, date]:
    rng = ctx.rng
    for _ in range(max_tentativas):
        if ctx.defesa_civil is not None and rng.random() < config.FRACAO_LEGITIMOS_DEFESA_CIVIL:
            dc = ctx.defesa_civil
            linha = dc.iloc[int(rng.choice(len(dc), p=dc["peso"].to_numpy()))]
            dias = (linha.data_fim - linha.data_inicio).days
            return int(linha.codigo_ibge), linha.data_inicio + timedelta(days=int(rng.integers(0, dias + 1)))
        if ctx._dias_com_sinal.empty:
            break
        dia = ctx._dias_com_sinal.iloc[int(rng.integers(0, len(ctx._dias_com_sinal)))]
        candidatos = ctx._mun_por_estacao.get(dia.codigo_estacao, [])
        if not candidatos:
            continue
        codigo = int(candidatos[int(rng.integers(0, len(candidatos)))])
        m = ctx._mun.loc[codigo]
        if ctx.evidencia(codigo, m.lat, m.lon, dia.data, causa)[0] == "forte":
            return codigo, dia.data
    raise RuntimeError(f"não foi possível sortear local legítimo para '{causa}'")


def sortear_local_sem_evento(ctx: ContextoGeracao, causa: str, max_tentativas: int = 3000) -> tuple[int, date]:
    rng = ctx.rng
    ini, fim = ctx.janela
    estacoes = [c for c, ms in ctx._mun_por_estacao.items() if ms]
    for _ in range(max_tentativas):
        est = estacoes[int(rng.integers(0, len(estacoes)))]
        codigo = int(ctx._mun_por_estacao[est][int(rng.integers(0, len(ctx._mun_por_estacao[est])))])
        data = ini + timedelta(days=int(rng.integers(0, (fim - ini).days + 1)))
        m = ctx._mun.loc[codigo]
        if ctx.evidencia(codigo, m.lat, m.lon, data, causa)[0] == "contraria":
            return codigo, data
    raise RuntimeError(f"não foi possível sortear local sem evento para '{causa}'")


def _sortear_local_qualquer(ctx: ContextoGeracao) -> tuple[int, date]:
    codigo = int(ctx.municipios["codigo_ibge"].iloc[int(ctx.rng.integers(0, len(ctx.municipios)))])
    dia = ctx._dias_com_sinal.iloc[int(ctx.rng.integers(0, len(ctx._dias_com_sinal)))]
    return codigo, dia.data


def _escolher_apolice(rng, candidatas, cob_por_apolice, data_oc: date, cobertura: str, quer_cobertura: bool, usadas: set):
    if candidatas is None or candidatas.empty:
        return None
    iso = data_oc.isoformat()
    ok = candidatas[(candidatas["inicio_vigencia"] <= iso) & (candidatas["fim_vigencia"] >= iso)
                    & ~candidatas["id_apolice"].isin(usadas)]
    if ok.empty:
        return None
    tem = ok["id_apolice"].map(lambda a: cobertura in cob_por_apolice.get(a, set()))
    ok = ok[tem == quer_cobertura]
    return None if ok.empty else ok.iloc[int(rng.integers(0, len(ok)))].to_dict()


def _data_aviso(rng: np.random.Generator, data_oc: date) -> date:
    return data_oc + timedelta(days=int(min(rng.geometric(0.35) - 1, 15)))


def _canal(rng: np.random.Generator) -> str:
    return _sortear(rng, config.CANAIS)


def gerar_evento(ctx: ContextoGeracao, segurados: pd.DataFrame, apolices: pd.DataFrame, coberturas: pd.DataFrame,
                 corretores: pd.DataFrame, n: int, n_lotes: int) -> ResultadoEvento:
    rng = ctx.rng
    cob_por_apolice = coberturas.groupby("id_apolice")["cobertura"].apply(set).to_dict()
    detalhe = coberturas.set_index(["id_apolice", "cobertura"])[["lmi", "franquia"]].to_dict("index")
    por_municipio = {c: df for c, df in apolices.groupby("codigo_ibge")}
    seg_idx = segurados.set_index("id_segurado")
    usadas: set = set()
    prox_ap, prox_seg = len(apolices) + 1, len(segurados) + 1
    extras_ap, extras_cob, extras_seg, registros = [], [], [], []

    for padrao in sortear_padroes(rng, n):
        causa = sortear_causa(rng, padrao)
        cobertura = config.CAUSA_COBERTURA[causa]
        codigo, data_oc = (sortear_local_sem_evento(ctx, causa) if padrao == "sem_evento_climatico"
                           else sortear_local_legitimo(ctx, causa))
        apolice = None
        if padrao != "apolice_recente":
            apolice = _escolher_apolice(rng, por_municipio.get(codigo), cob_por_apolice, data_oc, cobertura,
                                        quer_cobertura=(padrao != "sem_cobertura"), usadas=usadas)
        if apolice is None:
            segurado = criar_segurado_avulso(ctx.fk, rng, f"SG-{prox_seg:06d}", ctx._mun.loc[codigo], codigo)
            prox_seg += 1
            dias = int(rng.integers(1, 11)) if padrao == "apolice_recente" else int(rng.integers(30, 330))
            forcar = frozenset({"incendio"} | ({cobertura} if padrao != "sem_cobertura" else set()))
            excluir = frozenset({cobertura}) if padrao == "sem_cobertura" else frozenset()
            apolice, cobs = criar_apolice_avulsa(rng, segurado, f"AP-{prox_ap:07d}", data_oc - timedelta(days=dias),
                                                 corretores, forcar=forcar, excluir=excluir)
            prox_ap += 1
            extras_seg.append(segurado)
            extras_ap.append(apolice)
            extras_cob.extend(cobs)
            cob_por_apolice[apolice["id_apolice"]] = {c["cobertura"] for c in cobs}
            for c in cobs:
                detalhe[(apolice["id_apolice"], c["cobertura"])] = {"lmi": c["lmi"], "franquia": c["franquia"]}
        else:
            segurado = seg_idx.loc[apolice["id_segurado"]].to_dict() | {"id_segurado": apolice["id_segurado"]}
        usadas.add(apolice["id_apolice"])

        cob = detalhe.get((apolice["id_apolice"], cobertura), {"lmi": 0.0, "franquia": 0.0})
        itens = _itens_do_padrao(rng, ctx, padrao, causa, cob["franquia"])
        decisao, valor_devido, motivo = gabarito(padrao, itens, cob["franquia"], cob["lmi"])
        total = round(sum(i["valor_total"] for i in itens), 2)
        data_av = _data_aviso(rng, data_oc)
        forca, fonte = ctx.evidencia(codigo, apolice["lat"], apolice["lon"], data_oc, causa)
        tem_laudo = total > config.LIMIAR_LAUDO_RS or padrao == "dano_preexistente"
        registros.append({
            "id_apolice": apolice["id_apolice"], "cpf_segurado": segurado["cpf"],
            "data_ocorrencia": data_oc.isoformat(), "data_aviso": data_av.isoformat(), "causa_declarada": causa,
            "descricao": descrever(rng, causa), "valor_reclamado": total, "canal": _canal(rng),
            "codigo_ibge": codigo, "municipio": apolice["municipio"], "lat": apolice["lat"], "lon": apolice["lon"],
            "id_prestador": _prestador(rng, ctx, padrao),
            "_nome_segurado": segurado["nome"], "_padrao": padrao, "_tem_laudo": tem_laudo,
            "_texto_laudo": texto_laudo(rng, causa, data_av + timedelta(days=3), itens, padrao) if tem_laudo else "",
            "_itens": itens, "_gab": (decisao, valor_devido, motivo, forca, fonte),
        })

    avisos = pd.DataFrame(registros).sort_values(["data_aviso", "data_ocorrencia"], kind="stable").reset_index(drop=True)
    avisos.insert(0, "id_aviso", [f"AV-2026-{i:06d}" for i in range(1, len(avisos) + 1)])
    avisos["documentos"] = [[f"{a}_orcamento.pdf"] + ([f"{a}_laudo.pdf"] if laudo else [])
                            for a, laudo in zip(avisos["id_aviso"], avisos["_tem_laudo"])]
    avisos["lote"] = 0
    for k, idx in enumerate(np.array_split(avisos.index.to_numpy(), n_lotes), start=1):
        avisos.loc[idx, "lote"] = k
    itens_df = pd.DataFrame([{"id_aviso": a, **i} for a, its in zip(avisos["id_aviso"], avisos["_itens"]) for i in its])
    gab = pd.DataFrame([{"id_aviso": a, "padrao": p, "decisao_esperada": g[0], "valor_devido": g[1], "motivo": g[2],
                         "forca_evidencia_esperada": g[3], "fonte_evidencia_esperada": g[4]}
                        for a, p, g in zip(avisos["id_aviso"], avisos["_padrao"], avisos["_gab"])])
    avisos = avisos.drop(columns=["_itens", "_gab", "_tem_laudo"])
    return ResultadoEvento(avisos, itens_df, gab, pd.DataFrame(extras_ap), pd.DataFrame(extras_cob), pd.DataFrame(extras_seg))


def gerar_historico(ctx: ContextoGeracao, n: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sinistros já regulados (base de treino). A apólice entra como snapshot nas próprias linhas."""
    rng = ctx.rng
    linhas, itens_todos = [], []
    for i, padrao in enumerate(sortear_padroes(rng, n), start=1):
        causa = sortear_causa(rng, padrao)
        if padrao == "sem_evento_climatico":
            codigo, data_oc = sortear_local_sem_evento(ctx, causa)
        elif rng.random() < config.FRACAO_HISTORICO_SEM_ESTACAO:
            codigo, data_oc = _sortear_local_qualquer(ctx)
        else:
            codigo, data_oc = sortear_local_legitimo(ctx, causa)
        ramo = "empresarial" if rng.random() < 0.15 else "residencial"
        lmi, franquia = sortear_lmi_franquia(rng, config.CAUSA_COBERTURA[causa], ramo)
        itens = _itens_do_padrao(rng, ctx, padrao, causa, franquia)
        decisao, valor, _ = gabarito(padrao, itens, franquia, lmi)
        dias = int(rng.integers(1, 11)) if padrao == "apolice_recente" else int(rng.integers(30, 330))
        m = ctx._mun.loc[codigo]
        id_sinistro = f"SN-2025-{i:06d}"
        linhas.append({
            "id_sinistro": id_sinistro, "data_ocorrencia": data_oc.isoformat(), "data_aviso": _data_aviso(rng, data_oc).isoformat(),
            "causa_declarada": causa, "descricao": descrever(rng, causa),
            "valor_reclamado": round(sum(x["valor_total"] for x in itens), 2), "canal": _canal(rng),
            "codigo_ibge": codigo, "municipio": m.municipio,
            "lat": round(float(m.lat) + float(rng.normal(0, 0.01)), 5), "lon": round(float(m.lon) + float(rng.normal(0, 0.01)), 5),
            "id_prestador": _prestador(rng, ctx, padrao), "ramo": ramo, "cobertura_contratada": padrao != "sem_cobertura",
            "lmi_cobertura": lmi, "franquia": franquia, "inicio_vigencia": (data_oc - timedelta(days=dias)).isoformat(),
            "menciona_preexistente": padrao == "dano_preexistente", "decisao_final": decisao,
            "motivo_decisao": "regular" if padrao.startswith("legitimo") else padrao, "valor_pago": valor,
        })
        itens_todos += [{"id_sinistro": id_sinistro, **x} for x in itens]
    return pd.DataFrame(linhas), pd.DataFrame(itens_todos)
```

- [ ] **Passo 5: rodar e ver passar.**

Comando: `uv run pytest testes/test_sinistros.py -q`
Esperado: `12 passed`

- [ ] **Passo 6: rodar a suíte toda.**

Comando: `uv run pytest -q`
Esperado: todos os testes passam.

- [ ] **Passo 7: commit.**

```bash
git add src/dados_sinteticos/sinistros.py testes/conftest.py testes/test_sinistros.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: gerador de sinistros (histórico 2025 e evento 2026) com gabarito

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.9: Orquestração da geração (arquivos, lotes, PDFs, resumo, amostras)

**Arquivos:**
- Criar: `src/dados_sinteticos/gerar.py`, `testes/test_gerar.py`
- Gerados: `_saida/` (fora do git), `dados/amostras/amostra_avisos.md` e `evidencias/00b-geracao-dados.md` (versionados)

**Interfaces:**
- Consome: tudo o que foi produzido nas tarefas 1.3 a 1.8.
- Produz:
  - `Volumes` (dataclass com `corretores`, `prestadores`, `segurados`, `apolices`, `historico`, `evento` e `lotes`) e `Volumes.escalar(fator) -> Volumes`;
  - `gerar(publicos_dir: Path, brutos_dir: Path | None, saida: Path, volumes: Volumes, seed: int) -> dict`, que devolve o resumo;
  - `renderizar_resumo_md(resumo: dict) -> str`;
  - CLI: `uv run python -m dados_sinteticos.gerar --saida _saida --escala 1.0`.
- **Layout de `saida`:**
  - `landing/apolices/{segurados,apolices,apolices_coberturas,corretores}.csv`
  - `landing/referencias/{precos_referencia,prestadores,municipios_sc,estacoes_inmet_sc,defesa_civil_sc_2026}.csv`
  - `landing/clima/inmet_sc_horario_{2025,2026}.csv` (quando `brutos_dir` é informado)
  - `landing/historico/{historico_sinistros_2025,historico_itens_2025}.csv`
  - `_staging/lote_XX/avisos/avisos_lote_XX.jsonl` e `_staging/lote_XX/documentos/*.pdf`
  - `restrito/{gabarito_evento_2026,gabarito_itens_evento_2026}.csv`
  - `resumo_geracao.json`

- [ ] **Passo 1: escrever o teste que falha** (`testes/test_gerar.py`):

```python
import json
import shutil
from pathlib import Path

import pandas as pd

from dados_sinteticos.gerar import Volumes, gerar, renderizar_resumo_md

RAIZ = Path(__file__).resolve().parents[1]


def _publicos_minimos(destino: Path, mundo):
    ctx, _ = mundo
    destino.mkdir(parents=True)
    ctx.municipios.to_csv(destino / "municipios_sc.csv", index=False)
    ctx.estacoes.to_csv(destino / "estacoes_inmet_sc.csv", index=False)
    clima = ctx.clima_diario.copy()
    clima2025 = clima.assign(data=clima["data"].map(lambda d: d.replace(year=2025)))
    clima.to_csv(destino / "clima_sc_diario_2026.csv", index=False)
    clima2025.to_csv(destino / "clima_sc_diario_2025.csv", index=False)
    dc = ctx.defesa_civil.drop(columns=["codigo_ibge", "lat", "lon", "peso"])
    dc.to_csv(destino / "defesa_civil_sc_2026.csv", index=False)


def test_gera_layout_completo_em_escala_minima(tmp_path, mundo, monkeypatch):
    import dados_sinteticos.config as config
    monkeypatch.setattr(config, "JANELA_EVENTO_2026", mundo[0].janela)
    monkeypatch.setattr(config, "JANELA_HISTORICO_2025", tuple(d.replace(year=2025) for d in mundo[0].janela))
    publicos = tmp_path / "publicos"
    _publicos_minimos(publicos, mundo)
    v = Volumes(corretores=5, prestadores=50, segurados=200, apolices=230, historico=60, evento=80, lotes=4)
    resumo = gerar(publicos, None, tmp_path / "saida", v, seed=3)

    s = tmp_path / "saida"
    for f in ["landing/apolices/apolices.csv", "landing/apolices/apolices_coberturas.csv", "landing/apolices/segurados.csv",
              "landing/referencias/precos_referencia.csv", "landing/historico/historico_sinistros_2025.csv",
              "restrito/gabarito_evento_2026.csv", "resumo_geracao.json"]:
        assert (s / f).exists(), f
    lotes = sorted(p.name for p in (s / "_staging").iterdir())
    assert lotes == ["lote_01", "lote_02", "lote_03", "lote_04"]
    linhas = [json.loads(l) for p in sorted((s / "_staging").glob("lote_*/avisos/*.jsonl")) for l in p.read_text().splitlines()]
    assert len(linhas) == 80
    assert not any(k.startswith("_") for k in linhas[0])  # colunas internas não vazam
    pdfs = list((s / "_staging").glob("lote_*/documentos/*.pdf"))
    assert len(pdfs) == sum(len(l["documentos"]) for l in linhas)
    assert resumo["evento"]["avisos"] == 80
    assert "Geração dos dados sintéticos" in renderizar_resumo_md(resumo)


def test_escalar_volumes():
    v = Volumes(corretores=300, prestadores=2000, segurados=50_000, apolices=60_000, historico=20_000, evento=8_000, lotes=10)
    p = v.escalar(0.0625)
    assert p.evento == 500 and p.lotes == 10 and p.corretores >= 20
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_gerar.py -q`
Esperado: FALHA com `ModuleNotFoundError`

- [ ] **Passo 3: implementar** `src/dados_sinteticos/gerar.py`:

```python
"""Orquestra a geração completa dos dados sintéticos e grava o layout de saída (veja o plano, tarefa 1.9).

Uso: uv run python -m dados_sinteticos.gerar --saida _saida --escala 1.0
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from dados_sinteticos import config
from dados_sinteticos.cadastros import (
    gerar_apolices, gerar_corretores, gerar_prestadores, gerar_segurados, nova_faker, pesos_carteira,
)
from dados_sinteticos.documentos import gerar_laudo_pdf, gerar_orcamento_pdf, moeda
from dados_sinteticos.precos import gerar_tabela_precos
from dados_sinteticos.publicos import carregar_clima_diario, carregar_defesa_civil, carregar_estacoes, carregar_municipios_sc
from dados_sinteticos.sinistros import ContextoGeracao, gerar_evento, gerar_historico

RAIZ = Path(__file__).resolve().parents[2]


@dataclass
class Volumes:
    corretores: int = config.N_CORRETORES
    prestadores: int = config.N_PRESTADORES
    segurados: int = config.N_SEGURADOS
    apolices: int = config.N_APOLICES
    historico: int = config.N_HISTORICO
    evento: int = config.N_AVISOS_EVENTO
    lotes: int = config.N_LOTES

    def escalar(self, fator: float) -> "Volumes":
        def e(x: int, minimo: int) -> int:
            return max(minimo, int(round(x * fator)))
        return Volumes(corretores=e(self.corretores, 20), prestadores=e(self.prestadores, 100), segurados=e(self.segurados, 500),
                       apolices=e(self.apolices, 600), historico=e(self.historico, 500), evento=e(self.evento, 50), lotes=self.lotes)


def _csv(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, index=False)


def _distribuicao(serie: pd.Series) -> dict:
    return {str(k): round(float(v), 4) for k, v in serie.value_counts(normalize=True).sort_index().items()}


def gerar(publicos_dir: Path, brutos_dir: Path | None, saida: Path, volumes: Volumes, seed: int = config.SEED) -> dict:
    if saida.exists():
        shutil.rmtree(saida)
    rng, fk = np.random.default_rng(seed), nova_faker(seed)
    municipios = carregar_municipios_sc(publicos_dir / "municipios_sc.csv")
    estacoes = carregar_estacoes(publicos_dir / "estacoes_inmet_sc.csv")
    clima_2025 = carregar_clima_diario(publicos_dir / "clima_sc_diario_2025.csv")
    clima_2026 = carregar_clima_diario(publicos_dir / "clima_sc_diario_2026.csv")
    dc = carregar_defesa_civil(publicos_dir / "defesa_civil_sc_2026.csv", municipios)
    precos = gerar_tabela_precos()
    corretores = gerar_corretores(fk, volumes.corretores)
    prestadores = gerar_prestadores(fk, volumes.prestadores)
    segurados = gerar_segurados(fk, rng, municipios, pesos_carteira(municipios, dc, config.FRACAO_CARTEIRA_UNIFORME), volumes.segurados)
    apolices, coberturas = gerar_apolices(rng, segurados, corretores, volumes.apolices, *config.INICIO_VIGENCIA_CARTEIRA)

    ctx_hist = ContextoGeracao(rng, fk, municipios, estacoes, clima_2025, precos, prestadores, config.JANELA_HISTORICO_2025)
    historico, itens_hist = gerar_historico(ctx_hist, volumes.historico)
    ctx_ev = ContextoGeracao(rng, fk, municipios, estacoes, clima_2026, precos, prestadores, config.JANELA_EVENTO_2026, dc)
    ev = gerar_evento(ctx_ev, segurados, apolices, coberturas, corretores, volumes.evento, volumes.lotes)

    land = saida / "landing"
    _csv(pd.concat([segurados, ev.segurados_extra], ignore_index=True), land / "apolices/segurados.csv")
    _csv(pd.concat([apolices, ev.apolices_extra], ignore_index=True), land / "apolices/apolices.csv")
    _csv(pd.concat([coberturas, ev.coberturas_extra], ignore_index=True), land / "apolices/apolices_coberturas.csv")
    _csv(corretores, land / "apolices/corretores.csv")
    _csv(precos, land / "referencias/precos_referencia.csv")
    _csv(prestadores, land / "referencias/prestadores.csv")
    for nome in ("municipios_sc.csv", "estacoes_inmet_sc.csv", "defesa_civil_sc_2026.csv"):
        (land / "referencias").mkdir(parents=True, exist_ok=True)
        shutil.copy(publicos_dir / nome, land / "referencias" / nome)
    if brutos_dir is not None:
        (land / "clima").mkdir(parents=True, exist_ok=True)
        for ano in (2025, 2026):
            shutil.copy(brutos_dir / f"inmet_sc_horario_{ano}.csv", land / "clima" / f"inmet_sc_horario_{ano}.csv")
    _csv(historico, land / "historico/historico_sinistros_2025.csv")
    _csv(itens_hist, land / "historico/historico_itens_2025.csv")
    _csv(ev.gabarito, saida / "restrito/gabarito_evento_2026.csv")
    _csv(ev.itens, saida / "restrito/gabarito_itens_evento_2026.csv")

    prest = prestadores.set_index("id_prestador")
    itens_por_aviso = {a: g.to_dict("records") for a, g in ev.itens.groupby("id_aviso")}
    publicas = [c for c in ev.avisos.columns if not c.startswith("_") and c != "lote"]
    for lote, grupo in ev.avisos.groupby("lote"):
        base = saida / "_staging" / f"lote_{lote:02d}"
        (base / "avisos").mkdir(parents=True)
        (base / "documentos").mkdir(parents=True)
        with open(base / "avisos" / f"avisos_lote_{lote:02d}.jsonl", "w", encoding="utf-8") as f:
            for a in grupo.to_dict("records"):
                f.write(json.dumps({k: a[k] for k in publicas}, ensure_ascii=False) + "\n")
                gerar_orcamento_pdf(base / "documentos" / a["documentos"][0], rng, a, itens_por_aviso[a["id_aviso"]],
                                    prest.loc[a["id_prestador"]].to_dict(), a["_nome_segurado"])
                if len(a["documentos"]) > 1:
                    gerar_laudo_pdf(base / "documentos" / a["documentos"][1], a, a["_texto_laudo"])

    resumo = {
        "seed": seed, "volumes": asdict(volumes),
        "cadastros": {"segurados": len(segurados) + len(ev.segurados_extra), "apolices": len(apolices) + len(ev.apolices_extra),
                      "corretores": len(corretores), "prestadores": len(prestadores), "itens_preco": len(precos)},
        "historico": {"sinistros": len(historico), "decisao_final": _distribuicao(historico["decisao_final"]),
                      "motivo_decisao": _distribuicao(historico["motivo_decisao"])},
        "evento": {"avisos": len(ev.avisos), "documentos_pdf": int(ev.avisos["documentos"].map(len).sum()),
                   "lotes": {int(k): int(v) for k, v in ev.avisos["lote"].value_counts().sort_index().items()},
                   "ticket_medio_rs": round(float(ev.avisos["valor_reclamado"].mean()), 2),
                   "pct_ate_teto_fast_track": round(float((ev.avisos["valor_reclamado"] <= config.TETO_FAST_TRACK_RS).mean()), 4),
                   "padrao": _distribuicao(ev.gabarito["padrao"]), "causa": _distribuicao(ev.avisos["causa_declarada"]),
                   "forca_evidencia": _distribuicao(ev.gabarito["forca_evidencia_esperada"]),
                   "fonte_evidencia": _distribuicao(ev.gabarito["fonte_evidencia_esperada"]),
                   "top_municipios": {str(k): int(v) for k, v in ev.avisos["municipio"].value_counts().head(10).items()}},
    }
    (saida / "resumo_geracao.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    resumo["_amostras"] = _amostras(ev, itens_por_aviso)
    return resumo


def _amostras(ev, itens_por_aviso) -> list[dict]:
    escolhidos = []
    for padrao in ("legitimo_simples", "orcamento_inflado", "dano_preexistente"):
        linhas = ev.avisos[ev.avisos["_padrao"] == padrao]
        if not linhas.empty:
            a = linhas.iloc[0].to_dict()
            escolhidos.append({"padrao": padrao, "aviso": {k: a[k] for k in ev.avisos.columns if not k.startswith("_") and k != "lote"},
                               "itens": itens_por_aviso[a["id_aviso"]], "laudo": a["_texto_laudo"]})
    return escolhidos


def renderizar_resumo_md(resumo: dict) -> str:
    e = resumo["evento"]
    linhas = ["# Geração dos dados sintéticos", "",
              f"Seed `{resumo['seed']}`. Script: `uv run python -m dados_sinteticos.gerar`. Arquivo completo: `_saida/resumo_geracao.json`.", "",
              "## Cadastros", "", "| Entidade | Quantidade |", "|---|---|"]
    linhas += [f"| {k} | {v:,} |".replace(",", ".") for k, v in resumo["cadastros"].items()]
    linhas += ["", "## Evento (avisos de 2026)", "", f"- Avisos: **{e['avisos']}**, PDFs: **{e['documentos_pdf']}**, lotes: {e['lotes']}",
               f"- Ticket médio: **{moeda(e['ticket_medio_rs'])}**; avisos até o teto de fast track (R$ 5 mil): **{e['pct_ate_teto_fast_track']:.1%}**", ""]
    for titulo, chave in (("Padrão", "padrao"), ("Causa", "causa"), ("Força da evidência esperada", "forca_evidencia"),
                          ("Fonte da evidência esperada", "fonte_evidencia")):
        linhas += [f"### {titulo}", "", "| Valor | % |", "|---|---|"] + [f"| {k} | {v:.1%} |" for k, v in e[chave].items()] + [""]
    linhas += ["### Municípios com mais avisos", "", "| Município | Avisos |", "|---|---|"]
    linhas += [f"| {k} | {v} |" for k, v in e["top_municipios"].items()]
    h = resumo["historico"]
    linhas += ["", "## Histórico regulado (2025)", "", f"- Sinistros: **{h['sinistros']}**", "", "| Decisão final | % |", "|---|---|"]
    linhas += [f"| {k} | {v:.1%} |" for k, v in h["decisao_final"].items()]
    return "\n".join(linhas) + "\n"


def renderizar_amostras_md(amostras: list[dict]) -> str:
    linhas = ["# Amostras de avisos sintéticos", "",
              "Exemplos gerados pelo gerador (o padrão é do gabarito e não é publicado com o aviso). Os itens são os que aparecem no PDF do orçamento.", ""]
    for a in amostras:
        linhas += [f"## Padrão `{a['padrao']}`", "", "```json", json.dumps(a["aviso"], ensure_ascii=False, indent=2), "```", "",
                   "| Item | Qtd. | Un. | Valor unit. | Total | Preço de referência |", "|---|---|---|---|---|---|"]
        linhas += [f"| {i['descricao']} | {i['quantidade']} | {i['unidade']} | {moeda(i['valor_unitario'])} | {moeda(i['valor_total'])} | {moeda(i['preco_referencia'])} |"
                   for i in a["itens"]]
        if a["laudo"]:
            linhas += ["", f"**Laudo:** {a['laudo']}"]
        linhas.append("")
    return "\n".join(linhas)


def main() -> None:
    p = argparse.ArgumentParser(description="Gera os dados sintéticos do caso")
    p.add_argument("--saida", default="_saida")
    p.add_argument("--escala", type=float, default=1.0)
    args = p.parse_args()
    volumes = Volumes().escalar(args.escala) if args.escala != 1.0 else Volumes()
    resumo = gerar(RAIZ / "dados/publicos", RAIZ / "dados/brutos", RAIZ / args.saida, volumes)
    amostras = resumo.pop("_amostras")
    (RAIZ / "evidencias").mkdir(exist_ok=True)
    (RAIZ / "evidencias/00b-geracao-dados.md").write_text(renderizar_resumo_md(resumo), encoding="utf-8")
    (RAIZ / "dados/amostras").mkdir(parents=True, exist_ok=True)
    (RAIZ / "dados/amostras/amostra_avisos.md").write_text(renderizar_amostras_md(amostras), encoding="utf-8")
    print(renderizar_resumo_md(resumo))


if __name__ == "__main__":
    main()
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_gerar.py -q`
Esperado: `2 passed`

- [ ] **Passo 5: gerar em escala de desenvolvimento** (500 avisos) e conferir o resumo.

Comando: `uv run python -m dados_sinteticos.gerar --saida _saida --escala 0.0625`

Esperado:
- o resumo é impresso com `Avisos: 500` e cerca de 85% de evidência `forte`;
- os municípios do topo são Florianópolis, Biguaçu e Seara;
- o ticket médio fica entre R$ 8 mil e R$ 16 mil.

Se o percentual de evidência forte ficar abaixo de 80%, ou o ticket médio sair da faixa, ajuste apenas `COMPLEXO_MEDIANA_RS` ou `FRACAO_LEGITIMOS_DEFESA_CIVIL` em `config.py`, registre o ajuste em `docs/decisoes-e-tradeoffs.md` e rode de novo.

- [ ] **Passo 6: commit.**

```bash
git add src/dados_sinteticos/gerar.py testes/test_gerar.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: orquestração da geração com lotes, PDFs, resumo e amostras

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.10: Publicação dos lotes do evento (`simular_evento.py`)

**Arquivos:**
- Criar: `scripts/simular_evento.py`, `testes/test_simular_evento.py`

**Interfaces:**
- Produz:
  - `publicar_lotes(staging: Path, quantidade: int, enviar: Callable[[Path, str], None], estado: Path) -> list[str]`. Envia, para cada lote, primeiro os documentos e depois os avisos. Os caminhos relativos no destino são `documentos/<arquivo>` e `avisos/<arquivo>`. O estado fica em JSON (`{"publicados": ["lote_01", ...]}`);
  - CLI: `uv run python scripts/simular_evento.py --lotes N [--destino volume|local:<dir>]`. O destino `volume` usa `ambiente.carregar_ambiente().volume_arquivos`.

- [ ] **Passo 1: escrever os testes que falham** (`testes/test_simular_evento.py`):

```python
import shutil
from pathlib import Path

from simular_evento import enviar_local, publicar_lotes


def _staging(tmp_path: Path) -> Path:
    s = tmp_path / "_staging"
    for k in (1, 2, 3):
        (s / f"lote_{k:02d}/avisos").mkdir(parents=True)
        (s / f"lote_{k:02d}/documentos").mkdir(parents=True)
        (s / f"lote_{k:02d}/avisos/avisos_lote_{k:02d}.jsonl").write_text("{}\n")
        (s / f"lote_{k:02d}/documentos/AV-{k}_orcamento.pdf").write_bytes(b"%PDF")
    return s


def test_publica_documentos_antes_dos_avisos(tmp_path):
    ordem = []
    publicar_lotes(_staging(tmp_path), 1, lambda origem, rel: ordem.append(rel), tmp_path / "estado.json")
    assert ordem == ["documentos/AV-1_orcamento.pdf", "avisos/avisos_lote_01.jsonl"]


def test_publicacao_idempotente(tmp_path):
    """Foco de revisão 5: rodar de novo continua do próximo lote, sem duplicar nem pular."""
    s, estado, destino = _staging(tmp_path), tmp_path / "estado.json", tmp_path / "volume"
    assert publicar_lotes(s, 2, enviar_local(destino), estado) == ["lote_01", "lote_02"]
    assert publicar_lotes(s, 2, enviar_local(destino), estado) == ["lote_03"]
    assert publicar_lotes(s, 2, enviar_local(destino), estado) == []
    assert sorted(p.name for p in (destino / "avisos").iterdir()) == [f"avisos_lote_0{k}.jsonl" for k in (1, 2, 3)]
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_simular_evento.py -q`
Esperado: FALHA com `ModuleNotFoundError`

- [ ] **Passo 3: implementar** `scripts/simular_evento.py`:

```python
"""Simula a chegada do pico do evento: publica os próximos lotes de avisos e documentos no Volume.

Uso:
  uv run python scripts/simular_evento.py --lotes 1                 # publica no Volume do UC
  uv run python scripts/simular_evento.py --lotes 1 --destino local:/tmp/volume
O estado (lotes já publicados) fica em _saida/_staging/publicados.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Callable

from ambiente import carregar_ambiente

RAIZ = Path(__file__).resolve().parents[1]


def publicar_lotes(staging: Path, quantidade: int, enviar: Callable[[Path, str], None], estado: Path) -> list[str]:
    publicados = json.loads(estado.read_text())["publicados"] if estado.exists() else []
    pendentes = [p for p in sorted(staging.glob("lote_*")) if p.is_dir() and p.name not in publicados][:quantidade]
    for lote in pendentes:
        for pasta in ("documentos", "avisos"):  # documentos primeiro: quando o aviso chega, o PDF já existe
            for arquivo in sorted((lote / pasta).iterdir()):
                enviar(arquivo, f"{pasta}/{arquivo.name}")
        publicados.append(lote.name)
        estado.write_text(json.dumps({"publicados": publicados}, indent=2))
        print(f"publicado: {lote.name}")
    return [p.name for p in pendentes]


def enviar_local(destino: Path) -> Callable[[Path, str], None]:
    def _enviar(origem: Path, relativo: str) -> None:
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(origem, alvo)
    return _enviar


def enviar_volume(volume: str) -> Callable[[Path, str], None]:
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))

    def _enviar(origem: Path, relativo: str) -> None:
        with open(origem, "rb") as f:
            w.files.upload(f"{volume}/{relativo}", f, overwrite=True)
    return _enviar


def main() -> None:
    p = argparse.ArgumentParser(description="Publica os próximos lotes do evento")
    p.add_argument("--lotes", type=int, default=1)
    p.add_argument("--saida", default="_saida")
    p.add_argument("--destino", default="volume", help="'volume' ou 'local:<diretório>'")
    args = p.parse_args()
    staging = RAIZ / args.saida / "_staging"
    enviar = enviar_volume(carregar_ambiente().volume_arquivos) if args.destino == "volume" else enviar_local(Path(args.destino.split(":", 1)[1]))
    publicar_lotes(staging, args.lotes, enviar, staging / "publicados.json")


if __name__ == "__main__":
    main()
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_simular_evento.py -q`
Esperado: `2 passed`

- [ ] **Passo 5: commit.**

```bash
git add scripts/simular_evento.py testes/test_simular_evento.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: publicação idempotente dos lotes do evento no Volume

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 1.11: Geração completa, envio da base ao Volume e evidência

**Arquivos:**
- Gerados e versionados: `evidencias/00b-geracao-dados.md`, `dados/amostras/amostra_avisos.md`
- Modificar: `README.md`, `docs/decisoes-e-tradeoffs.md` (se houver ajuste de calibração)

- [ ] **Passo 1: gerar na escala completa.**

Comando: `uv run python -m dados_sinteticos.gerar --saida _saida`
Esperado:
- avisos: 8.000;
- PDFs: ~9.500 (um orçamento por aviso mais os laudos);
- histórico: 20.000;
- tempo total de alguns minutos.

- [ ] **Passo 2: revisar `evidencias/00b-geracao-dados.md` e `dados/amostras/amostra_avisos.md`.** Confira:
  - as proporções de padrão são exatamente as da `config` (60%, 25%, 3%, 4%, 3%, 2%, 2%, 1%);
  - o topo de municípios segue a Defesa Civil;
  - a amostra de orçamento inflado mostra o valor unitário acima da referência;
  - o laudo da amostra de dano preexistente cita o dano anterior.

  Mostre ao usuário o resumo da evidência de geração.

- [ ] **Passo 3: enviar a base ao Volume.** Os lotes do evento **não** vão agora: eles são publicados na fase 2, por `simular_evento.py`.

```bash
set -a; source .env; set +a
ARQUIVOS="/Volumes/${FE_BAR_CATALOGO}/${FE_BAR_PREFIXO_SCHEMA}landing/arquivos"
RESTRITO="/Volumes/${FE_BAR_CATALOGO}/${FE_BAR_PREFIXO_SCHEMA}ml/restrito"
for pasta in apolices referencias clima historico; do
  databricks fs cp -r _saida/landing/$pasta dbfs:$ARQUIVOS/$pasta --overwrite -p fe-bar
done
databricks fs cp -r _saida/restrito dbfs:$RESTRITO/gabarito --overwrite -p fe-bar
databricks fs ls dbfs:$ARQUIVOS -p fe-bar
```

Esperado: `apolices/`, `clima/`, `historico/`, `referencias/` e `_verificacao/`.

- [ ] **Passo 4: conferir pelo SQL** (sanidade de leitura no warehouse). Criar `src/governanca/90_conferir_volume.sql`:

```sql
SELECT 'apolices' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/${catalogo}/${schema_landing}/arquivos/apolices/apolices.csv', format => 'csv', header => true);
SELECT 'historico' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/${catalogo}/${schema_landing}/arquivos/historico/historico_sinistros_2025.csv', format => 'csv', header => true);
SELECT 'clima_2026' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/${catalogo}/${schema_landing}/arquivos/clima/inmet_sc_horario_2026.csv', format => 'csv', header => true);
```

Comando: `set -a; source .env; set +a; uv run python scripts/executar_sql.py src/governanca/90_conferir_volume.sql`
Esperado:
- apólices: ~60 mil mais as extras;
- histórico: 20.000;
- clima de 2026: cerca de 23 estações × 7.296 horas.

- [ ] **Passo 5: atualizar a documentação e a memória.**
  - No `README.md`, a tabela de status passa a ter `| Build: fase 1 (dados) | ✅ Concluída |`.
  - Na seção "Estrutura do repositório", acrescentar:
    - `src/` (pacotes `regras` e `dados_sinteticos`);
    - `dados/publicos/` (dados públicos curados, com `FONTES.md`);
    - `dados/amostras/`;
    - `evidencias/`;
    - `testes/`.
  - Atualizar a memória `fe-bar-caso-sinistros-climaticos.md`: as fases 0 e 1 foram concluídas, mais os números reais da geração.

- [ ] **Passo 6: commit.**

```bash
git add evidencias/00b-geracao-dados.md dados/amostras/amostra_avisos.md src/governanca/90_conferir_volume.sql README.md docs/decisoes-e-tradeoffs.md
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: geração completa dos dados e envio da base ao Volume

Co-authored-by: Isaac <no-reply@databricks.com>"
```

- [ ] **Passo 7: escrever o plano da fase 2** (pipeline bronze e silver) com a skill `superpowers:writing-plans`, partindo do roadmap e das decisões da tarefa 0.4.

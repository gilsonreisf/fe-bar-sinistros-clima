# Plano de implementação: fase 2 (pipeline bronze e silver)

> **Para agentes executores:** sub-skill obrigatória: use `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para implementar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`) para acompanhamento.

**Objetivo:** ingerir a base e o lote 1 do evento com Auto Loader, extrair os PDFs com IA e entregar `silver.sinistros_enriquecidos`: cada aviso cruzado com a apólice, o clima (duas fontes) e os documentos, com expectations. O resultado é conferido contra o gabarito e o custo é medido.

**Arquitetura:**
- Um pipeline Lakeflow (SDP, serverless) declarado no bundle, com:
  - bronze em Python (um Auto Loader por pasta do Volume);
  - silver em SQL para tipagem, cruzamentos e IA (`ai_parse_document` e `ai_extract`);
  - silver em Python só onde a regra de negócio já existe em `src/regras`: a agregação diária do INMET e a evidência climática, por `applyInPandas`.
- O pipeline instala o próprio projeto (`--editable ${workspace.file_path}`), então gerador, pipeline e testes usam **as mesmas funções**.
- Nenhum nome de catálogo ou schema é fixo: o bundle passa `catalogo`, `schema_bronze`, `schema_silver` e `volume_arquivos` como configuração do pipeline (D-016).

**Stack:** Lakeflow Spark Declarative Pipelines (`from pyspark import pipelines as dp`), Auto Loader, AI Functions (`ai_parse_document`, `ai_extract` v2.1), DAB (CLI 1.25), pandas e pytest locais.

**Spec:** `docs/specs/2026-11-20-regulacao-sinistros-climaticos-design.md`. Seções principais: 3 (arquitetura), 4.3 (regras climáticas), 4.4 (modelo de dados), 5 (pipeline), 10.3 (erros) e 12 (custo).
**Roadmap:** `docs/planos/2026-11-20-roadmap.md` (fase 2). **Decisões que valem aqui:** D-015, D-016, D-017 e D-018.

## Restrições globais
- **Idioma:** código, comentários, mensagens, documentos e nomes de objetos em **português**; identificadores sem acento.
- **Nomes parametrizados (D-016):**
  - Python lê do módulo `ambiente` ou de `spark.conf`;
  - os `.sql` usam `${...}`;
  - o bundle usa `${var.catalogo}` e `${var.prefixo_schema}`;
  - **nunca** escrever `fe_bar_sinistros_catalog` ou `sinistros_clima.` no código;
  - nenhum nome de pessoa em identificadores.
- **Compute:** apenas serverless. Pipeline com `continuous: false`. **Sem** `mode: development` no bundle, porque ele prefixa os recursos com o nome do usuário.
- **Gabarito:** `ml/restrito` **nunca** é lido pelo pipeline. Ele aparece só nas consultas de conferência (evidência).
- **Custo (D-017):** nesta fase só o **lote 1** (800 avisos) é publicado e processado. O custo é medido em `system.billing` antes de qualquer outro lote; os demais lotes ficam para a fase 5 (chegada do evento pelo `job_evento`).
- **Toda falha leva o sinistro ao regulador (spec 10.3):** expectations só registram (warn), nunca descartam. PDF ilegível vira flag, e falta de estação vira evidência `fraca`.
- **Commits:** autor `-c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com"`; mensagem termina com `Co-authored-by: Isaac <no-reply@databricks.com>`. **Nenhum push.**
- **Antes de comandos que falam com o workspace:** `set -a; source .env; set +a`.

## Foco de revisão
1. **Aviso sem nenhuma linha de clima na janela** (estação fora do ar): o `applyInPandas` recebe uma linha com `codigo_estacao` nulo. Deve sair `fraca` (ou `forte` pela Defesa Civil), nunca erro. Teste em `testes/test_evidencia_pipeline.py::test_grupo_sem_estacao_e_fraca_ou_defesa_civil`.
2. **Paridade gerador × pipeline:** a evidência calculada no formato de grupo do pipeline deve ser **idêntica** à do gabarito para todo aviso sintético. Teste em `testes/test_evidencia_pipeline.py::test_evidencia_do_pipeline_bate_com_o_gabarito`.
3. **Descrição de item extraída com espaços ou maiúsculas diferentes** deve casar com a tabela de preços; um item sem par deve ficar fora do desvio, sem zerá-lo. Conferido na consulta 4 de `91_conferir_pipeline.sql`; os limites estão na tarefa 2.5.
4. **Placeholder do SQL sem chave na configuração do pipeline**, ou nome de catálogo fixo, quebraria o deploy em outro workspace. Teste em `testes/test_pipeline_sql.py`.
5. **Pasta do landing sem tabela bronze**, ou esquema dos avisos diferente do JSON publicado, quebraria a ingestão em silêncio. Teste em `testes/test_gerar.py::test_layout_bate_com_o_contrato_do_landing`.

---

### Tarefa 2.1: Regras de evidência reutilizáveis pelo pipeline

**Arquivos:**
- Modificar: `src/regras/clima.py` (recebe `MIN_HORAS_VALIDAS`, `agregar_diario`, `registro_defesa_civil` e a nova `clima_no_local`)
- Modificar: `src/dados_sinteticos/inmet.py` e `src/dados_sinteticos/publicos.py` (passam a reexportar de `regras.clima`)
- Criar: `src/regras/sinistro.py`, `testes/test_evidencia_pipeline.py`
- Modificar: `testes/conftest.py` (recebe a fixture `evento`) e `testes/test_sinistros.py` (perde a fixture)

**Interfaces:**
- Produz:
  - `regras.clima.agregar_diario(horario) -> DataFrame` e `regras.clima.MIN_HORAS_VALIDAS = 12`, movidos sem mudança de `dados_sinteticos/inmet.py`;
  - `regras.clima.registro_defesa_civil(dc, codigo_ibge, data) -> bool`, movido sem mudança de `dados_sinteticos/publicos.py`;
  - `regras.clima.clima_no_local(lat, lon, janela, estacoes) -> dict`, com as chaves `chuva_mm`, `chuva_max_hora_mm`, `rajada_max_ms` e `granizo_provavel`. Cada valor vem da estação válida mais próxima a até `RAIO_ESTACAO_KM` (máximo da janela), ou `None`;
  - `regras.sinistro.ESQUEMA_EVIDENCIA: str` (DDL Spark) e `regras.sinistro.calcular_evidencia_grupo(grupo: pd.DataFrame) -> pd.DataFrame` (uma linha). O grupo tem as colunas `id_aviso`, `codigo_ibge`, `lat`, `lon`, `data_ocorrencia`, `causa_declarada`, `registro_defesa_civil`, `codigo_estacao`, `data`, `lat_estacao`, `lon_estacao`, `chuva_mm`, `chuva_max_hora_mm`, `rajada_max_ms`, `queda_temp_max_c` e `granizo_provavel`.

- [ ] **Passo 1: mover a fixture `evento`** de `testes/test_sinistros.py` para o fim de `testes/conftest.py`, sem mudar o código, e acrescentar ao `conftest.py` o import `from dados_sinteticos.cadastros import gerar_apolices, gerar_segurados, pesos_carteira` e `from dados_sinteticos.sinistros import gerar_evento`.

Comando: `uv run pytest testes/test_sinistros.py -q`
Esperado: todos passam (a fixture continua sendo encontrada).

- [ ] **Passo 2: escrever os testes que falham** (`testes/test_evidencia_pipeline.py`):

```python
from datetime import date, timedelta

import pandas as pd

from regras.clima import JANELA_DIAS, clima_no_local, registro_defesa_civil
from regras.sinistro import ESQUEMA_EVIDENCIA, calcular_evidencia_grupo


def _grupo_como_pipeline(ctx, aviso: dict) -> pd.DataFrame:
    """Reproduz o formato do grupo montado pelo pipeline (silver.evidencia_climatica): o aviso repetido em cada
    linha de clima das estações na janela D−1 a D+1, ou uma linha com codigo_estacao nulo se não houver clima."""
    data = date.fromisoformat(aviso["data_ocorrencia"])
    c = ctx.clima_diario
    jan = c[(c["data"] >= data - timedelta(days=JANELA_DIAS)) & (c["data"] <= data + timedelta(days=JANELA_DIAS))]
    est = ctx.estacoes.rename(columns={"lat": "lat_estacao", "lon": "lon_estacao"})[["codigo_estacao", "lat_estacao", "lon_estacao"]]
    jan = jan.merge(est, on="codigo_estacao")
    dc = registro_defesa_civil(ctx.defesa_civil, int(aviso["codigo_ibge"]), data) if ctx.defesa_civil is not None else False
    base = {k: aviso[k] for k in ("id_aviso", "codigo_ibge", "lat", "lon", "causa_declarada")}
    base |= {"data_ocorrencia": data, "registro_defesa_civil": dc}
    if jan.empty:
        return pd.DataFrame([base | {"codigo_estacao": None, "data": None, "lat_estacao": None, "lon_estacao": None,
                                     "chuva_mm": None, "chuva_max_hora_mm": None, "rajada_max_ms": None,
                                     "queda_temp_max_c": None, "granizo_provavel": None}])
    return jan.assign(**base)


def test_evidencia_do_pipeline_bate_com_o_gabarito(evento, mundo):
    """Foco de revisão 2: paridade exata entre a evidência do pipeline e a do gerador."""
    r, _, _ = evento
    ctx, _ = mundo
    gab = r.gabarito.set_index("id_aviso")
    for aviso in r.avisos.to_dict("records"):
        out = calcular_evidencia_grupo(_grupo_como_pipeline(ctx, aviso)).iloc[0]
        g = gab.loc[aviso["id_aviso"]]
        assert (out.forca_evidencia_climatica, out.fonte_evidencia) == (g.forca_evidencia_esperada, g.fonte_evidencia_esperada), aviso["id_aviso"]


def test_grupo_sem_estacao_e_fraca_ou_defesa_civil():
    """Foco de revisão 1: estação fora do ar não pode derrubar o pipeline nem virar 'contraria'."""
    linha = {"id_aviso": "AV-X", "codigo_ibge": 1, "lat": -27.0, "lon": -50.0, "data_ocorrencia": date(2026, 9, 28),
             "causa_declarada": "granizo", "codigo_estacao": None, "data": None, "lat_estacao": None, "lon_estacao": None,
             "chuva_mm": None, "chuva_max_hora_mm": None, "rajada_max_ms": None, "queda_temp_max_c": None,
             "granizo_provavel": None}
    sem_dc = calcular_evidencia_grupo(pd.DataFrame([linha | {"registro_defesa_civil": False}])).iloc[0]
    com_dc = calcular_evidencia_grupo(pd.DataFrame([linha | {"registro_defesa_civil": True}])).iloc[0]
    assert (sem_dc.forca_evidencia_climatica, sem_dc.fonte_evidencia) == ("fraca", "nenhuma")
    assert (com_dc.forca_evidencia_climatica, com_dc.fonte_evidencia) == ("forte", "defesa_civil")
    assert sem_dc.chuva_mm is None and sem_dc.distancia_estacao_km is None


def test_colunas_seguem_o_esquema_do_pipeline():
    linha = {"id_aviso": "AV-X", "codigo_ibge": 1, "lat": -27.0, "lon": -50.0, "data_ocorrencia": date(2026, 9, 28),
             "causa_declarada": "vendaval", "registro_defesa_civil": None, "codigo_estacao": "S", "data": date(2026, 9, 28),
             "lat_estacao": -27.01, "lon_estacao": -50.0, "chuva_mm": 3.0, "chuva_max_hora_mm": 1.0, "rajada_max_ms": 20.0,
             "queda_temp_max_c": 1.0, "granizo_provavel": False}
    out = calcular_evidencia_grupo(pd.DataFrame([linha]))
    assert list(out.columns) == [c.split()[0] for c in ESQUEMA_EVIDENCIA.split(", ")]
    assert out.iloc[0].forca_evidencia_climatica == "forte" and out.iloc[0].rajada_max_ms == 20.0


def test_clima_no_local_ignora_estacao_fora_do_raio():
    estacoes = pd.DataFrame([{"codigo_estacao": "LONGE", "lat": -28.0, "lon": -50.0}])
    janela = pd.DataFrame([{"codigo_estacao": "LONGE", "data": date(2026, 9, 28), "chuva_mm": 80.0,
                            "chuva_max_hora_mm": 20.0, "rajada_max_ms": 25.0, "granizo_provavel": True}])
    assert clima_no_local(-27.0, -50.0, janela, estacoes) == {
        "chuva_mm": None, "chuva_max_hora_mm": None, "rajada_max_ms": None, "granizo_provavel": None}
```

- [ ] **Passo 3: rodar e ver falhar.**

Comando: `uv run pytest testes/test_evidencia_pipeline.py -q`
Esperado: FALHA com `ImportError` (`clima_no_local`, `registro_defesa_civil` ou `regras.sinistro` ainda não existem).

- [ ] **Passo 4: mover para `src/regras/clima.py`:**
  - a constante `MIN_HORAS_VALIDAS` e a função `agregar_diario` de `src/dados_sinteticos/inmet.py`, idênticas, com o `import numpy as np`;
  - a função `registro_defesa_civil` de `src/dados_sinteticos/publicos.py`, idêntica (ela usa `JANELA_DIAS` e `timedelta`, que `clima.py` já importa).

  Em `inmet.py`, trocar a definição por `from regras.clima import MIN_HORAS_VALIDAS, agregar_diario  # noqa: F401 (reexportados)` e remover o import de limiares que ficar sem uso. Em `publicos.py`, trocar a definição por `from regras.clima import registro_defesa_civil  # noqa: F401 (reexportado)`.

  Acrescentar a `src/regras/clima.py`, depois de `evidencia_inmet`:

```python
VARIAVEIS_LOCAL = ("chuva_mm", "chuva_max_hora_mm", "rajada_max_ms", "granizo_provavel")


def clima_no_local(lat: float, lon: float, janela: pd.DataFrame, estacoes: pd.DataFrame) -> dict:
    """Valor de cada variável na estação válida mais próxima a até RAIO_ESTACAO_KM (máximo da janela).

    É o clima que o regulador vê no sinistro. Fora do raio, o valor é None (não se usa estação distante).
    """
    dist = {e.codigo_estacao: haversine_km(lat, lon, e.lat, e.lon) for e in estacoes.itertuples()}
    saida: dict = {}
    for var in VARIAVEIS_LOCAL:
        saida[var] = None
        if var not in janela.columns:
            continue
        por_estacao = janela.dropna(subset=[var]).groupby("codigo_estacao")[var].max()
        por_estacao = por_estacao[por_estacao.index.isin(list(dist))]
        if por_estacao.empty:
            continue
        codigo = min(por_estacao.index, key=lambda c: dist[c])
        if dist[codigo] <= RAIO_ESTACAO_KM:
            valor = por_estacao[codigo]
            saida[var] = bool(valor) if var == "granizo_provavel" else float(valor)
    return saida
```

- [ ] **Passo 5: criar `src/regras/sinistro.py`:**

```python
"""Regras do aviso de sinistro usadas pelo pipeline (camada silver), em pandas puro.

`calcular_evidencia_grupo` roda dentro do pipeline via `applyInPandas`, um grupo por aviso, e nos testes locais,
que conferem o resultado contra o gabarito do gerador (paridade). Nada aqui lê o gabarito.
"""
from __future__ import annotations

import pandas as pd

from regras.clima import classificar_evidencia, clima_no_local, evidencia_inmet

COLUNAS_CLIMA = ["chuva_mm", "chuva_max_hora_mm", "rajada_max_ms", "queda_temp_max_c", "granizo_provavel"]
ESQUEMA_EVIDENCIA = ("id_aviso STRING, forca_evidencia_climatica STRING, fonte_evidencia STRING, distancia_estacao_km DOUBLE, "
                     "registro_defesa_civil BOOLEAN, chuva_mm DOUBLE, chuva_max_hora_mm DOUBLE, rajada_max_ms DOUBLE, "
                     "granizo_provavel BOOLEAN")


def calcular_evidencia_grupo(grupo: pd.DataFrame) -> pd.DataFrame:
    """Evidência climática de UM aviso (regra de duas fontes, D-015 e D-018).

    O grupo traz o aviso repetido em cada linha de clima das estações na janela D−1 a D+1. Sem clima na janela, vem
    uma única linha com `codigo_estacao` nulo, e o resultado é 'fraca' (ou 'forte' pela Defesa Civil).
    """
    a = grupo.iloc[0]
    janela = grupo[grupo["codigo_estacao"].notna()]
    estacoes = (janela.drop_duplicates("codigo_estacao")
                .rename(columns={"lat_estacao": "lat", "lon_estacao": "lon"})[["codigo_estacao", "lat", "lon"]])
    janela = janela[["codigo_estacao", "data", *COLUNAS_CLIMA]]
    lat, lon = float(a["lat"]), float(a["lon"])
    ev = evidencia_inmet(lat, lon, a["causa_declarada"], janela, estacoes)
    dc = bool(a["registro_defesa_civil"]) if pd.notna(a["registro_defesa_civil"]) else False
    forca, fonte = classificar_evidencia(ev["sinal"], ev["distancia_km"], dc)
    return pd.DataFrame([{
        "id_aviso": a["id_aviso"], "forca_evidencia_climatica": forca, "fonte_evidencia": fonte,
        "distancia_estacao_km": ev["distancia_km"], "registro_defesa_civil": dc,
        **clima_no_local(lat, lon, janela, estacoes),
    }])
```

- [ ] **Passo 6: rodar e ver passar.**

Comando: `uv run pytest testes/test_evidencia_pipeline.py -q && uv run pytest -q`
Esperado: os 4 testes novos passam e a suíte inteira passa (85 testes).

- [ ] **Passo 7: commit.**

```bash
git add src/regras src/dados_sinteticos/inmet.py src/dados_sinteticos/publicos.py testes/conftest.py testes/test_sinistros.py testes/test_evidencia_pipeline.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: regras de evidência reutilizáveis pelo pipeline, com teste de paridade

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 2.2: Contrato do landing (pastas e esquema dos avisos)

**Arquivos:**
- Modificar: `src/ambiente/__init__.py`, `testes/test_gerar.py`

**Interfaces:**
- Produz:
  - `ambiente.PASTAS_LANDING: dict[str, tuple[str, str]]` (pasta do Volume → (tabela bronze, formato do Auto Loader));
  - `ambiente.ESQUEMA_AVISOS: str` (DDL Spark do JSON publicado);
  - `ambiente.nomes_do_esquema(ddl: str) -> list[str]`.

- [ ] **Passo 1: escrever o teste que falha** (acrescentar a `testes/test_gerar.py`):

```python
def test_layout_bate_com_o_contrato_do_landing(tmp_path, mundo, monkeypatch):
    """Foco de revisão 5: toda pasta do landing tem tabela bronze, e o JSON dos avisos segue o esquema do bronze."""
    import dados_sinteticos.config as config
    from ambiente import ESQUEMA_AVISOS, PASTAS_LANDING, nomes_do_esquema

    monkeypatch.setattr(config, "JANELA_EVENTO_2026", mundo[0].janela)
    monkeypatch.setattr(config, "JANELA_HISTORICO_2025", tuple(d.replace(year=2025) for d in mundo[0].janela))
    publicos = tmp_path / "publicos"
    _publicos_minimos(publicos, mundo)
    v = Volumes(corretores=5, prestadores=50, segurados=200, apolices=230, historico=60, evento=40, lotes=2)
    gerar(publicos, None, tmp_path / "saida", v, seed=5)
    s = tmp_path / "saida"
    pastas = {p.name for p in (s / "landing").iterdir()} | {"avisos", "documentos"}
    assert pastas - {"clima_horario"} == set(PASTAS_LANDING) - {"clima_horario"}  # sem brutos_dir não há clima horário
    assert "clima_horario" in PASTAS_LANDING
    aviso = json.loads((s / "_staging/lote_01/avisos/avisos_lote_01.jsonl").read_text().splitlines()[0])
    assert list(aviso) == nomes_do_esquema(ESQUEMA_AVISOS)
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_gerar.py -q`
Esperado: FALHA com `ImportError: cannot import name 'ESQUEMA_AVISOS'`.

- [ ] **Passo 3: implementar** (acrescentar a `src/ambiente/__init__.py`):

```python
# Contrato do landing: pasta do Volume (uma entidade por pasta; D-018) → (tabela bronze, formato do Auto Loader).
PASTAS_LANDING: dict[str, tuple[str, str]] = {
    "avisos": ("avisos", "json"),
    "documentos": ("documentos", "binaryFile"),
    "apolices": ("apolices", "csv"),
    "apolices_coberturas": ("apolices_coberturas", "csv"),
    "segurados": ("segurados", "csv"),
    "corretores": ("corretores", "csv"),
    "prestadores": ("prestadores", "csv"),
    "precos_referencia": ("precos_referencia", "csv"),
    "municipios_sc": ("municipios", "csv"),
    "estacoes_inmet_sc": ("estacoes_inmet", "csv"),
    "defesa_civil_sc_2026": ("ocorrencias_defesa_civil", "csv"),
    "clima_horario": ("clima_inmet", "csv"),
    "historico_sinistros": ("historico_sinistros", "csv"),
    "historico_itens": ("historico_itens", "csv"),
}

# Esquema explícito dos avisos (JSON): a pasta pode estar vazia antes do primeiro lote, e a inferência falharia.
ESQUEMA_AVISOS = ("id_aviso STRING, id_apolice STRING, cpf_segurado STRING, data_ocorrencia STRING, data_aviso STRING, "
                  "causa_declarada STRING, descricao STRING, valor_reclamado DOUBLE, canal STRING, codigo_ibge INT, "
                  "municipio STRING, lat DOUBLE, lon DOUBLE, id_prestador STRING, documentos ARRAY<STRING>")


def nomes_do_esquema(ddl: str) -> list[str]:
    """Nomes das colunas de um DDL simples do Spark ('a STRING, b ARRAY<STRING>')."""
    return [parte.split()[0] for parte in ddl.split(", ")]
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest -q`
Esperado: todos passam.

- [ ] **Passo 5: commit.**

```bash
git add src/ambiente/__init__.py testes/test_gerar.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: contrato do landing (pastas, tabelas bronze e esquema dos avisos)

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 2.3: Pipeline Lakeflow (bronze e silver) no bundle

> **Revisão na execução (ledger e D-019):** o código abaixo é a versão do plano. A versão final:
> - instala as regras como wheel do Volume `ml/artefatos` (`scripts/publicar_pacote.py`, variável `pacote_python`), com `root_path: ../src/pipeline` e `development: true`, porque o serverless do pipeline não lê os arquivos do workspace fora das fontes;
> - lê o `ai_extract` 2.1 por `$.campo.value`;
> - faz o cast de `parsed:document:elements` e `error_status` para `ARRAY<VARIANT>`;
> - em `calcular_evidencia_grupo`, usa só `lat_estacao` e `lon_estacao` como coordenadas da estação.

**Arquivos:**
- Criar: `src/pipeline/bronze.py`, `src/pipeline/silver_avisos.sql`, `src/pipeline/silver_documentos.sql`, `src/pipeline/silver_cadastros.sql`, `src/pipeline/silver_clima.py`, `src/pipeline/silver_sinistros.sql`
- Criar: `recursos/pipeline_sinistros.yml`, `testes/test_pipeline_sql.py`
- Modificar: `recursos/README.md`

**Interfaces:**
- Consome: `ambiente.PASTAS_LANDING` e `ambiente.ESQUEMA_AVISOS` (2.2); `regras.clima.agregar_diario` e `JANELA_DIAS`; `regras.sinistro.calcular_evidencia_grupo` e `ESQUEMA_EVIDENCIA` (2.1).
- Produz (em `${catalogo}`):
  - **bronze:** as 14 tabelas de `PASTAS_LANDING`, com `_arquivo` e `_ingerido_em`;
  - **silver:** `avisos`, `documentos_texto`, `documentos_extraidos`, `apolices_coberturas`, `ocorrencias_defesa_civil`, `clima_estacao_dia`, `evidencia_climatica`, `documentos_resumo` e `sinistros_enriquecidos`.
  - O pipeline do bundle tem a chave `pipeline_sinistros`.

- [ ] **Passo 1: escrever os testes estáticos que falham** (`testes/test_pipeline_sql.py`):

```python
"""Checagens estáticas do pipeline: sem nome fixo e só com placeholders que o bundle fornece (foco de revisão 4)."""
import re
from pathlib import Path

from dados_sinteticos import config
from regras.clima import RAIO_ESTACAO_KM

RAIZ = Path(__file__).resolve().parents[1]
PIPELINE = RAIZ / "src/pipeline"
RECURSO = RAIZ / "recursos/pipeline_sinistros.yml"
CHAVES = {"catalogo", "schema_bronze", "schema_silver", "volume_arquivos"}


def _arquivos():
    return sorted(PIPELINE.glob("*.sql")) + sorted(PIPELINE.glob("*.py"))


def test_pipeline_tem_bronze_e_silver():
    nomes = {p.name for p in _arquivos()}
    assert {"bronze.py", "silver_avisos.sql", "silver_documentos.sql", "silver_cadastros.sql", "silver_clima.py",
            "silver_sinistros.sql"} <= nomes


def test_configuracao_do_pipeline_tem_todas_as_chaves():
    yml = RECURSO.read_text(encoding="utf-8")
    for chave in CHAVES:
        assert re.search(rf"^\s+{chave}: ", yml, re.M), chave
    assert "--editable ${workspace.file_path}" in yml


def test_sql_usa_so_chaves_da_configuracao():
    for arq in PIPELINE.glob("*.sql"):
        usados = set(re.findall(r"\$\{([a-z_]+)\}", arq.read_text(encoding="utf-8")))
        assert usados and usados <= CHAVES, (arq.name, usados - CHAVES)


def test_python_le_so_chaves_da_configuracao():
    for arq in PIPELINE.glob("*.py"):
        usados = set(re.findall(r'spark\.conf\.get\("([a-z_]+)"\)', arq.read_text(encoding="utf-8")))
        assert usados and usados <= CHAVES, (arq.name, usados - CHAVES)


def test_sem_nome_de_catalogo_fixo():
    for arq in _arquivos() + [RECURSO]:
        texto = arq.read_text(encoding="utf-8")
        assert "fe_bar_sinistros_catalog" not in texto and "sinistros_clima." not in texto, arq.name


def test_regras_do_sql_batem_com_as_regras_python():
    texto = (PIPELINE / "silver_sinistros.sql").read_text(encoding="utf-8")
    for causa, cobertura in config.CAUSA_COBERTURA.items():
        if causa != cobertura:
            assert f"WHEN '{causa}' THEN '{cobertura}'" in texto, causa
    assert f"distancia_estacao_km <= {RAIO_ESTACAO_KM:g}" in texto
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_pipeline_sql.py -q`
Esperado: FALHA (arquivos e recurso ainda não existem).

- [ ] **Passo 3: criar `src/pipeline/bronze.py`:**

```python
"""Bronze: um Auto Loader por pasta do Volume (uma entidade por pasta; D-018), com metadados de ingestão.

Os dados entram como chegaram. Tipagem, cruzamentos e regras ficam na silver.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

from ambiente import ESQUEMA_AVISOS, PASTAS_LANDING

CATALOGO = spark.conf.get("catalogo")  # noqa: F821 (spark é injetado pelo pipeline)
SCHEMA = spark.conf.get("schema_bronze")  # noqa: F821
VOLUME = spark.conf.get("volume_arquivos")  # noqa: F821


def _registrar(pasta: str, tabela: str, formato: str) -> None:
    @dp.table(name=f"{CATALOGO}.{SCHEMA}.{tabela}", comment=f"Bronze: arquivos de {pasta}/ no Volume, como chegaram (Auto Loader).")
    def _ingestao():
        leitor = spark.readStream.format("cloudFiles").option("cloudFiles.format", formato)  # noqa: F821
        if formato == "csv":
            leitor = leitor.option("header", "true").option("cloudFiles.inferColumnTypes", "true")
        elif formato == "json":
            leitor = leitor.schema(ESQUEMA_AVISOS)
        else:  # binaryFile: os PDFs dos avisos
            leitor = leitor.option("pathGlobFilter", "*.pdf")
        return (leitor.load(f"{VOLUME}/{pasta}/")
                .withColumn("_arquivo", F.col("_metadata.file_path"))
                .withColumn("_ingerido_em", F.current_timestamp()))


for _pasta, (_tabela, _formato) in PASTAS_LANDING.items():
    _registrar(_pasta, _tabela, _formato)
```

- [ ] **Passo 4: criar `src/pipeline/silver_avisos.sql`:**

```sql
-- Silver: avisos tipados. As violações viram métricas de qualidade e não descartam o aviso (spec 5 e 10.3).
CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_silver}.avisos (
  CONSTRAINT valor_positivo EXPECT (valor_reclamado > 0),
  CONSTRAINT datas_coerentes EXPECT (data_ocorrencia <= data_aviso),
  CONSTRAINT tem_documento EXPECT (size(documentos) > 0)
)
COMMENT 'Avisos de sinistro tipados, um por linha, como chegaram do canal (app, corretor ou central).'
AS SELECT
  id_aviso, id_apolice, cpf_segurado,
  to_date(data_ocorrencia) AS data_ocorrencia,
  to_date(data_aviso) AS data_aviso,
  causa_declarada, descricao, valor_reclamado, canal, codigo_ibge, municipio, lat, lon, id_prestador, documentos,
  _arquivo, _ingerido_em
FROM STREAM(${catalogo}.${schema_bronze}.avisos);
```

- [ ] **Passo 5: criar `src/pipeline/silver_documentos.sql`:**

```sql
-- Silver: texto dos PDFs (ai_parse_document) e campos estruturados (ai_extract). Cada PDF é processado uma única vez
-- (streaming). Documento ilegível vira flag, não erro (spec 10.3).
CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_silver}.documentos_texto
COMMENT 'Texto de cada PDF do aviso, extraído com ai_parse_document (sem descrições de imagem, para reduzir custo).'
AS SELECT
  regexp_extract(_arquivo, '(AV-[0-9]{4}-[0-9]{6})_', 1) AS id_aviso,
  regexp_extract(_arquivo, '_(orcamento|laudo)[.]pdf$', 1) AS tipo_documento,
  _arquivo,
  concat_ws('\n', transform(parsed:document:elements, e -> e:content::STRING)) AS texto,
  parsed:error_status::STRING AS erro_leitura,
  _ingerido_em
FROM (
  SELECT _arquivo, _ingerido_em,
    ai_parse_document(content, map('version', '2.0', 'descriptionElementTypes', '')) AS parsed
  FROM STREAM(${catalogo}.${schema_bronze}.documentos)
);

CREATE OR REFRESH STREAMING TABLE ${catalogo}.${schema_silver}.documentos_extraidos
COMMENT 'Campos estruturados de orçamentos e laudos (ai_extract): prestador, itens, valores e menção a dano anterior.'
AS SELECT
  id_aviso, tipo_documento, _arquivo, legivel,
  extraido:response:nome_prestador::STRING AS nome_prestador,
  extraido:response:cnpj_prestador::STRING AS cnpj_prestador,
  extraido:response:valor_total::DOUBLE AS valor_total,
  extraido:response:menciona_dano_anterior::BOOLEAN AS menciona_dano_anterior,
  try_variant_get(extraido, '$.response.itens',
    'ARRAY<STRUCT<descricao: STRING, quantidade: DOUBLE, unidade: STRING, valor_unitario: DOUBLE, valor_total: DOUBLE>>') AS itens,
  extraido:error_message::STRING AS erro_extracao,
  _ingerido_em
FROM (
  SELECT *,
    CASE WHEN legivel THEN ai_extract(
      texto,
      '{"nome_prestador": {"type": "string"}, "cnpj_prestador": {"type": "string"}, "valor_total": {"type": "number"}, "menciona_dano_anterior": {"type": "boolean"}, "itens": {"type": "array", "items": {"type": "object", "properties": {"descricao": {"type": "string"}, "quantidade": {"type": "number"}, "unidade": {"type": "string"}, "valor_unitario": {"type": "number"}, "valor_total": {"type": "number"}}}}}',
      map('version', '2.1', 'instructions',
        'Documentos de sinistro residencial no Brasil: orçamentos de reparo e laudos de vistoria, em português. Valores em reais no formato brasileiro: R$ 1.925,00 significa 1925.00. Em orçamentos, itens traz uma linha por item, com a descrição copiada exatamente como está no documento, incluindo o texto entre parênteses. valor_total é o total do orçamento. Em laudos, não há itens nem valor_total, e menciona_dano_anterior é true somente se o texto indicar dano anterior ao evento.')
    ) END AS extraido
  FROM (
    SELECT *, (erro_leitura IS NULL AND length(trim(texto)) > 20) AS legivel
    FROM STREAM(${catalogo}.${schema_silver}.documentos_texto)
  )
);

CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.documentos_resumo
COMMENT 'Resumo dos documentos de cada aviso: valor do orçamento, itens casados com a tabela de preços e desvio de preço.'
AS WITH docs AS (
  SELECT id_aviso,
    max(CASE WHEN tipo_documento = 'orcamento' AND legivel THEN 1 ELSE 0 END) AS tem_orcamento,
    max(CASE WHEN NOT legivel THEN 1 ELSE 0 END) AS tem_ilegivel,
    max(CASE WHEN tipo_documento = 'laudo' AND legivel AND menciona_dano_anterior THEN 1 ELSE 0 END) AS laudo_dano_anterior,
    max(CASE WHEN tipo_documento = 'orcamento' AND legivel THEN valor_total END) AS valor_orcamento
  FROM ${catalogo}.${schema_silver}.documentos_extraidos
  GROUP BY id_aviso
),
itens AS (
  SELECT d.id_aviso, i.descricao, i.quantidade, i.valor_unitario
  FROM ${catalogo}.${schema_silver}.documentos_extraidos d
  LATERAL VIEW explode(d.itens) t AS i
  WHERE d.tipo_documento = 'orcamento' AND d.legivel
),
precos AS (
  SELECT lower(regexp_replace(trim(descricao), '\\s+', ' ')) AS chave, CAST(preco_referencia AS DOUBLE) AS preco_referencia
  FROM ${catalogo}.${schema_bronze}.precos_referencia
),
casados AS (
  SELECT it.id_aviso,
    count(*) AS itens_extraidos,
    count(p.preco_referencia) AS itens_casados,
    sum(CASE WHEN p.preco_referencia IS NOT NULL THEN it.quantidade * it.valor_unitario END) AS valor_casado,
    sum(it.quantidade * p.preco_referencia) AS valor_referencia
  FROM itens it
  LEFT JOIN precos p ON p.chave = lower(regexp_replace(trim(it.descricao), '\\s+', ' '))
  GROUP BY it.id_aviso
)
SELECT d.id_aviso, d.tem_orcamento, d.tem_ilegivel, d.laudo_dano_anterior, d.valor_orcamento,
  coalesce(c.itens_extraidos, 0) AS itens_extraidos, coalesce(c.itens_casados, 0) AS itens_casados,
  round(c.valor_casado / c.valor_referencia - 1, 4) AS desvio_preco_pct
FROM docs d
LEFT JOIN casados c ON c.id_aviso = d.id_aviso;
```

- [ ] **Passo 6: criar `src/pipeline/silver_cadastros.sql`:**

```sql
-- Silver: apólices com coberturas e ocorrências da Defesa Civil ligadas ao código IBGE.
CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.apolices_coberturas
COMMENT 'Apólice com cada cobertura contratada (LMI e franquia): uma linha por apólice e cobertura.'
AS SELECT
  a.id_apolice, a.id_segurado, a.id_corretor, a.ramo, CAST(a.codigo_ibge AS INT) AS codigo_ibge, a.municipio,
  to_date(a.inicio_vigencia) AS inicio_vigencia, to_date(a.fim_vigencia) AS fim_vigencia,
  CAST(a.premio_anual AS DOUBLE) AS premio_anual,
  c.cobertura, CAST(c.lmi AS DOUBLE) AS lmi, CAST(c.franquia AS DOUBLE) AS franquia
FROM ${catalogo}.${schema_bronze}.apolices a
JOIN ${catalogo}.${schema_bronze}.apolices_coberturas c ON c.id_apolice = a.id_apolice;

CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.ocorrencias_defesa_civil (
  CONSTRAINT municipio_reconhecido EXPECT (codigo_ibge IS NOT NULL)
)
COMMENT 'Ocorrências da Defesa Civil de SC por município e episódio, com o código IBGE (segunda fonte de evidência; D-015).'
AS SELECT
  o.episodio, to_date(o.data_inicio) AS data_inicio, to_date(o.data_fim) AS data_fim, o.municipio,
  CAST(m.codigo_ibge AS INT) AS codigo_ibge, CAST(o.moradias_atingidas AS INT) AS moradias_atingidas, o.fonte_url
FROM ${catalogo}.${schema_bronze}.ocorrencias_defesa_civil o
LEFT JOIN ${catalogo}.${schema_bronze}.municipios m ON m.municipio = o.municipio;
```

- [ ] **Passo 7: criar `src/pipeline/silver_clima.py`:**

```python
"""Silver: clima diário por estação e evidência climática de cada aviso.

As regras são as mesmas do gerador (src/regras), executadas no pipeline com applyInPandas: nada é reimplementado.
"""
import pandas as pd
from pyspark import pipelines as dp
from pyspark.sql import functions as F

from regras.clima import JANELA_DIAS, agregar_diario
from regras.sinistro import ESQUEMA_EVIDENCIA, calcular_evidencia_grupo

CATALOGO = spark.conf.get("catalogo")  # noqa: F821 (spark é injetado pelo pipeline)
BRONZE = f"{CATALOGO}.{spark.conf.get('schema_bronze')}"  # noqa: F821
SILVER = f"{CATALOGO}.{spark.conf.get('schema_silver')}"  # noqa: F821
ESQUEMA_CLIMA_DIA = ("codigo_estacao STRING, data DATE, horas_chuva BIGINT, chuva_mm DOUBLE, chuva_max_hora_mm DOUBLE, "
                     "horas_rajada BIGINT, rajada_max_ms DOUBLE, queda_temp_max_c DOUBLE, granizo_provavel BOOLEAN")


def _agregar_estacao(horario: pd.DataFrame) -> pd.DataFrame:
    diario = agregar_diario(horario.assign(data=pd.to_datetime(horario["data"]).dt.date))
    diario["granizo_provavel"] = diario["granizo_provavel"].astype(object).where(diario["granizo_provavel"].notna(), None)
    return diario


@dp.materialized_view(name=f"{SILVER}.clima_estacao_dia",
                      comment="Clima diário por estação do INMET (dias com menos de 12 h válidas ficam ausentes).")
def clima_estacao_dia():
    horario = spark.read.table(f"{BRONZE}.clima_inmet").select(  # noqa: F821
        "codigo_estacao", F.to_date("data").alias("data"), F.col("hora_utc").cast("int").alias("hora_utc"),
        *[F.col(c).cast("double").alias(c) for c in ("chuva_mm", "rajada_ms", "temp_c")])
    return horario.groupBy("codigo_estacao").applyInPandas(_agregar_estacao, ESQUEMA_CLIMA_DIA)


@dp.materialized_view(name=f"{SILVER}.evidencia_climatica",
                      comment="Evidência climática de cada aviso: INMET a até 30 km ou Defesa Civil no município (D-015).")
def evidencia_climatica():
    avisos = spark.read.table(f"{SILVER}.avisos").select(  # noqa: F821
        "id_aviso", "codigo_ibge", "lat", "lon", "data_ocorrencia", "causa_declarada")
    estacoes = spark.read.table(f"{BRONZE}.estacoes_inmet").select(  # noqa: F821
        F.col("codigo_estacao").cast("string").alias("codigo_estacao"),
        F.col("lat").cast("double").alias("lat_estacao"), F.col("lon").cast("double").alias("lon_estacao"))
    clima = spark.read.table(f"{SILVER}.clima_estacao_dia").join(estacoes, "codigo_estacao")  # noqa: F821
    janela = avisos.join(
        clima,
        (clima["data"] >= F.date_sub(avisos["data_ocorrencia"], JANELA_DIAS))
        & (clima["data"] <= F.date_add(avisos["data_ocorrencia"], JANELA_DIAS)),
        "left")
    ocorrencias = spark.read.table(f"{SILVER}.ocorrencias_defesa_civil").alias("d")  # noqa: F821
    registro = (avisos.alias("a")
                .join(ocorrencias,
                      (F.col("a.codigo_ibge") == F.col("d.codigo_ibge"))
                      & (F.col("a.data_ocorrencia") >= F.date_sub(F.col("d.data_inicio"), JANELA_DIAS))
                      & (F.col("a.data_ocorrencia") <= F.date_add(F.col("d.data_fim"), JANELA_DIAS)),
                      "left")
                .groupBy(F.col("a.id_aviso").alias("id_aviso"))
                .agg(F.max(F.col("d.codigo_ibge").isNotNull()).alias("registro_defesa_civil")))
    return (janela.join(registro, "id_aviso", "left")
            .groupBy("id_aviso").applyInPandas(calcular_evidencia_grupo, ESQUEMA_EVIDENCIA))
```

- [ ] **Passo 8: criar `src/pipeline/silver_sinistros.sql`:**

```sql
-- Silver: o sinistro enriquecido, com o aviso cruzado com a apólice, a evidência climática e os documentos.
-- Expectations só medem (warn): nenhum aviso é descartado em silêncio, e toda falha vai para o regulador (spec 10.3).
CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.sinistros_enriquecidos (
  CONSTRAINT apolice_existente EXPECT (apolice_existe),
  CONSTRAINT ocorrencia_na_vigencia EXPECT (dentro_vigencia),
  CONSTRAINT datas_coerentes EXPECT (data_ocorrencia <= data_aviso),
  CONSTRAINT valor_positivo EXPECT (valor_reclamado > 0),
  CONSTRAINT documento_lido EXPECT (NOT array_contains(flags_documento, 'documento_ilegivel')),
  CONSTRAINT estacao_no_raio EXPECT (coalesce(distancia_estacao_km <= 30, false))
)
COMMENT 'Sinistro enriquecido: aviso + apólice e cobertura + evidência climática (duas fontes) + documentos e preços.'
AS WITH apolice AS (
  SELECT DISTINCT id_apolice, ramo, inicio_vigencia, fim_vigencia
  FROM ${catalogo}.${schema_silver}.apolices_coberturas
),
base AS (
  SELECT a.*, ap.ramo, ap.inicio_vigencia, ap.fim_vigencia,
    CASE a.causa_declarada
      WHEN 'granizo' THEN 'vendaval_granizo'
      WHEN 'vendaval' THEN 'vendaval_granizo'
      ELSE a.causa_declarada
    END AS cobertura_necessaria
  FROM ${catalogo}.${schema_silver}.avisos a
  LEFT JOIN apolice ap ON ap.id_apolice = a.id_apolice
),
prestador AS (
  SELECT id_prestador, count(*) AS qtd_orcamentos_prestador
  FROM ${catalogo}.${schema_silver}.avisos
  GROUP BY id_prestador
),
juntos AS (
  SELECT b.*,
    b.inicio_vigencia IS NOT NULL AS apolice_existe,
    c.lmi IS NOT NULL AS cobertura_valida, c.lmi, c.franquia,
    datediff(b.data_ocorrencia, b.inicio_vigencia) AS dias_desde_contratacao,
    coalesce(b.data_ocorrencia BETWEEN b.inicio_vigencia AND b.fim_vigencia, false) AS dentro_vigencia,
    e.forca_evidencia_climatica, e.fonte_evidencia, e.distancia_estacao_km, e.registro_defesa_civil,
    e.chuva_mm, e.chuva_max_hora_mm, e.rajada_max_ms, e.granizo_provavel,
    r.valor_orcamento, coalesce(r.itens_extraidos, 0) AS itens_extraidos, coalesce(r.itens_casados, 0) AS itens_casados,
    r.desvio_preco_pct, r.tem_orcamento, r.tem_ilegivel, r.laudo_dano_anterior,
    p.qtd_orcamentos_prestador
  FROM base b
  LEFT JOIN ${catalogo}.${schema_silver}.apolices_coberturas c
    ON c.id_apolice = b.id_apolice AND c.cobertura = b.cobertura_necessaria
  LEFT JOIN ${catalogo}.${schema_silver}.evidencia_climatica e ON e.id_aviso = b.id_aviso
  LEFT JOIN ${catalogo}.${schema_silver}.documentos_resumo r ON r.id_aviso = b.id_aviso
  LEFT JOIN prestador p ON p.id_prestador = b.id_prestador
)
SELECT
  id_aviso, id_apolice, cpf_segurado, data_ocorrencia, data_aviso, causa_declarada, descricao, valor_reclamado, canal,
  codigo_ibge, municipio, lat, lon, id_prestador, documentos, ramo, cobertura_necessaria, apolice_existe,
  cobertura_valida, lmi, franquia, inicio_vigencia, dias_desde_contratacao, dentro_vigencia,
  coalesce(forca_evidencia_climatica, 'fraca') AS forca_evidencia_climatica,
  coalesce(fonte_evidencia, 'nenhuma') AS fonte_evidencia,
  distancia_estacao_km, registro_defesa_civil, chuva_mm, chuva_max_hora_mm, rajada_max_ms, granizo_provavel,
  valor_orcamento, itens_extraidos, itens_casados, desvio_preco_pct, qtd_orcamentos_prestador,
  filter(array(
    CASE WHEN coalesce(tem_orcamento, 0) = 0 THEN 'sem_orcamento' END,
    CASE WHEN tem_ilegivel = 1 THEN 'documento_ilegivel' END,
    CASE WHEN laudo_dano_anterior = 1 THEN 'menciona_dano_anterior' END,
    CASE WHEN abs(valor_orcamento - valor_reclamado) > 0.01 * greatest(1.0, valor_reclamado) THEN 'valor_divergente' END,
    CASE WHEN desvio_preco_pct >= 0.30 THEN 'preco_acima_referencia' END
  ), x -> x IS NOT NULL) AS flags_documento,
  filter(array(
    CASE WHEN NOT apolice_existe THEN 'apolice_inexistente' END,
    CASE WHEN apolice_existe AND NOT dentro_vigencia THEN 'fora_vigencia' END,
    CASE WHEN data_ocorrencia > data_aviso THEN 'datas_incoerentes' END,
    CASE WHEN valor_reclamado <= 0 THEN 'valor_invalido' END,
    CASE WHEN distancia_estacao_km IS NULL OR distancia_estacao_km > 30 THEN 'sem_estacao_no_raio' END
  ), x -> x IS NOT NULL) AS alertas_qualidade
FROM juntos;
```

- [ ] **Passo 9: criar `recursos/pipeline_sinistros.yml`:**

```yaml
# Pipeline Lakeflow (SDP, serverless): bronze e silver dos sinistros. Nomes vêm das variáveis do bundle (D-016).
resources:
  pipelines:
    pipeline_sinistros:
      name: sinistros_clima_pipeline
      catalog: ${var.catalogo}
      schema: ${var.prefixo_schema}bronze
      serverless: true
      continuous: false
      channel: CURRENT
      root_path: ../src/pipeline
      libraries:
        - glob:
            include: ../src/pipeline/**
      environment:
        dependencies:
          - --editable ${workspace.file_path}
      configuration:
        catalogo: ${var.catalogo}
        schema_bronze: ${var.prefixo_schema}bronze
        schema_silver: ${var.prefixo_schema}silver
        volume_arquivos: /Volumes/${var.catalogo}/${var.prefixo_schema}landing/arquivos
```

  E acrescentar a `recursos/README.md` a linha: `- pipeline_sinistros.yml: pipeline Lakeflow (bronze e silver) com a configuração catalogo, schema_bronze, schema_silver e volume_arquivos.`

- [ ] **Passo 10: rodar os testes e validar o bundle.**

Comando: `uv run pytest -q && set -a && source .env && set +a && databricks bundle validate -t dev --var warehouse_id=$FE_BAR_WAREHOUSE_ID`
Esperado: todos os testes passam e `Validation OK!`.

- [ ] **Passo 11: commit.**

```bash
git add src/pipeline recursos testes/test_pipeline_sql.py
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: pipeline Lakeflow bronze e silver (Auto Loader, ai_parse_document, ai_extract, evidência)

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 2.4: Evidência em texto (conferência e custo)

**Arquivos:**
- Criar: `scripts/registrar_evidencia.py`, `testes/test_registrar_evidencia.py`, `src/governanca/91_conferir_pipeline.sql`, `src/governanca/92_custo.sql`
- Modificar: `scripts/executar_sql.py` (aceita variáveis extras)

**Interfaces:**
- Consome: `executar_sql.aplicar_variaveis`, `dividir_comandos` e `executar`; `ambiente.carregar_ambiente().variaveis_sql()`.
- Produz:
  - `renderizar_evidencia(titulo: str, origem: str, quando: str, resultados: list[tuple[str, list[str], list[list]]]) -> str`;
  - CLI: `uv run python scripts/registrar_evidencia.py <arquivo.sql> <saida.md> "<título>"`, com a variável extra `${workspace_id}`.

- [ ] **Passo 1: escrever o teste que falha** (`testes/test_registrar_evidencia.py`):

```python
from registrar_evidencia import renderizar_evidencia


def test_renderiza_cada_consulta_com_sql_e_tabela():
    md = renderizar_evidencia("Ingestão", "src/governanca/91.sql", "2026-11-20 20:00",
                              [("SELECT 1 AS a, NULL AS b", ["a", "b"], [["1", None]])])
    assert md.startswith("# Ingestão\n")
    assert "```sql\nSELECT 1 AS a, NULL AS b\n```" in md
    assert "| a | b |\n|---|---|\n| 1 |  |" in md


def test_consulta_sem_colunas_vira_nota():
    md = renderizar_evidencia("X", "y.sql", "agora", [("COMMENT ON TABLE t IS 'x'", [], [])])
    assert "(comando sem resultado tabular)" in md
```

- [ ] **Passo 2: rodar e ver falhar.**

Comando: `uv run pytest testes/test_registrar_evidencia.py -q`
Esperado: FALHA com `ModuleNotFoundError: No module named 'registrar_evidencia'`.

- [ ] **Passo 3: implementar `scripts/registrar_evidencia.py`:**

```python
"""Executa um .sql no SQL Warehouse e grava as saídas em Markdown, como evidência em texto (o avaliador só lê texto).

Uso: uv run python scripts/registrar_evidencia.py <arquivo.sql> <saida.md> "<título>"
Placeholders: os do módulo `ambiente` (catálogo e schemas) mais ${workspace_id}.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from databricks.sdk import WorkspaceClient

from ambiente import carregar_ambiente
from executar_sql import aplicar_variaveis, dividir_comandos, executar

RAIZ = Path(__file__).resolve().parents[1]


def renderizar_evidencia(titulo: str, origem: str, quando: str, resultados: list[tuple[str, list[str], list[list]]]) -> str:
    partes = [f"# {titulo}", "", f"Executado em {quando} com `uv run python scripts/registrar_evidencia.py {origem}` "
              "(catálogo e schemas lidos do `.env`; D-016).", ""]
    for i, (comando, colunas, linhas) in enumerate(resultados, start=1):
        partes += [f"## Consulta {i}", "", "```sql", comando, "```", ""]
        if not colunas:
            partes += ["(comando sem resultado tabular)", ""]
            continue
        partes += ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
        partes += ["| " + " | ".join("" if v is None else str(v) for v in linha) + " |" for linha in linhas]
        partes.append("")
    return "\n".join(partes)


def main(arquivo_sql: str, saida_md: str, titulo: str) -> None:
    w = WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fe-bar"))
    variaveis = carregar_ambiente().variaveis_sql() | {"workspace_id": str(w.get_workspace_id())}
    sql = aplicar_variaveis((RAIZ / arquivo_sql).read_text(encoding="utf-8"), variaveis)
    resultados = []
    for comando in dividir_comandos(sql):
        colunas, linhas = executar(w, os.environ["FE_BAR_WAREHOUSE_ID"], comando)
        resultados.append((comando, colunas, linhas))
    md = renderizar_evidencia(titulo, arquivo_sql, datetime.now().strftime("%Y-%m-%d %H:%M"), resultados)
    destino = RAIZ / saida_md
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main(*sys.argv[1:4])
```

- [ ] **Passo 4: rodar e ver passar.**

Comando: `uv run pytest testes/test_registrar_evidencia.py -q`
Esperado: `2 passed`.

- [ ] **Passo 5: criar `src/governanca/91_conferir_pipeline.sql`** (conferência do pipeline contra o gabarito; o gabarito é lido **só aqui**, nunca no pipeline):

```sql
-- Conferência da fase 2: volumes por camada, leitura e extração dos documentos e paridade com o gabarito.
SELECT 'bronze' AS camada, 'avisos' AS tabela, count(*) AS linhas FROM ${catalogo}.${schema_bronze}.avisos
UNION ALL SELECT 'bronze', 'documentos', count(*) FROM ${catalogo}.${schema_bronze}.documentos
UNION ALL SELECT 'bronze', 'apolices', count(*) FROM ${catalogo}.${schema_bronze}.apolices
UNION ALL SELECT 'bronze', 'apolices_coberturas', count(*) FROM ${catalogo}.${schema_bronze}.apolices_coberturas
UNION ALL SELECT 'bronze', 'segurados', count(*) FROM ${catalogo}.${schema_bronze}.segurados
UNION ALL SELECT 'bronze', 'clima_inmet', count(*) FROM ${catalogo}.${schema_bronze}.clima_inmet
UNION ALL SELECT 'bronze', 'historico_sinistros', count(*) FROM ${catalogo}.${schema_bronze}.historico_sinistros
UNION ALL SELECT 'silver', 'avisos', count(*) FROM ${catalogo}.${schema_silver}.avisos
UNION ALL SELECT 'silver', 'documentos_extraidos', count(*) FROM ${catalogo}.${schema_silver}.documentos_extraidos
UNION ALL SELECT 'silver', 'clima_estacao_dia', count(*) FROM ${catalogo}.${schema_silver}.clima_estacao_dia
UNION ALL SELECT 'silver', 'evidencia_climatica', count(*) FROM ${catalogo}.${schema_silver}.evidencia_climatica
UNION ALL SELECT 'silver', 'sinistros_enriquecidos', count(*) FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos;

SELECT tipo_documento, count(*) AS documentos, sum(CAST(legivel AS INT)) AS legiveis,
  sum(CAST(erro_extracao IS NOT NULL AS INT)) AS erros_extracao
FROM ${catalogo}.${schema_silver}.documentos_extraidos GROUP BY tipo_documento ORDER BY tipo_documento;

SELECT g.forca_evidencia_esperada, s.forca_evidencia_climatica, g.fonte_evidencia_esperada, s.fonte_evidencia, count(*) AS avisos
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos s
JOIN read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) g
  ON g.id_aviso = s.id_aviso
GROUP BY ALL ORDER BY avisos DESC;

WITH gab AS (
  SELECT id_aviso, round(sum(CAST(valor_total AS DOUBLE)), 2) AS total_gabarito, count(*) AS itens_gabarito
  FROM read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_itens_evento_2026.csv', format => 'csv', header => true)
  GROUP BY id_aviso
)
SELECT count(*) AS avisos,
  round(100 * avg(CASE WHEN abs(r.valor_orcamento - gab.total_gabarito) <= 0.01 THEN 1.0 ELSE 0.0 END), 1) AS pct_total_exato,
  round(100 * avg(CASE WHEN r.itens_extraidos = gab.itens_gabarito THEN 1.0 ELSE 0.0 END), 1) AS pct_qtd_itens_exata,
  round(100 * sum(r.itens_casados) / sum(r.itens_extraidos), 1) AS pct_itens_casados_com_preco
FROM ${catalogo}.${schema_silver}.documentos_resumo r JOIN gab ON gab.id_aviso = r.id_aviso;

SELECT g.padrao, count(*) AS avisos,
  round(avg(CAST(s.cobertura_valida AS INT)), 2) AS pct_cobertura_valida,
  round(avg(s.desvio_preco_pct), 3) AS desvio_preco_medio,
  round(avg(CAST(array_contains(s.flags_documento, 'menciona_dano_anterior') AS INT)), 2) AS pct_dano_anterior,
  round(avg(CAST(array_contains(s.flags_documento, 'preco_acima_referencia') AS INT)), 2) AS pct_preco_acima,
  percentile(s.dias_desde_contratacao, 0.5) AS mediana_dias_contratacao,
  max(s.qtd_orcamentos_prestador) AS max_orcamentos_prestador
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos s
JOIN read_files('/Volumes/${catalogo}/${schema_ml}/restrito/gabarito/gabarito_evento_2026.csv', format => 'csv', header => true) g
  ON g.id_aviso = s.id_aviso
GROUP BY g.padrao ORDER BY avisos DESC;

SELECT 'flag_documento' AS tipo, f AS valor, count(*) AS avisos
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos LATERAL VIEW explode(flags_documento) t AS f GROUP BY ALL
UNION ALL
SELECT 'alerta_qualidade', a, count(*)
FROM ${catalogo}.${schema_silver}.sinistros_enriquecidos LATERAL VIEW explode(alertas_qualidade) t AS a GROUP BY ALL
ORDER BY tipo, avisos DESC;
```

- [ ] **Passo 6: criar `src/governanca/92_custo.sql`** (o workspace é dedicado ao projeto; preço de lista, sem descontos):

```sql
-- Custo real medido em system.billing.usage (spec 10.1, item 09). Pode haver atraso de algumas horas no faturamento.
SELECT u.usage_date, u.billing_origin_product, u.sku_name,
  round(sum(u.usage_quantity), 3) AS quantidade, any_value(u.usage_unit) AS unidade,
  round(sum(u.usage_quantity * lp.pricing.default), 2) AS custo_lista_usd
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices lp
  ON lp.sku_name = u.sku_name AND lp.cloud = u.cloud
  AND u.usage_start_time >= lp.price_start_time
  AND (lp.price_end_time IS NULL OR u.usage_start_time < lp.price_end_time)
WHERE u.workspace_id = '${workspace_id}' AND u.usage_date >= DATE'2026-11-20'
GROUP BY ALL ORDER BY u.usage_date, custo_lista_usd DESC;
```

  Adicionar `"workspace_id"` às variáveis aceitas: o teste `test_sql_do_projeto_usa_apenas_placeholders_conhecidos`, de `testes/test_executar_sql.py`, passa a montar as variáveis como `carregar_ambiente({}).variaveis_sql() | {"workspace_id": "0"}`.

- [ ] **Passo 7: rodar a suíte.**

Comando: `uv run pytest -q`
Esperado: todos passam.

- [ ] **Passo 8: commit.**

```bash
git add scripts/registrar_evidencia.py testes/test_registrar_evidencia.py testes/test_executar_sql.py src/governanca/91_conferir_pipeline.sql src/governanca/92_custo.sql
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: evidência em texto da conferência do pipeline e do custo real

Co-authored-by: Isaac <no-reply@databricks.com>"
```

### Tarefa 2.5: Execução com o lote 1, conferência e custo

**Arquivos:**
- Gerados e versionados: `evidencias/01-ingestao.md`, `evidencias/09-custo-real.md`
- Modificar: `docs/decisoes-e-tradeoffs.md` (D-019), `README.md`, a memória do projeto

**Interfaces:**
- Consome: tudo das tarefas 2.1 a 2.4; `scripts/simular_evento.py`.

- [ ] **Passo 1: criar as pastas do evento no Volume** (o Auto Loader precisa que o caminho exista).

Comando: `set -a; source .env; set +a; for p in avisos documentos; do databricks fs mkdir dbfs:/Volumes/$FE_BAR_CATALOGO/${FE_BAR_PREFIXO_SCHEMA}landing/arquivos/$p -p fe-bar; done`
Esperado: sem erro.

- [ ] **Passo 2: publicar o lote 1.**

Comando: `set -a; source .env; set +a; uv run python scripts/simular_evento.py --lotes 1`
Esperado: `publicado: lote_01` (800 avisos, ~970 PDFs).

- [ ] **Passo 3: deploy e execução do pipeline.**

Comando: `set -a; source .env; set +a; databricks bundle deploy -t dev --var warehouse_id=$FE_BAR_WAREHOUSE_ID && databricks bundle run pipeline_sinistros -t dev --var warehouse_id=$FE_BAR_WAREHOUSE_ID`
Esperado: a atualização termina em `COMPLETED`. Se falhar, ler `error.exceptions[0].message` nos eventos (`databricks pipelines list-pipeline-events <id> -p fe-bar`). Corrigir a causa com `superpowers:systematic-debugging`, registrar a correção no ledger e rodar de novo.

- [ ] **Passo 4: conferência e evidência.**

Comando: `set -a; source .env; set +a; uv run python scripts/registrar_evidencia.py src/governanca/91_conferir_pipeline.sql evidencias/01-ingestao.md "Ingestão e enriquecimento: lote 1 do evento"`
Esperado:
- bronze: `avisos` = 800, `documentos` = PDFs do lote 1, `apolices` = 60.251 e `clima_inmet` = 378.048 (210.240 + 167.808);
- silver: `avisos` = `sinistros_enriquecidos` = `evidencia_climatica` = 800;
- evidência: em toda linha da consulta 3, a força e a fonte do pipeline são iguais às do gabarito;
- extração: `pct_total_exato` ≥ 95% e `pct_itens_casados_com_preco` ≥ 90%;
- padrões:
  - `sem_cobertura` com `pct_cobertura_valida` = 0;
  - `orcamento_inflado` com `desvio_preco_medio` ≥ 0,40;
  - `legitimo_*` com |desvio| ≤ 0,15;
  - `dano_preexistente` com `pct_dano_anterior` ≥ 0,9;
  - `apolice_recente` com mediana de dias ≤ 10.

Se a extração ficar abaixo do limite, ajustar o texto das `instructions` do `ai_extract`, refazer só as tabelas de documentos (`databricks bundle run pipeline_sinistros -t dev --refresh documentos_texto,documentos_extraidos,documentos_resumo,sinistros_enriquecidos --var ...`, com full refresh dessas tabelas) e registrar no ledger. Divergência de evidência é bug: investigar antes de seguir.

- [ ] **Passo 5: custo real do lote 1.**

Comando: `set -a; source .env; set +a; uv run python scripts/registrar_evidencia.py src/governanca/92_custo.sql evidencias/09-custo-real.md "Custo real medido (lote 1 do evento)"`
Esperado: linhas por produto e SKU (pipeline serverless, AI Functions, SQL warehouse). Se o faturamento ainda não tiver chegado, o arquivo registra isso e o passo é refeito na fase 5, antes de publicar os lotes 2 a 10.

- [ ] **Passo 6: registrar a D-019** em `docs/decisoes-e-tradeoffs.md`:
  - `ai_extract` em vez de `ai_query` para extrair os documentos (função específica, sem escolha de endpoint);
  - tabelas silver adicionais (`documentos_texto`, `documentos_resumo`, `evidencia_climatica` e `clima_estacao_dia` no lugar de `clima_municipio_dia`) e o motivo;
  - regras Python reaproveitadas no pipeline por `applyInPandas`;
  - só o lote 1 processado nesta fase, com o custo medido.

  Atualizar a tabela de status do `README.md` com `| Build: fase 2 (pipeline bronze e silver) | ✅ Concluída (`evidencias/01-ingestao.md`) |` e a estrutura com `src/pipeline/`. Atualizar a memória `fe-bar-caso-sinistros-climaticos.md`.

- [ ] **Passo 7: commit.**

```bash
git add evidencias/01-ingestao.md evidencias/09-custo-real.md docs/decisoes-e-tradeoffs.md README.md
git -c user.name="Gilson Reis" -c user.email="gilson.reis@databricks.com" commit -m "feat: pipeline executado com o lote 1, conferido contra o gabarito e com custo medido

Co-authored-by: Isaac <no-reply@databricks.com>"
```

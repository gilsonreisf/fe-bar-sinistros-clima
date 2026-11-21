# Fase 3: modelo de suspeita — plano de implementação

> **Para agentes:** sub-skill obrigatória: superpowers:executing-plans (modo NATIVE, como nas fases anteriores). Os passos usam checkbox (`- [ ]`).
> **Autorização:** o autor autorizou, em 2026-11-20 (~22h), escrever e executar sem aprovação prévia até o projeto técnico ficar pronto para submissão; ele revisa as decisões depois. Push e repo público continuam exigindo autorização (D-013).

**Objetivo:** treinar no histórico de 2025 um LightGBM que dá a cada sinistro um `score_suspeita` (0 a 1) explicável, registrado no UC como `ml.modelo_suspeita@champion`, com as mesmas features no treino e no score do evento.

**Arquitetura:**
- O pipeline ganha a MV `silver.historico_enriquecido`, com as **mesmas colunas de entrada** de `silver.sinistros_enriquecidos`, calculadas pelas mesmas regras (evidência por `applyInPandas` com `calcular_evidencia_grupo`, desvio de preço com a mesma chave normalizada e participação do prestador point-in-time).
- `regras.features.montar_features()` (pandas puro) transforma essas colunas na matriz do modelo e é usada no treino e no modelo servido.
- O treino roda num notebook, como job serverless do bundle (`job_treino_modelo`):
  - MLflow completo: métricas, artefatos, `log_input` de `ml.features_treino` com a versão Delta, assinatura e SHAP;
  - modelo *models from code*: booster LightGBM como artefato e `regras` em `code_paths`;
  - checagem fora do tempo no lote 1 do evento;
  - portão de promoção para o alias `champion`.

**Tech stack:** Lakeflow SDP (SQL e Python), LightGBM 4.7, MLflow 3 (UC registry), pandas, matplotlib, Databricks Jobs serverless (ambiente 4) e DAB.

**Spec:** `docs/specs/2026-11-20-regulacao-sinistros-climaticos-design.md`, seções 4.4, 6.1, 6.3 e 10. **Decisões herdadas:** D-014 (histórico 2025 como treino), D-016 (nada fixo), D-019 (wheel no Volume) e D-020 (prestador point-in-time).

## Restrições globais

- Nenhum nome de catálogo ou schema fixo: tudo vem de `${var.catalogo}`, de `${var.prefixo_schema}` ou de parâmetros do job (D-016). Nada com o nome do usuário: o experimento fica em `/Shared/${bundle.name}/${bundle.target}/`.
- **Alvo:** `suspeito = padrao não começa com "legitimo_"` (spec 6.1). O rótulo vem só de `restrito/gabarito/gabarito_historico_2025.csv`.
- **Proibidas como feature (vazam o rótulo):** `decisao_final`, `valor_pago`, `motivo_decisao`, `padrao` e a coluna `preexistente` dos itens. Do evento, `decisao_esperada`, `valor_devido` e `motivo`.
- **Split temporal:** treino com `data_aviso` < 2025-10-01 e teste de 2025-10-01 a 2025-12-31.
- **Métricas exigidas (spec 6.1):** AUC, e precisão e recall nos 10% mais suspeitos. **Métricas de negócio adicionadas:** fração de suspeitos com score < 0,2 (escapariam do bloqueio de fast track, spec 6.3) e fração de legítimos com score < 0,2.
- **Registro:** `<catálogo>.<prefixo>ml.modelo_suspeita`, com o alias `champion`. Uma versão nova só vira `champion` se o AUC dela no mesmo teste for **maior** que o do `champion` atual; senão, recebe `challenger` (spec 6.1).
- Todo o conteúdo em português. Evidência em texto (`evidencias/04-ml*.md` e o notebook com saídas em `.ipynb`).
- **Custo:** a fase não reprocessa PDFs (as tabelas com IA têm `reset.allowed=false`) e não publica lotes novos. O treino é um job serverless de minutos.

## Decisões tomadas neste plano (registrar como D-021)

1. **Clima bruto (chuva, rajada, distância) fora do modelo; a evidência entra como ordinal** (contrária < fraca < forte). O histórico de 2025 não tem a Defesa Civil, então a força ali depende só do INMET, e "sem chuva/rajada medida" coincide com suspeita. No evento, 74% da evidência forte vem só da Defesa Civil, muitas vezes sem sinal na estação. Com o clima bruto, o modelo aprenderia que sinistro confirmado pela Defesa Civil sem rajada medida é suspeito. A spec lista chuva, rajada e distância; o desvio é registrado. Os valores continuam na silver, para o parecer e o app. Uma **ablação** (run aninhado, sem registro) treina com o clima bruto e mostra o efeito no teste de 2025 e no lote 1. A escolha é feita antes de ver o resultado, por isso não há seleção usando o evento.
2. **SHAP calculado pelo próprio LightGBM** (`pred_contrib=True`, TreeSHAP exato, igual ao `shap.TreeExplainer`). O pacote `shap` 0.54 exige numpy ≥ 2, e trocar o numpy do ambiente serverless pode quebrar pandas e pyarrow. O mesmo cálculo dá ao modelo servido os **3 principais fatores** de cada score, em português, para o parecer e o app.
3. **Participação do prestador point-in-time:** avisos do prestador nos 30 dias **anteriores** à `data_aviso` (excluindo o próprio dia) ÷ total de avisos na janela, e **nula se a janela tiver menos de 200 avisos**. Sem esse mínimo, no início do evento um prestador comum com 1 aviso em 50 teria 2%, sete vezes o nível dos concentrados no histórico (~0,3%). A janela estritamente anterior garante que um lote novo não altere o valor de avisos já pontuados, porque os lotes saem ordenados por `data_aviso`. A contagem absoluta (`qtd_orcamentos_prestador`) fica na silver para o app, mas fora do modelo.
4. **`canal` fora do modelo** (sem hipótese de negócio; é ruído no gerador). Ficam `causa_declarada` e `ramo` como categóricas de categorias fixas.
5. **Lote 1 do evento = checagem de deriva** (fora do tempo). O teste final em todo o evento fica para a fase 5, com os lotes 2 a 10.
6. **AUC alto é esperado e deve ser dito com honestidade:** os padrões sintéticos foram plantados com sinais claros. O que o modelo prova é que o sinal sobrevive ao pipeline real (OCR, extração e cruzamentos) e que o score combina sinais em um número explicável. Com dados reais, o AUC seria menor, e a calibração viria da PoC.

## Foco de revisão

1. **Paridade treino × score:** uma coluna de entrada com significado diferente entre `historico_enriquecido` e `sinistros_enriquecidos` (ex.: `lmi` preenchido sem cobertura no histórico e nulo no evento). Esperado: os mesmos nulos e unidades. Teste: `test_historico_e_evento_tem_as_mesmas_colunas_de_entrada` e as conferências da consulta 93.
2. **Vazamento de rótulo:** o SQL do histórico ou o notebook usando `decisao_final`, `valor_pago`, `motivo_decisao`, `padrao` ou `preexistente`. Teste: `test_historico_nao_le_colunas_que_vazam_o_rotulo` e a checagem de colunas em `montar_features`.
3. **Entrada do modelo servido com nulos e tipos do Spark** (inteiro com nulo vira float; booleano nulo; categoria desconhecida). Esperado: sem erro, com score. Teste: `test_modelo_salvo_carrega_e_pontua_entrada_com_nulos`.
4. **Promoção sobre champion inexistente ou empate de AUC.** Esperado: a primeira versão vira `champion`; um empate não promove. Teste: `test_decidir_promocao`.
5. **Participação do prestador com janela pequena ou vazia** (início do histórico e do evento). Esperado: nula, nunca 100%. Teste estático das constantes no SQL e conferência na consulta 93.

---

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/regras/features.py` (novo) | Colunas de entrada, `montar_features`, `rotulo_suspeito`, rótulos em português, `principais_fatores` |
| `src/ml/__init__.py`, `src/ml/treino.py` (novos) | Split temporal, parâmetros, treino, métricas, recall por padrão, contribuições SHAP, portão de promoção e assinatura |
| `src/ml/modelo_pyfunc.py` (novo) | Modelo MLflow *models from code* (`ModeloSuspeita`): score e principais fatores |
| `src/pipeline/silver_clima.py` (alterado) | Evidência do histórico com a mesma função do evento |
| `src/pipeline/silver_historico.sql` (novo) | MV `historico_enriquecido` |
| `src/pipeline/silver_sinistros.sql` (alterado) | `menciona_dano_anterior` e `participacao_prestador_30d` |
| `src/governanca/93_conferir_features.sql` (novo) | Conferência das features do histórico e do evento contra os gabaritos |
| `notebooks/treino_modelo_suspeita.py` (novo) | Notebook de treino (formato source) |
| `recursos/job_treino_modelo.yml` (novo) | Job serverless e experimento MLflow |
| `scripts/exportar_execucao.py` (novo) | Converte a execução de um notebook de job em `.ipynb` com as saídas em texto |
| `scripts/evidencia_modelo.py` (novo) | Gera `evidencias/04-ml.md` com o run do MLflow, a versão do modelo e os aliases |
| `testes/test_features.py`, `testes/test_treino.py`, `testes/test_modelo_pyfunc.py`, `testes/test_exportar_execucao.py` (novos), `testes/test_pipeline_sql.py` (alterado) | Testes |
| `pyproject.toml` | Pacote `src/ml` no wheel; grupo `ml` (lightgbm, scikit-learn, mlflow, matplotlib) no padrão do `uv run` |

---

### Task 3.1: features compartilhadas

**Files:** criar `src/regras/features.py` e `testes/test_features.py`.

**Interfaces (produz):**
- `COLUNAS_ENTRADA: list[str]`, `COLUNAS_CLIMA_BRUTO: list[str]`, `FEATURES: list[str]`, `CATEGORIAS: dict[str, list[str]]`
- `COLUNAS_PROIBIDAS: frozenset[str]`, `JANELA_PRESTADOR_DIAS = 30`, `MIN_AVISOS_JANELA_PRESTADOR = 200`
- `rotulo_suspeito(padrao: pd.Series) -> pd.Series[int]`
- `montar_features(df: pd.DataFrame, com_clima_bruto: bool = False) -> pd.DataFrame` (colunas na ordem de `FEATURES`, mais `COLUNAS_CLIMA_BRUTO` se pedido)
- `ROTULOS: dict[str, str]`, `principais_fatores(contribuicoes: np.ndarray, nomes: list[str], k: int = 3) -> list[str]`

- [ ] **Passo 1: testes (RED)**

```python
# testes/test_features.py
import numpy as np
import pandas as pd
import pytest

from regras.features import (CATEGORIAS, COLUNAS_ENTRADA, COLUNAS_PROIBIDAS, FEATURES, montar_features,
                             principais_fatores, rotulo_suspeito)


def _entrada(**kw):
    base = {"valor_reclamado": 4000.0, "lmi": 80000.0, "desvio_preco_pct": 0.05, "dias_desde_contratacao": 200,
            "forca_evidencia_climatica": "forte", "cobertura_valida": True, "menciona_dano_anterior": False,
            "participacao_prestador_30d": 0.0005, "causa_declarada": "granizo", "ramo": "residencial"}
    return pd.DataFrame([base | kw])


def test_rotulo_suspeito_so_legitimos_sao_zero():
    s = rotulo_suspeito(pd.Series(["legitimo_simples", "legitimo_complexo", "orcamento_inflado", "sem_cobertura"]))
    assert s.tolist() == [0, 0, 1, 1]


def test_rotulo_suspeito_recusa_padrao_nulo():
    with pytest.raises(ValueError):
        rotulo_suspeito(pd.Series(["legitimo_simples", None]))


def test_features_na_ordem_e_sem_colunas_proibidas():
    X = montar_features(_entrada())
    assert list(X.columns) == FEATURES
    assert not (set(X.columns) | set(COLUNAS_ENTRADA)) & COLUNAS_PROIBIDAS


def test_features_traduzem_evidencia_e_razoes():
    X = montar_features(pd.concat([_entrada(forca_evidencia_climatica=f) for f in ("contraria", "fraca", "forte", "outra")]))
    assert X["evidencia_climatica"].tolist()[:3] == [0.0, 1.0, 2.0] and np.isnan(X["evidencia_climatica"].iloc[3])
    assert X["razao_valor_lmi"].iloc[0] == pytest.approx(0.05)


def test_sem_cobertura_tem_lmi_nulo_e_razao_nula():
    X = montar_features(_entrada(cobertura_valida=False, lmi=None))
    assert X["cobertura_valida"].iloc[0] == 0.0 and np.isnan(X["razao_valor_lmi"].iloc[0])


def test_nulos_e_categoria_desconhecida_nao_quebram():
    X = montar_features(_entrada(menciona_dano_anterior=None, cobertura_valida=None, causa_declarada="incendio",
                                 participacao_prestador_30d=None, dias_desde_contratacao=None, lmi=0.0))
    assert X["menciona_dano_anterior"].iloc[0] == 0.0 and X["cobertura_valida"].iloc[0] == 0.0
    assert pd.isna(X["causa_declarada"].iloc[0]) and np.isnan(X["razao_valor_lmi"].iloc[0])
    assert list(X["causa_declarada"].cat.categories) == CATEGORIAS["causa_declarada"]


def test_coluna_de_entrada_ausente_falha_com_o_nome():
    with pytest.raises(KeyError, match="desvio_preco_pct"):
        montar_features(_entrada().drop(columns=["desvio_preco_pct"]))


def test_clima_bruto_so_quando_pedido():
    df = _entrada().assign(chuva_mm=12.0, chuva_max_hora_mm=8.0, rajada_max_ms=20.0, distancia_estacao_km=7.0)
    assert "rajada_max_ms" not in montar_features(df).columns
    assert montar_features(df, com_clima_bruto=True)["rajada_max_ms"].iloc[0] == 20.0


def test_principais_fatores_so_os_que_aumentam_a_suspeita():
    nomes = ["desvio_preco_pct", "dias_desde_contratacao", "evidencia_climatica", "ramo"]
    fatores = principais_fatores(np.array([2.0, -1.0, 0.5, 0.0]), nomes, k=3)
    assert fatores == ["Preço acima da tabela de referência", "Evidência climática fraca ou contrária"]
```

Run: `uv run pytest testes/test_features.py -q`. Esperado: FAIL (módulo inexistente).

- [ ] **Passo 2: implementação**

```python
# src/regras/features.py
"""Features do modelo de suspeita, iguais no treino (histórico 2025) e no score (evento 2026).

As colunas de entrada existem com o mesmo nome e significado em silver.historico_enriquecido e em
silver.sinistros_enriquecidos (mesmas regras do pipeline). Aqui elas viram a matriz do modelo. Nada aqui lê o gabarito.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

JANELA_PRESTADOR_DIAS = 30  # participação do prestador nos 30 dias anteriores ao aviso (point-in-time; D-020/D-021)
MIN_AVISOS_JANELA_PRESTADOR = 200  # abaixo disso a proporção é ruído (início do histórico ou do evento) e fica nula

COLUNAS_ENTRADA = ["valor_reclamado", "lmi", "desvio_preco_pct", "dias_desde_contratacao", "forca_evidencia_climatica",
                   "cobertura_valida", "menciona_dano_anterior", "participacao_prestador_30d", "causa_declarada", "ramo"]
# Fora do modelo principal (D-021): no histórico, sem Defesa Civil, o clima bruto se confunde com a fonte da evidência
COLUNAS_CLIMA_BRUTO = ["chuva_mm", "chuva_max_hora_mm", "rajada_max_ms", "distancia_estacao_km"]
CATEGORIAS = {"causa_declarada": ["granizo", "vendaval", "alagamento", "danos_eletricos"],
              "ramo": ["residencial", "empresarial"]}
ORDEM_EVIDENCIA = {"contraria": 0.0, "fraca": 1.0, "forte": 2.0}
FEATURES = ["log_valor_reclamado", "razao_valor_lmi", "desvio_preco_pct", "dias_desde_contratacao", "evidencia_climatica",
            "cobertura_valida", "menciona_dano_anterior", "participacao_prestador_30d", "causa_declarada", "ramo"]
# Vazam o rótulo: nunca entram como feature (histórico: decisão e pagamento; itens: preexistente; evento: gabarito)
COLUNAS_PROIBIDAS = frozenset({"decisao_final", "valor_pago", "motivo_decisao", "padrao", "preexistente",
                               "decisao_esperada", "valor_devido", "motivo", "suspeito"})

ROTULOS = {
    "log_valor_reclamado": "Valor reclamado alto",
    "razao_valor_lmi": "Valor próximo do limite da cobertura (LMI)",
    "desvio_preco_pct": "Preço acima da tabela de referência",
    "dias_desde_contratacao": "Apólice contratada há pouco tempo",
    "evidencia_climatica": "Evidência climática fraca ou contrária",
    "cobertura_valida": "Causa sem cobertura contratada",
    "menciona_dano_anterior": "Laudo menciona dano anterior ao evento",
    "participacao_prestador_30d": "Prestador com concentração atípica de orçamentos",
    "causa_declarada": "Causa declarada",
    "ramo": "Ramo da apólice",
    "chuva_mm": "Chuva no dia", "chuva_max_hora_mm": "Chuva máxima em uma hora",
    "rajada_max_ms": "Rajada máxima", "distancia_estacao_km": "Distância até a estação",
}


def rotulo_suspeito(padrao: pd.Series) -> pd.Series:
    """1 para todo padrão diferente de legitimo_* (spec 6.1). Padrão nulo é erro: o rótulo não pode ser inventado."""
    if padrao.isna().any():
        raise ValueError(f"{int(padrao.isna().sum())} sinistro(s) sem padrão no gabarito")
    return (~padrao.astype(str).str.startswith("legitimo_")).astype(int)


def _numero(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)


def _booleano(s: pd.Series) -> pd.Series:
    """Booleano do Spark (True/False/None) como 1.0/0.0; nulo conta como 0 (sem cobertura, sem menção)."""
    return s.map(lambda v: 1.0 if v is True or v == 1 or (isinstance(v, str) and v.lower() == "true") else 0.0).astype(float)


def montar_features(df: pd.DataFrame, com_clima_bruto: bool = False) -> pd.DataFrame:
    colunas = COLUNAS_ENTRADA + (COLUNAS_CLIMA_BRUTO if com_clima_bruto else [])
    faltando = [c for c in colunas if c not in df.columns]
    if faltando:
        raise KeyError(f"colunas de entrada ausentes: {', '.join(faltando)}")
    valor, lmi = _numero(df["valor_reclamado"]), _numero(df["lmi"])
    X = pd.DataFrame(index=df.index)
    X["log_valor_reclamado"] = np.log1p(valor.clip(lower=0))
    X["razao_valor_lmi"] = valor / lmi.where(lmi > 0)
    X["desvio_preco_pct"] = _numero(df["desvio_preco_pct"])
    X["dias_desde_contratacao"] = _numero(df["dias_desde_contratacao"])
    X["evidencia_climatica"] = df["forca_evidencia_climatica"].map(ORDEM_EVIDENCIA).astype(float)
    X["cobertura_valida"] = _booleano(df["cobertura_valida"])
    X["menciona_dano_anterior"] = _booleano(df["menciona_dano_anterior"])
    X["participacao_prestador_30d"] = _numero(df["participacao_prestador_30d"])
    for coluna, categorias in CATEGORIAS.items():
        X[coluna] = pd.Categorical(df[coluna].where(df[coluna].isin(categorias)), categories=categorias)
    if com_clima_bruto:
        for coluna in COLUNAS_CLIMA_BRUTO:
            X[coluna] = _numero(df[coluna])
    return X


def principais_fatores(contribuicoes: np.ndarray, nomes: list[str], k: int = 3) -> list[str]:
    """Até k fatores que mais AUMENTAM a suspeita (contribuição SHAP > 0), em português, do maior para o menor."""
    ordem = np.argsort(-np.asarray(contribuicoes, dtype=float))
    return [ROTULOS.get(nomes[i], nomes[i]) for i in ordem[:k] if contribuicoes[i] > 0]
```

- [ ] **Passo 3:** `uv run pytest testes/test_features.py -q` → PASS. Commit: `feat: features do modelo de suspeita compartilhadas pelo treino e pelo score`.

### Task 3.2: treino, métricas, promoção e modelo MLflow

**Files:** criar `src/ml/__init__.py`, `src/ml/treino.py`, `src/ml/modelo_pyfunc.py`, `testes/test_treino.py` e `testes/test_modelo_pyfunc.py`; alterar `pyproject.toml`.

**Interfaces (produz):**
- `CORTE_TESTE = "2025-10-01"`, `LIMIAR_FAST_TRACK = 0.2`, `FRACAO_TOPO = 0.10`, `PARAMS_LGBM: dict`
- `dividir_temporal(df, coluna="data_aviso", corte=CORTE_TESTE) -> tuple[pd.DataFrame, pd.DataFrame]` (falha se algum lado ficar vazio)
- `treinar(X, y, params=PARAMS_LGBM) -> lgb.LGBMClassifier`
- `metricas(y, score, prefixo="") -> dict[str, float]` (chaves: `auc`, `ap`, `precisao_top10`, `recall_top10`, `suspeitos_abaixo_limiar`, `legitimos_abaixo_limiar`, `n`, `n_suspeitos`)
- `por_padrao(padrao, score) -> pd.DataFrame` (colunas `padrao`, `n`, `score_mediano`, `pct_acima_limiar`)
- `contribuicoes(booster, X) -> pd.DataFrame` (colunas = `X.columns` + `base`)
- `decidir_promocao(auc_novo: float, auc_champion: float | None) -> str` (`"champion"` ou `"challenger"`)
- `assinatura() -> mlflow.models.ModelSignature`
- Modelo pyfunc: entrada `COLUNAS_ENTRADA` (+ clima bruto se configurado); saída `score_suspeita` (double) e `fatores_suspeita` (string, separada por `"; "`). Artefatos: `booster` (texto do LightGBM) e `config` (JSON com `features` e `com_clima_bruto`).

- [ ] **Passo 1: pyproject.** Grupo `ml = ["lightgbm>=4.5", "scikit-learn>=1.5", "mlflow>=3.1", "matplotlib>=3.9"]` (sem `shap`; D-021), `[tool.uv] default-groups = ["dev", "ml"]` e `packages` com `"src/ml"`. `uv sync`.
- [ ] **Passo 2: testes (RED)**

```python
# testes/test_treino.py
import numpy as np
import pandas as pd
import pytest

from ml.treino import (LIMIAR_FAST_TRACK, contribuicoes, decidir_promocao, dividir_temporal, metricas, por_padrao,
                       treinar)
from regras.features import montar_features


def test_dividir_temporal_corta_por_data_aviso():
    df = pd.DataFrame({"data_aviso": pd.to_datetime(["2025-09-30", "2025-10-01", "2025-12-31"]).date})
    treino, teste = dividir_temporal(df)
    assert len(treino) == 1 and len(teste) == 2


def test_dividir_temporal_falha_se_um_lado_ficar_vazio():
    with pytest.raises(ValueError):
        dividir_temporal(pd.DataFrame({"data_aviso": pd.to_datetime(["2025-01-02"]).date}))


def test_metricas_topo_e_limiar():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0] * 10)
    score = np.where(y == 1, 0.9, 0.1)
    score[0] = 0.15  # um suspeito escaparia do bloqueio do fast track
    m = metricas(y, score)
    assert m["precisao_top10"] == 1.0 and m["recall_top10"] == pytest.approx(10 / 20)
    assert m["suspeitos_abaixo_limiar"] == pytest.approx(1 / 20) and m["legitimos_abaixo_limiar"] == 1.0
    assert 0.97 < m["auc"] <= 1.0 and m["n"] == 100 and m["n_suspeitos"] == 20


def test_metricas_com_prefixo():
    assert "teste_auc" in metricas(np.array([0, 1]), np.array([0.1, 0.9]), prefixo="teste_")


def test_por_padrao():
    t = por_padrao(pd.Series(["a", "a", "b"]), np.array([0.1, 0.9, 0.5]))
    a = t.set_index("padrao").loc["a"]
    assert a.n == 2 and a.pct_acima_limiar == 50.0 and LIMIAR_FAST_TRACK == 0.2


@pytest.mark.parametrize("novo, atual, esperado", [(0.9, None, "champion"), (0.91, 0.90, "champion"),
                                                     (0.90, 0.90, "challenger"), (0.80, 0.90, "challenger")])
def test_decidir_promocao(novo, atual, esperado):
    assert decidir_promocao(novo, atual) == esperado


def _dados(n=400, seed=0):
    rng = np.random.default_rng(seed)
    suspeito = rng.random(n) < 0.2
    df = pd.DataFrame({
        "valor_reclamado": rng.uniform(1000, 30000, n), "lmi": 100000.0,
        "desvio_preco_pct": np.where(suspeito, rng.uniform(0.4, 1.2, n), rng.uniform(-0.1, 0.15, n)),
        "dias_desde_contratacao": rng.integers(30, 330, n), "forca_evidencia_climatica": "forte",
        "cobertura_valida": True, "menciona_dano_anterior": False, "participacao_prestador_30d": 0.0005,
        "causa_declarada": "granizo", "ramo": "residencial"})
    return df, suspeito.astype(int)


def test_treinar_separa_sinal_claro_e_contribuicoes_somam_o_logito():
    df, y = _dados()
    X = montar_features(df)
    modelo = treinar(X, y)
    m = metricas(y, modelo.predict_proba(X)[:, 1])
    assert m["auc"] > 0.95
    c = contribuicoes(modelo.booster_, X)
    assert list(c.columns) == list(X.columns) + ["base"]
    logito = modelo.booster_.predict(X, raw_score=True)
    assert np.allclose(c.sum(axis=1).to_numpy(), logito)
```

```python
# testes/test_modelo_pyfunc.py
import json
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

import ml
import regras
from ml.treino import assinatura, treinar
from regras.features import COLUNAS_ENTRADA, FEATURES, montar_features
from test_treino import _dados


def _salvar(tmp_path: Path) -> str:
    df, y = _dados()
    modelo = treinar(montar_features(df), y)
    booster = tmp_path / "booster.txt"
    modelo.booster_.save_model(str(booster))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"features": FEATURES, "com_clima_bruto": False}))
    destino = tmp_path / "modelo"
    mlflow.pyfunc.save_model(
        path=str(destino), python_model=str(Path(ml.__file__).with_name("modelo_pyfunc.py")),
        artifacts={"booster": str(booster), "config": str(config)},
        code_paths=[str(Path(regras.__file__).parent)], signature=assinatura())
    return str(destino)


def test_modelo_salvo_carrega_e_pontua_entrada_com_nulos(tmp_path):
    carregado = mlflow.pyfunc.load_model(_salvar(tmp_path))
    entrada = pd.DataFrame({
        "valor_reclamado": [4000.0, 25000.0, 3000.0], "lmi": [80000.0, None, 50000.0],
        "desvio_preco_pct": [0.02, 0.9, None], "dias_desde_contratacao": [200.0, 5.0, None],
        "forca_evidencia_climatica": ["forte", "contraria", None], "cobertura_valida": [True, False, None],
        "menciona_dano_anterior": [False, True, None], "participacao_prestador_30d": [0.0005, None, 0.003],
        "causa_declarada": ["granizo", "vendaval", "incendio"], "ramo": ["residencial", "empresarial", None]})
    saida = carregado.predict(entrada[COLUNAS_ENTRADA])
    assert list(saida.columns) == ["score_suspeita", "fatores_suspeita"]
    assert saida["score_suspeita"].between(0, 1).all() and len(saida) == 3
    assert saida["score_suspeita"].iloc[1] > saida["score_suspeita"].iloc[0]
    assert "Preço acima da tabela de referência" in saida["fatores_suspeita"].iloc[1]


def test_modelo_aceita_dias_inteiros_como_vem_do_spark(tmp_path):
    carregado = mlflow.pyfunc.load_model(_salvar(tmp_path))
    df, _ = _dados(n=5)
    saida = carregado.predict(df.assign(dias_desde_contratacao=df["dias_desde_contratacao"].astype("int32"))[COLUNAS_ENTRADA])
    assert saida["score_suspeita"].notna().all() and np.isfinite(saida["score_suspeita"]).all()
```

Run: `uv run pytest testes/test_treino.py testes/test_modelo_pyfunc.py -q`. Esperado: FAIL (módulos inexistentes).

- [ ] **Passo 3: implementação de `src/ml/treino.py`**

```python
"""Treino, métricas e portão de promoção do modelo de suspeita (pandas, LightGBM e MLflow; roda no job e nos testes)."""
from __future__ import annotations

import math
from datetime import date

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

CORTE_TESTE = "2025-10-01"  # treino: jan–set/2025; teste: out–dez/2025 (split temporal)
LIMIAR_FAST_TRACK = 0.2  # spec 6.3: score abaixo disso é condição do fast track
FRACAO_TOPO = 0.10  # spec 6.1: precisão e recall nos 10% mais suspeitos
PARAMS_LGBM = dict(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=30, subsample=0.8,
                   subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=42, verbose=-1)


def dividir_temporal(df: pd.DataFrame, coluna: str = "data_aviso", corte: str = CORTE_TESTE):
    datas = pd.to_datetime(df[coluna])
    treino, teste = df[datas < pd.Timestamp(corte)], df[datas >= pd.Timestamp(corte)]
    if treino.empty or teste.empty:
        raise ValueError(f"split temporal vazio: treino={len(treino)}, teste={len(teste)} (corte {corte})")
    return treino, teste


def treinar(X: pd.DataFrame, y, params: dict = PARAMS_LGBM) -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(**params).fit(X, np.asarray(y))


def metricas(y, score, prefixo: str = "") -> dict[str, float]:
    y, score = np.asarray(y).astype(int), np.asarray(score, dtype=float)
    k = max(1, math.ceil(FRACAO_TOPO * len(y)))
    topo = np.argsort(-score, kind="stable")[:k]
    n_susp = int(y.sum())
    abaixo = score < LIMIAR_FAST_TRACK
    m = {
        "auc": float(roc_auc_score(y, score)) if 0 < n_susp < len(y) else float("nan"),
        "ap": float(average_precision_score(y, score)) if n_susp else float("nan"),
        "precisao_top10": float(y[topo].mean()),
        "recall_top10": float(y[topo].sum() / n_susp) if n_susp else float("nan"),
        "suspeitos_abaixo_limiar": float(abaixo[y == 1].mean()) if n_susp else float("nan"),
        "legitimos_abaixo_limiar": float(abaixo[y == 0].mean()) if n_susp < len(y) else float("nan"),
        "n": float(len(y)), "n_suspeitos": float(n_susp),
    }
    return {f"{prefixo}{c}": v for c, v in m.items()}


def por_padrao(padrao: pd.Series, score) -> pd.DataFrame:
    t = pd.DataFrame({"padrao": np.asarray(padrao), "score": np.asarray(score, dtype=float)})
    return (t.groupby("padrao")
            .agg(n=("score", "size"), score_mediano=("score", "median"),
                 pct_acima_limiar=("score", lambda s: round(100 * float((s >= LIMIAR_FAST_TRACK).mean()), 1)))
            .reset_index().sort_values("padrao"))


def contribuicoes(booster: lgb.Booster, X: pd.DataFrame) -> pd.DataFrame:
    """Valores SHAP exatos (TreeSHAP do próprio LightGBM), na escala do logito; a última coluna é o valor base."""
    return pd.DataFrame(booster.predict(X, pred_contrib=True), columns=[*X.columns, "base"], index=X.index)


def decidir_promocao(auc_novo: float, auc_champion: float | None) -> str:
    """Spec 6.1: só vira champion com AUC MAIOR que o do champion atual no mesmo teste; a primeira versão é champion."""
    return "champion" if auc_champion is None or auc_novo > auc_champion else "challenger"


def assinatura(com_clima_bruto: bool = False):
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema

    from regras.features import COLUNAS_CLIMA_BRUTO

    tipos = {"forca_evidencia_climatica": "string", "causa_declarada": "string", "ramo": "string",
             "cobertura_valida": "boolean", "menciona_dano_anterior": "boolean"}
    from regras.features import COLUNAS_ENTRADA
    colunas = COLUNAS_ENTRADA + (COLUNAS_CLIMA_BRUTO if com_clima_bruto else [])
    entrada = Schema([ColSpec(tipos.get(c, "double"), c, required=False) for c in colunas])
    saida = Schema([ColSpec("double", "score_suspeita"), ColSpec("string", "fatores_suspeita")])
    return ModelSignature(inputs=entrada, outputs=saida)


def hoje() -> str:
    return date.today().isoformat()
```

(Na implementação, os imports de `regras.features` ficam no topo da função, juntos; o `hoje()` só existe se for usado no notebook.)

- [ ] **Passo 4: implementação de `src/ml/modelo_pyfunc.py`** (*models from code*, logado como arquivo)

```python
"""Modelo MLflow do score de suspeita (models from code): booster LightGBM + features compartilhadas (regras).

Entrada: as colunas de regras.features.COLUNAS_ENTRADA, como estão em silver.sinistros_enriquecidos.
Saída: score_suspeita (0 a 1) e fatores_suspeita (até 3 fatores que mais aumentam a suspeita, em português).
"""
import json

import mlflow
import pandas as pd
from mlflow.pyfunc import PythonModel


class ModeloSuspeita(PythonModel):
    def load_context(self, context):
        import lightgbm as lgb

        self.booster = lgb.Booster(model_file=context.artifacts["booster"])
        with open(context.artifacts["config"], encoding="utf-8") as f:
            self.config = json.load(f)

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        from regras.features import montar_features, principais_fatores

        X = montar_features(model_input, com_clima_bruto=self.config["com_clima_bruto"])[self.config["features"]]
        score = self.booster.predict(X)
        contrib = self.booster.predict(X, pred_contrib=True)[:, :-1]
        nomes = list(X.columns)
        fatores = ["; ".join(principais_fatores(linha, nomes)) for linha in contrib]
        return pd.DataFrame({"score_suspeita": score.astype(float), "fatores_suspeita": fatores})


mlflow.models.set_model(ModeloSuspeita())
```

`config["features"]` guarda a ordem das colunas usada no treino, incluindo as de clima bruto quando houver.

- [ ] **Passo 5:** `uv run pytest -q` → toda a suíte PASS. Se a imposição de schema do MLflow recusar inteiros em coluna `double`, declarar `dias_desde_contratacao` como `long` não resolve, porque um inteiro com nulo chega como float; nesse caso, converter para `float` antes do `predict` no lado do score e manter `double`. Registrar a decisão no ledger. Commit: `feat: treino, métricas, portão de promoção e modelo MLflow do score de suspeita`.

### Task 3.3: features do histórico e do evento no pipeline

**Files:** alterar `src/pipeline/silver_clima.py` e `src/pipeline/silver_sinistros.sql`; criar `src/pipeline/silver_historico.sql` e `src/governanca/93_conferir_features.sql`; alterar `testes/test_pipeline_sql.py`.

**Interfaces:**
- **Consome:** `calcular_evidencia_grupo` e `ESQUEMA_EVIDENCIA` (regras.sinistro), `JANELA_DIAS`, e as constantes de 3.1.
- **Produz:**
  - `silver.evidencia_climatica_historico` (`id_sinistro` mais as colunas de `ESQUEMA_EVIDENCIA`, sem `id_aviso`);
  - `silver.historico_enriquecido`, com `id_sinistro`, `data_ocorrencia`, `data_aviso`, `COLUNAS_ENTRADA`, `COLUNAS_CLIMA_BRUTO`, `canal`, `municipio`, `codigo_ibge`, `id_prestador`, `itens`, `itens_casados` e `fonte_evidencia`;
  - em `sinistros_enriquecidos`, as colunas novas `menciona_dano_anterior BOOLEAN` e `participacao_prestador_30d DOUBLE`.

- [ ] **Passo 1: testes estáticos (RED)** em `testes/test_pipeline_sql.py`:

```python
def _colunas_do_select_final(sql: str) -> str:
    return sql[sql.rindex("SELECT"):]


def test_historico_e_evento_tem_as_mesmas_colunas_de_entrada():
    from regras.features import COLUNAS_CLIMA_BRUTO, COLUNAS_ENTRADA
    for nome in ("silver_historico.sql", "silver_sinistros.sql"):
        final = _colunas_do_select_final(_sql(nome))
        for coluna in COLUNAS_ENTRADA + COLUNAS_CLIMA_BRUTO:
            assert re.search(rf"\b{coluna}\b", final), (nome, coluna)


def test_historico_nao_le_colunas_que_vazam_o_rotulo():
    texto = _sql("silver_historico.sql")
    for proibida in ("decisao_final", "valor_pago", "motivo_decisao", "padrao", "gabarito"):
        assert proibida not in texto, proibida
    assert not re.search(r"\bpreexistente\b", texto)  # só menciona_preexistente (o laudo), nunca o item marcado


def test_participacao_do_prestador_e_point_in_time_nos_dois_lados():
    from regras.features import JANELA_PRESTADOR_DIAS, MIN_AVISOS_JANELA_PRESTADOR
    for nome in ("silver_historico.sql", "silver_sinistros.sql"):
        texto = _sql(nome)
        assert f"date_sub(k.data_aviso, {JANELA_PRESTADOR_DIAS})" in texto and "< k.data_aviso" in texto, nome
        assert f">= {MIN_AVISOS_JANELA_PRESTADOR}" in texto, nome


def test_desvio_de_preco_usa_a_mesma_chave_nos_dois_lados():
    chave = "lower(regexp_replace(trim(descricao), '\\\\s+', ' '))"
    assert chave in _sql("silver_documentos.sql") and chave in _sql("silver_historico.sql")
```

Acrescentar `"silver_historico.sql"` ao conjunto de `test_pipeline_tem_bronze_e_silver`. Run → FAIL.

- [ ] **Passo 2: `silver_clima.py`.** Extrair o corpo de `evidencia_climatica()` para `_evidencia(avisos)`, que recebe colunas `id_aviso, codigo_ibge, lat, lon, data_ocorrencia, causa_declarada` e devolve o resultado de `applyInPandas`. A MV do evento chama `_evidencia(avisos)`. A nova MV:

```python
@dp.materialized_view(name=f"{SILVER}.evidencia_climatica_historico",
                      comment="Evidência climática dos sinistros de 2025 (base de treino), pela mesma regra do evento.")
def evidencia_climatica_historico():
    hist = spark.read.table(f"{BRONZE}.historico_sinistros").select(  # noqa: F821
        F.col("id_sinistro").alias("id_aviso"), F.col("codigo_ibge").cast("int").alias("codigo_ibge"),
        F.col("lat").cast("double").alias("lat"), F.col("lon").cast("double").alias("lon"),
        F.to_date("data_ocorrencia").alias("data_ocorrencia"), "causa_declarada")
    return _evidencia(hist).withColumnRenamed("id_aviso", "id_sinistro")
```

Não há Defesa Civil em 2025, e o join com as ocorrências de 2026 não casa datas de 2025, então `registro_defesa_civil` fica falso pela mesma regra. Não há caso especial.

- [ ] **Passo 3: `silver_historico.sql`**

```sql
-- Silver: sinistros regulados em 2025 (base de treino do modelo de suspeita), com as MESMAS colunas de entrada do
-- evento (silver.sinistros_enriquecidos) e pelas mesmas regras. Decisão, valor pago e motivo ficam de fora (vazam o rótulo).
CREATE OR REFRESH MATERIALIZED VIEW ${catalogo}.${schema_silver}.historico_enriquecido
COMMENT 'Histórico 2025 enriquecido para o treino: mesmas features do evento (evidência, desvio de preço, prestador).'
AS WITH h AS (
  SELECT id_sinistro, to_date(data_ocorrencia) AS data_ocorrencia, to_date(data_aviso) AS data_aviso, causa_declarada,
    CAST(valor_reclamado AS DOUBLE) AS valor_reclamado, canal, CAST(codigo_ibge AS INT) AS codigo_ibge, municipio,
    id_prestador, ramo, CAST(cobertura_contratada AS BOOLEAN) AS cobertura_valida,
    -- como no evento: sem a cobertura da causa, não há LMI nem franquia (o join com a cobertura não casa)
    CASE WHEN CAST(cobertura_contratada AS BOOLEAN) THEN CAST(lmi_cobertura AS DOUBLE) END AS lmi,
    CASE WHEN CAST(cobertura_contratada AS BOOLEAN) THEN CAST(franquia AS DOUBLE) END AS franquia,
    datediff(to_date(data_ocorrencia), to_date(inicio_vigencia)) AS dias_desde_contratacao,
    -- no evento, o equivalente é o laudo lido por IA (menciona_dano_anterior)
    coalesce(CAST(menciona_preexistente AS BOOLEAN), false) AS menciona_dano_anterior
  FROM ${catalogo}.${schema_bronze}.historico_sinistros
),
precos AS (
  SELECT lower(regexp_replace(trim(descricao), '\\s+', ' ')) AS chave, CAST(preco_referencia AS DOUBLE) AS preco_referencia
  FROM ${catalogo}.${schema_bronze}.precos_referencia
),
desvio AS (
  SELECT i.id_sinistro, count(*) AS itens, count(p.preco_referencia) AS itens_casados,
    round(sum(CASE WHEN p.preco_referencia IS NOT NULL THEN CAST(i.quantidade AS DOUBLE) * CAST(i.valor_unitario AS DOUBLE) END)
          / sum(CAST(i.quantidade AS DOUBLE) * p.preco_referencia) - 1, 4) AS desvio_preco_pct
  FROM ${catalogo}.${schema_bronze}.historico_itens i
  LEFT JOIN precos p ON p.chave = lower(regexp_replace(trim(i.descricao), '\\s+', ' '))
  GROUP BY i.id_sinistro
),
-- Participação do prestador point-in-time (D-020/D-021): só avisos ANTERIORES ao dia do aviso, janela de 30 dias
dia_total AS (SELECT data_aviso AS dia, count(*) AS n FROM h GROUP BY data_aviso),
dia_prestador AS (SELECT id_prestador, data_aviso AS dia, count(*) AS n FROM h GROUP BY id_prestador, data_aviso),
janela_total AS (
  SELECT k.data_aviso, sum(t.n) AS avisos_janela
  FROM (SELECT DISTINCT data_aviso FROM h) k
  JOIN dia_total t ON t.dia >= date_sub(k.data_aviso, 30) AND t.dia < k.data_aviso
  GROUP BY k.data_aviso
),
janela_prestador AS (
  SELECT k.id_prestador, k.data_aviso, sum(p.n) AS avisos_prestador
  FROM (SELECT DISTINCT id_prestador, data_aviso FROM h) k
  JOIN dia_prestador p ON p.id_prestador = k.id_prestador AND p.dia >= date_sub(k.data_aviso, 30) AND p.dia < k.data_aviso
  GROUP BY k.id_prestador, k.data_aviso
)
SELECT h.id_sinistro, h.data_ocorrencia, h.data_aviso, h.causa_declarada, h.valor_reclamado, h.canal, h.codigo_ibge,
  h.municipio, h.id_prestador, h.ramo, h.cobertura_valida, h.lmi, h.franquia, h.dias_desde_contratacao,
  h.menciona_dano_anterior,
  coalesce(e.forca_evidencia_climatica, 'fraca') AS forca_evidencia_climatica,
  coalesce(e.fonte_evidencia, 'nenhuma') AS fonte_evidencia,
  e.distancia_estacao_km, e.chuva_mm, e.chuva_max_hora_mm, e.rajada_max_ms,
  d.itens, d.itens_casados, d.desvio_preco_pct,
  CASE WHEN jt.avisos_janela >= 200 THEN round(coalesce(jp.avisos_prestador, 0) / jt.avisos_janela, 6) END
    AS participacao_prestador_30d
FROM h
LEFT JOIN ${catalogo}.${schema_silver}.evidencia_climatica_historico e ON e.id_sinistro = h.id_sinistro
LEFT JOIN desvio d ON d.id_sinistro = h.id_sinistro
LEFT JOIN janela_total jt ON jt.data_aviso = h.data_aviso
LEFT JOIN janela_prestador jp ON jp.id_prestador = h.id_prestador AND jp.data_aviso = h.data_aviso;
```

- [ ] **Passo 4: `silver_sinistros.sql`.** Na CTE `juntos`, trocar a CTE `prestador` (a contagem continua sendo calculada) e adicionar as CTEs `dia_total`, `dia_prestador`, `janela_total` e `janela_prestador`, idênticas às do histórico, mas sobre `${catalogo}.${schema_silver}.avisos`. Em `juntos`, adicionar o LEFT JOIN de `janela_total` e `janela_prestador` por `data_aviso` e `id_prestador`. No SELECT final, adicionar, depois de `qtd_orcamentos_prestador`:

```sql
  coalesce(laudo_dano_anterior = 1, false) AS menciona_dano_anterior,
  CASE WHEN avisos_janela >= 200 THEN round(coalesce(avisos_prestador, 0) / avisos_janela, 6) END AS participacao_prestador_30d,
```

- [ ] **Passo 5: conferência `93_conferir_features.sql`.** Quatro consultas:
  1. Linhas por tabela (`historico_enriquecido` = 20.000 e `evidencia_climatica_historico` = 20.000).
  2. Histórico: por padrão (join com `gabarito_historico_2025.csv` **só na conferência**), n, % forte/fraca/contrária, desvio mediano, dias medianos, % sem cobertura, % com menção de dano anterior, participação mediana e % de participação nula.
  3. Evento (lote 1): as mesmas colunas por padrão, com `gabarito_evento_2026.csv`.
  4. Frescor e nulos: avisos e sinistros com `forca_evidencia_climatica` nula ou com `desvio_preco_pct` nulo.

Placeholders: `${catalogo}`, `${schema_silver}` e `${schema_ml}`, como no 91.

- [ ] **Passo 6: testes PASS e deploy.** Rodar `uv run pytest -q`. Depois `set -a; source .env; set +a`, `PKG=$(uv run python scripts/publicar_pacote.py)`, `databricks bundle deploy -t dev --var warehouse_id=$FE_BAR_WAREHOUSE_ID --var pacote_python=$PKG`, `databricks pipelines start-update <id> --validate-only` e, em seguida, `start-update` normal (sem full refresh: as MVs novas são criadas e as streaming tables não têm dado novo). Aguardar COMPLETED.
- [ ] **Passo 7: evidência.** `uv run python scripts/registrar_evidencia.py src/governanca/93_conferir_features.sql evidencias/04-ml-features.md "Features do modelo de suspeita: histórico 2025 e lote 1 do evento"`. Rodar também o 91 (frescor = 0, paridade 800/800), sem sobrescrever o 01 se nada mudou nele. Critérios de aceite:
  - `sem_evento_climatico` majoritariamente `contraria` nos dois lados;
  - `orcamento_inflado` com desvio mediano ≥ 0,3 nos dois lados;
  - `apolice_recente` com dias ≤ 10;
  - `sem_cobertura` 100% sem cobertura;
  - `dano_preexistente` com menção ≥ 90%;
  - `prestador_concentrado` com participação mediana maior que a dos legítimos.
  - Qualquer desvio: investigar (systematic-debugging) antes do treino.
  Commit: `feat: features point-in-time do histórico e do evento no pipeline, com conferência`.

### Task 3.4: notebook e job de treino

**Files:** criar `notebooks/treino_modelo_suspeita.py` e `recursos/job_treino_modelo.yml`; alterar `testes/test_pipeline_sql.py` (ou criar `testes/test_bundle_jobs.py`).

- [ ] **Passo 1: teste estático (RED)**, em `testes/test_bundle_jobs.py`: o YAML do job não contém `fe_bar_sinistros_catalog` nem `/Users/`; o experimento fica em `/Shared/${bundle.name}/${bundle.target}/`; as dependências contêm `--no-deps ${var.pacote_python}` e `lightgbm==4.7.0`; os parâmetros incluem `catalogo`, `schema_silver`, `schema_ml` e `experimento`; o notebook existe e termina com `dbutils.notebook.exit`.
- [ ] **Passo 2: `recursos/job_treino_modelo.yml`**

```yaml
# Job serverless de treino do modelo de suspeita (spec 6.1). Nomes vêm das variáveis do bundle (D-016).
resources:
  experiments:
    experimento_suspeita:
      name: /Shared/${bundle.name}/${bundle.target}/modelo_suspeita
  jobs:
    job_treino_modelo:
      name: sinistros_clima_treino_modelo
      max_concurrent_runs: 1
      tasks:
        - task_key: treino
          environment_key: ml
          notebook_task:
            notebook_path: ../notebooks/treino_modelo_suspeita.py
            base_parameters:
              catalogo: ${var.catalogo}
              schema_silver: ${var.prefixo_schema}silver
              schema_ml: ${var.prefixo_schema}ml
              experimento: ${resources.experiments.experimento_suspeita.name}
      environments:
        - environment_key: ml
          spec:
            environment_version: "4"
            dependencies:
              - --no-deps ${var.pacote_python}  # regras + ml (D-019)
              - lightgbm==4.7.0
              - mlflow>=3.1,<4
              - scikit-learn
              - matplotlib
```

Antes do primeiro deploy: `databricks workspace mkdirs /Shared/sinistros_clima/dev` (o experimento não cria a pasta-pai), documentado no README.

- [ ] **Passo 3: notebook** (formato source, células `# COMMAND ----------`), nesta ordem:
  1. **Markdown:** objetivo de negócio (priorizar a regulação e bloquear o fast track de casos suspeitos), dados, alvo e as decisões D-021.
  2. **Parâmetros:** `dbutils.widgets` (`catalogo`, `schema_silver`, `schema_ml`, `experimento`) e os nomes `SILVER`, `ML` e `NOME_MODELO = f"{catalogo}.{schema_ml}.modelo_suspeita"`. `VOLUME_RESTRITO = f"/Volumes/{catalogo}/{schema_ml}/restrito/gabarito"`.
  3. **Dados:** `historico_enriquecido` com `spark.table`; gabarito com `spark.read.csv(..., header=True)`; `join` por `id_sinistro`. Assert: toda linha com padrão (`rotulo_suspeito` falha se houver nulo) e 20.000 linhas. Checagem de colunas: `COLUNAS_ENTRADA + COLUNAS_CLIMA_BRUTO` ⊆ colunas das duas tabelas silver, e nenhuma de `COLUNAS_PROIBIDAS` usada em `montar_features` (assert sobre `FEATURES`).
  4. **`ml.features_treino`:** gravar (overwrite, `overwriteSchema`) `id_sinistro`, `data_aviso`, as colunas de entrada, o clima bruto, `padrao`, `suspeito` e `conjunto` (treino/teste). Ler a versão Delta com `DESCRIBE HISTORY ... LIMIT 1` e mostrar a distribuição por conjunto e padrão com `display()`.
  5. **Treino:**
     - `mlflow.set_registry_uri("databricks-uc")` e `set_experiment(experimento)`;
     - `with mlflow.start_run(run_name="lightgbm_sem_clima_bruto")`;
     - `log_params` (`PARAMS_LGBM`, corte, limiar, `FEATURES` e a versão da tabela);
     - `mlflow.log_input(mlflow.data.load_delta(table_name=..., version=v), context="treino")` e o mesmo com `context="teste"`;
     - treinar, `log_metrics` (`metricas(..., "treino_")` e `metricas(..., "teste_")`);
     - `por_padrao` do teste em `display()` e `log_table`.
  6. **Artefatos (matplotlib, `mlflow.log_figure`):** `curva_roc.png`, `curva_pr.png`, `matriz_confusao_limiar_0_2.png` e `shap_importancia.png` (média de |SHAP| por feature, a partir de `contribuicoes`). Mais `shap_dispersao.png` (para cada feature, pontos SHAP × valor normalizado, estilo beeswarm) e `shap_valores_teste.csv` (amostra de 500 linhas).
  7. **Modelo:**
     - salvar o booster em `/tmp/booster.txt` e o config em `/tmp/config.json`;
     - `mlflow.pyfunc.log_model(name="modelo", python_model=<ml/modelo_pyfunc.py do wheel>, artifacts=..., code_paths=[<pasta de regras>], signature=assinatura(), input_example=<5 linhas do teste>, pip_requirements=[mlflow, lightgbm, pandas, numpy com as versões do ambiente], registered_model_name=NOME_MODELO)`;
     - validar recarregando com `mlflow.pyfunc.load_model(models:/NOME@versão)` e conferir que o score bate com o do booster (`np.allclose`).
  8. **Checagem fora do tempo (lote 1):** `sinistros_enriquecidos` com `gabarito_evento_2026.csv`; pontuar com o modelo **carregado do UC**; `metricas(..., "evento_")` e `por_padrao` do evento; amostra de 5 sinistros com o score e os fatores.
  9. **Ablação (run aninhado `ablacao_com_clima_bruto`, sem registro):** treinar com `com_clima_bruto=True`, logar `teste_*` e `evento_*` e mostrar a comparação lado a lado com o modelo principal.
  10. **Promoção:**
      - se houver `champion`, carregar a versão dele e calcular o AUC no mesmo teste;
      - `decidir_promocao`, `set_registered_model_alias` para o alias decidido;
      - tags da versão (`auc_teste`, `corte_teste`, `features_versao_delta`, `decisao`) e descrição do modelo registrado e da versão, em português.
  11. **`dbutils.notebook.exit(json.dumps({...}))`:** `versao`, `alias`, `run_id`, `teste_auc`, `teste_precisao_top10`, `teste_recall_top10`, `teste_suspeitos_abaixo_limiar`, `evento_auc`, `evento_suspeitos_abaixo_limiar`, `ablacao_evento_auc` e `features_versao_delta`.
- [ ] **Passo 4:** rodar `uv run pytest -q`. Depois `databricks bundle validate`, o deploy (mesmo comando da 3.3) e `databricks bundle run -t dev job_treino_modelo`, aguardando o fim. Se falhar, ler o erro com `databricks jobs get-run-output <task_run_id>` e corrigir (systematic-debugging). Registrar cada ruling no ledger.
- [ ] **Passo 5: aceite.**
  - `teste_auc` ≥ 0,90 e `teste_suspeitos_abaixo_limiar` ≤ 0,10;
  - `evento_auc` ≥ 0,85 no lote 1;
  - alias `champion` na versão 1;
  - o score do modelo carregado do UC bate com o do booster.
  - Se o evento ficar muito abaixo do teste, analisar a deriva por feature antes de seguir.
  Commit: `feat: job serverless de treino do modelo de suspeita com MLflow e registro no UC`.

### Task 3.5: evidências, exportação do notebook e documentação

**Files:** criar `scripts/exportar_execucao.py`, `testes/test_exportar_execucao.py`, `scripts/evidencia_modelo.py`, `notebooks/saidas/treino_modelo_suspeita.ipynb` e `evidencias/04-ml.md`; alterar `README.md`, `docs/decisoes-e-tradeoffs.md`, `docs/planos/2026-11-20-roadmap.md` e a memória.

- [ ] **Passo 1: descobrir o formato.** Rodar `databricks jobs export-run <task_run_id> --views-to-export CODE -o json` e localizar no HTML o modelo do notebook (`__DATABRICKS_NOTEBOOK_MODEL`, base64 de JSON com URL-encoding). Conferir a estrutura de `commands[]` (`command` e `results` com `type` e `data`).
- [ ] **Passo 2: teste (RED)** com uma fixture mínima montada no próprio teste: um HTML com o modelo codificado, com uma célula markdown, uma célula de código com saída de texto e uma com tabela. Esperado:
  - o `.ipynb` (nbformat 4, JSON puro) tem as células na ordem;
  - a markdown vem sem o prefixo `%md`;
  - a saída de texto vem como `stream`;
  - a tabela vem como `text/plain` em Markdown;
  - nenhuma saída tem imagem em base64 (as imagens são substituídas por uma linha "[imagem: ver artefatos do MLflow]").
- [ ] **Passo 3: implementação** `scripts/exportar_execucao.py <task_run_id> <saida.ipynb>`, só com a biblioteca padrão e o `databricks-sdk` (`w.jobs.export_run`). Depois, PASS.
- [ ] **Passo 4:** `scripts/evidencia_modelo.py <task_run_id>` → `evidencias/04-ml.md` com:
  - a saída do notebook (`exit`);
  - os parâmetros e as métricas do run (MLflow, tabela);
  - a lista de artefatos;
  - a versão, os aliases e as tags do modelo no UC;
  - os inputs logados (nome da tabela e versão).
  Tudo renderizado com funções puras, testadas com dicionários de exemplo em `testes/test_evidencia_modelo.py`.
- [ ] **Passo 5:** gerar os dois arquivos. Copiar o notebook source para o `.py` em `notebooks/` (já é a fonte) e o `.ipynb` para `notebooks/saidas/`. Conferir que não há token, e-mail nem caminho `/Users/` nas saídas (grep).
- [ ] **Passo 6: documentação.**
  - **D-021** em `docs/decisoes-e-tradeoffs.md`: as 6 decisões deste plano mais os rulings da execução, com os resultados reais.
  - **README:** linha da fase 3 no status e estrutura (`src/ml/`, `notebooks/`), mais o comando do job e do `mkdirs`.
  - **Roadmap:** fase 3 com o plano.
  - **Memória:** checkpoint da fase 4.
  - Commit: `docs: evidências do modelo de suspeita e decisões da fase 3 (D-021)`.

### Task 3.6: revisão independente

- [ ] Despachar um revisor (opus, `superpowers:requesting-code-review`) com o diff da fase (`main..fase-3`), a spec 6.1 e este plano, pedindo foco em vazamento, paridade treino × score, point-in-time, honestidade das métricas e reprodutibilidade.
- [ ] Corrigir os pontos críticos e importantes (TDD quando houver teste possível), retreinar se alguma correção mudar features, e registrar no ledger `_interno/execucao/ledger-fase-3.md` e na D-021. Fazer o merge local no `main` (sem push).

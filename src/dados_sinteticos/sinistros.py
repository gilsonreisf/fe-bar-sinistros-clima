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

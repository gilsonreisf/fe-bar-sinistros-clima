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
FRACAO_CARTEIRA_POPULACAO = 0.40  # parte da carteira proporcional à população; o resto é concentração regional (D-018)
FRACAO_HISTORICO_SEM_ESTACAO = 0.20
CANAIS = {"app": 0.50, "corretor": 0.35, "central": 0.15}

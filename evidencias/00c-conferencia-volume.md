# Conferência da base no Volume

Executado em 2026-11-20 19:43 com `uv run python scripts/executar_sql.py src/governanca/90_conferir_volume.sql` (catálogo e schemas lidos do `.env`; D-016).

```text
[1] SELECT 'apolices' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/fe_bar_sinistros_catalog/
    arquivo | linhas
    apolices | 60251
[2] SELECT 'segurados' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/fe_bar_sinistros_catalog
    arquivo | linhas
    segurados | 50251
[3] SELECT 'historico' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/fe_bar_sinistros_catalog
    arquivo | linhas
    historico | 20000
[4] SELECT 'clima_2026' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/fe_bar_sinistros_catalo
    arquivo | linhas
    clima_2026 | 167808
[5] SELECT 'gabarito_evento' AS arquivo, COUNT(*) AS linhas FROM read_files('/Volumes/fe_bar_sinistros_c
    arquivo | linhas
    gabarito_evento | 8000
[6] COMMENT ON VOLUME fe_bar_sinistros_catalog.landing.arquivos IS 'Arquivos brutos, uma pasta por entid
```

Esperado: apólices ~60 mil + extras; segurados ~50 mil + extras; histórico 20.000; clima 2026 = 23 estações × 7.296 horas = 167.808; gabarito do evento 8.000.

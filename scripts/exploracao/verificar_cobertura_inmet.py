"""Mede a completude dos dados horários do INMET para as estações de SC.

Uso: python -I verificar_cobertura_inmet.py <caminho/AAAA.zip> [AAAA]
Fonte: https://portal.inmet.gov.br/dadoshistoricos (arquivo anual .zip).
Considera os meses de agosto e setembro do ano informado (padrão: 2026).
"""
import sys, zipfile
ANO = sys.argv[2] if len(sys.argv) > 2 else "2026"
z = zipfile.ZipFile(sys.argv[1])
for n in sorted(x for x in z.namelist() if "_SC_" in x):
    lines = z.read(n).decode("latin-1").splitlines()
    hdr_i = next(i for i,l in enumerate(lines) if l.startswith("Data;"))
    hdr = lines[hdr_i].split(";")
    pi = next(i for i,h in enumerate(hdr) if "PRECIPITA" in h.upper())
    ri = next(i for i,h in enumerate(hdr) if "RAJADA" in h.upper())
    tot=okp=okr=0; maxr=0.0; sump=0.0
    for l in lines[hdr_i+1:]:
        c=l.split(";")
        if len(c)<=max(pi,ri): continue
        d=c[0]
        if not (d.startswith(f"{ANO}/08") or d.startswith(f"{ANO}/09")): continue
        tot+=1
        p=c[pi].replace(",",".").strip(); r=c[ri].replace(",",".").strip()
        try:
            pv=float(p)
            if pv>-9000: okp+=1; sump+=pv
        except: pass
        try:
            rv=float(r)
            if rv>-9000: okr+=1; maxr=max(maxr,rv)
        except: pass
    st=n.split("_")[3]+" "+n.split("_")[4]
    print(f"{st:32s} horas={tot:5d} precip_ok={okp/ max(tot,1):5.0%} rajada_ok={okr/max(tot,1):5.0%} chuva_total_mm={sump:7.1f} rajada_max_ms={maxr:5.1f}")

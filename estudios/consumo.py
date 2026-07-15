"""Datos de consumo preparados para las exportaciones (Excel y PDF).

Los meses se presentan SIEMPRE de enero a diciembre, aunque el histórico abarque
dos años naturales (p. ej. may-2025 … abr-2026): lo que interesa al leer el estudio
es la estacionalidad, no el orden cronológico de la toma de datos.
"""
from decimal import Decimal

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
MESES_ABR = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
ZERO = Decimal(0)


def _pct(parte, total):
    return (parte / total * 100) if total else ZERO


def resumen_consumo(expediente):
    """Ficha de consumo por punto + agregado del expediente. None si no hay puntos."""
    puntos = list(expediente.puntos.prefetch_related("consumos"))
    if not puntos:
        return None

    fichas = []
    agregado = {}   # mes (1-12) -> [P1..P6]
    for punto in puntos:
        por_mes = {}
        for c in punto.consumos.all():
            por_mes[c.mes] = {
                "mes": c.mes,
                "anio": c.anio,
                "nombre": MESES[c.mes - 1],
                "abr": f"{MESES_ABR[c.mes - 1]} {c.anio}",
                "periodos": [c.p1, c.p2, c.p3, c.p4, c.p5, c.p6],
                "total": c.total,
            }
            fila = agregado.setdefault(c.mes, [ZERO] * 6)
            for i, v in enumerate([c.p1, c.p2, c.p3, c.p4, c.p5, c.p6]):
                fila[i] += v

        meses = [por_mes[m] for m in range(1, 13) if m in por_mes]   # enero → diciembre
        totales = [ZERO] * 6
        for m in meses:
            for i, v in enumerate(m["periodos"]):
                totales[i] += v
        total_anual = sum(totales)

        fichas.append({
            "punto": punto,
            "potencias": [punto.potencia_p1, punto.potencia_p2, punto.potencia_p3,
                          punto.potencia_p4, punto.potencia_p5, punto.potencia_p6],
            "meses": meses,
            "totales_periodo": totales,
            "pct_periodo": [_pct(t, total_anual) for t in totales],
            "total_anual": total_anual,
        })

    agg_meses = []
    for m in range(1, 13):
        if m not in agregado:
            continue
        periodos = agregado[m]
        agg_meses.append({"mes": m, "nombre": MESES[m - 1], "abr": MESES_ABR[m - 1],
                          "periodos": periodos, "total": sum(periodos)})
    agg_totales = [ZERO] * 6
    for m in agg_meses:
        for i, v in enumerate(m["periodos"]):
            agg_totales[i] += v
    total_global = sum(agg_totales)

    return {
        "fichas": fichas,
        "multiple": len(fichas) > 1,
        "meses": fichas[0]["meses"] if len(fichas) == 1 else agg_meses,
        "totales_periodo": fichas[0]["totales_periodo"] if len(fichas) == 1 else agg_totales,
        "pct_periodo": ([_pct(t, total_global) for t in agg_totales]
                        if len(fichas) > 1 else fichas[0]["pct_periodo"]),
        "agg_meses": agg_meses,
        "total_global": total_global,
    }

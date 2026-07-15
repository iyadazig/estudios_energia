"""Motor de cálculo del comparativo (factura anual sin IVA, sin alquiler).

Fórmula por punto de suministro:
  potencia = Σ_p kW_p × precio_potencia_p (€/kW·año)
  energía  = Σ_mes Σ_p kWh_p × precio_energia_p
  conceptos adicionales (solo ofertas): €/MWh, SSAA por umbral, fijo/mes, %
  IEE      = tipo vigente × (potencia + energía + conceptos con entra_en_iee)
  total    = potencia + energía + conceptos + IEE
Los precios "según ATR" o "sin ATR incluido" usan los parámetros regulados
vigentes en la fecha del estudio (peajes + cargos).
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Q

from .models import ParametroGeneral, ParametroRegulado, ProfileFactor, SerieSSAA

ZERO = Decimal("0")


@dataclass
class Desglose:
    potencia: Decimal = ZERO
    energia: Decimal = ZERO
    conceptos: dict = field(default_factory=dict)  # nombre del concepto -> importe
    ssaa: Decimal = ZERO                            # regularización de SSAA (línea propia)
    iee: Decimal = ZERO
    total: Decimal = ZERO
    kwh: Decimal = ZERO

    @property
    def conceptos_total(self):
        return sum(self.conceptos.values(), ZERO)

    @property
    def eur_kwh(self):
        return self.total / self.kwh if self.kwh else None

    def acumular(self, otro):
        self.potencia += otro.potencia
        self.energia += otro.energia
        for k, v in otro.conceptos.items():
            self.conceptos[k] = self.conceptos.get(k, ZERO) + v
        self.ssaa += otro.ssaa
        self.iee += otro.iee
        self.total += otro.total
        self.kwh += otro.kwh


def _valores(param):
    return [param.p1, param.p2, param.p3, param.p4, param.p5, param.p6]


def _parametro_vigente(tipo, termino, tarifa, fecha):
    return (
        ParametroRegulado.objects.filter(
            tipo=tipo, termino=termino, tarifa=tarifa, vigencia_inicio__lte=fecha
        )
        .filter(Q(vigencia_fin__isnull=True) | Q(vigencia_fin__gte=fecha))
        .order_by("-vigencia_inicio")
        .first()
    )


def atr_vigente(termino, tarifa, fecha, avisos):
    """Suma de peajes + cargos vigentes por periodo."""
    total = [ZERO] * 6
    for tipo in ("peaje", "cargo"):
        p = _parametro_vigente(tipo, termino, tarifa, fecha)
        if p is None:
            avisos.add(f"No hay {tipo} de {termino} vigente para {tarifa} a {fecha:%d/%m/%Y}: se toma 0.")
            continue
        if not p.validado:
            avisos.add(f"El {tipo} de {termino} {tarifa} usado está pendiente de validar en el panel de administración.")
        total = [a + b for a, b in zip(total, _valores(p))]
    return total


def perdidas_vigentes(tarifa, fecha, avisos):
    p = _parametro_vigente("perdidas", "energia", tarifa, fecha)
    if p is None:
        avisos.add(f"No hay coeficientes de pérdidas para {tarifa}: los conceptos con pérdidas usan consumo sin elevar.")
        return [ZERO] * 6
    return _valores(p)


def imp_local_vigente(tarifa, fecha, avisos):
    """Tipo del impuesto local (uniforme por periodos): se toma P1."""
    p = _parametro_vigente("imp_local", "energia", tarifa, fecha)
    if p is None:
        avisos.add(f"No hay impuesto local para {tarifa}: los conceptos «× impuesto local» no lo aplican.")
        return ZERO
    if not p.validado:
        avisos.add(f"El impuesto local de {tarifa} usado está pendiente de validar en el panel de administración.")
    return p.p1


# --- Servicios de ajuste (SSAA) por oferta -------------------------------

def _perdidas_ssaa(oferta, punto, fecha, avisos):
    """Coeficientes de pérdidas (tanto por uno, por periodo) para el SSAA de la oferta."""
    if oferta.ssaa_perdidas_modo == "fija":
        return [(oferta.ssaa_perdidas_pct or ZERO) / 100] * 6
    return perdidas_vigentes(punto.tarifa, fecha, avisos)


def _profile_factor(punto, mes, avisos):
    ambito = next((a for a, tarifas in ProfileFactor.TARIFAS_POR_AMBITO.items()
                   if punto.tarifa in tarifas), None)
    if ambito is None:
        avisos.add(f"No hay profile factors para {punto.tarifa}: no se puede aplicar el SSAA horario.")
        return None
    pf = ProfileFactor.objects.filter(ambito=ambito, mes=mes).first()
    if pf is None:
        avisos.add(f"Falta el profile factor de {punto.tarifa} para el mes {mes}: SSAA horario a 0 ese mes.")
        return None
    return [pf.p1, pf.p2, pf.p3, pf.p4, pf.p5, pf.p6]


def _diferencia_ssaa(oferta, ssaa):
    """Diferencia SSAA lineal (€/MWh) según el tipo de oferta (positiva=cargo, negativa=abono)."""
    if oferta.ssaa_tipo == "indexado":
        return ssaa
    sup, inf = oferta.ssaa_ref_superior, oferta.ssaa_ref_inferior
    if oferta.ssaa_tipo == "techo":
        return ssaa - sup if (sup is not None and ssaa > sup) else ZERO
    if oferta.ssaa_tipo == "banda":
        if sup is not None and ssaa > sup:
            return ssaa - sup
        if inf is not None and ssaa < inf:
            return ssaa - inf
        return ZERO
    return ZERO


def coste_ssaa(oferta, punto, consumos, fecha, avisos):
    """Coste anual de SSAA de la oferta para un punto (puede ser negativo = abono).

    Reg_mes = Σ_periodo [ dif_lineal(p) × (1+pérdidas_p) × apuntamiento × consumo_MWh_p × HL ]
    """
    if oferta.ssaa_tipo == "incluido":
        return ZERO
    perdidas = _perdidas_ssaa(oferta, punto, fecha, avisos)
    ap = oferta.ssaa_apuntamiento if oferta.ssaa_apuntamiento is not None else Decimal("1")
    hl = (1 + imp_local_vigente(punto.tarifa, fecha, avisos)) if oferta.ssaa_impuesto_municipal else Decimal("1")
    total = ZERO
    for _anio, mes, valores in consumos:
        ssaa = SerieSSAA.objects.filter(mes=mes).first()
        if ssaa is None:
            avisos.add(f"Falta el SSAA estimado del mes {mes}: se toma 0 ese mes.")
            continue
        base = ssaa.valor_considerado
        if oferta.ssaa_modo == "horario":
            pf = _profile_factor(punto, mes, avisos)
            if pf is None:
                continue
            ssaa_periodo = [base * f if f is not None else None for f in pf]
        else:
            ssaa_periodo = [base] * 6
        for p in range(6):
            kwh = valores[p]
            sp = ssaa_periodo[p]
            if not kwh or sp is None:
                continue
            dif = _diferencia_ssaa(oferta, sp)
            if dif == 0:
                continue
            total += dif * (1 + perdidas[p]) * ap * (kwh / 1000) * hl
    return total


def iee_vigente(fecha, avisos):
    p = (
        ParametroGeneral.objects.filter(clave="iee", vigencia_inicio__lte=fecha)
        .filter(Q(vigencia_fin__isnull=True) | Q(vigencia_fin__gte=fecha))
        .order_by("-vigencia_inicio")
        .first()
    )
    if p is None:
        avisos.add("No hay tipo de IEE vigente: se calcula sin impuesto.")
        return ZERO
    if not p.validado:
        avisos.add("El tipo de IEE usado está pendiente de validar en el panel de administración.")
    return p.valor


def _consumos_por_periodo(punto):
    """[(anio, mes, [kwh P1..P6])] y total anual."""
    filas = [
        (c.anio, c.mes, [c.p1, c.p2, c.p3, c.p4, c.p5, c.p6])
        for c in punto.consumos.all()
    ]
    total = sum((sum(v) for _, _, v in filas), ZERO)
    return filas, total


def _coste_energia(consumos, precios):
    precios = [p if p is not None else ZERO for p in precios]
    return sum(
        (sum(kwh * precio for kwh, precio in zip(valores, precios)) for _, _, valores in consumos),
        ZERO,
    )


def _coste_potencia(punto, precios):
    potencias = [punto.potencia_p1, punto.potencia_p2, punto.potencia_p3,
                 punto.potencia_p4, punto.potencia_p5, punto.potencia_p6]
    return sum(
        (kw * (precio if precio is not None else ZERO) for kw, precio in zip(potencias, precios) if kw),
        ZERO,
    )


def calcular_actual(punto, fecha, avisos):
    """Coste anual de las condiciones actuales. None si el contrato actual es indexado."""
    if punto.modalidad_actual == "indexado":
        avisos.add(f"{punto.cups}: contrato actual indexado — su línea base no se calcula en esta fase.")
        return None
    consumos, kwh = _consumos_por_periodo(punto)
    d = Desglose(kwh=kwh)

    precios_e = [punto.precio_energia_p1, punto.precio_energia_p2, punto.precio_energia_p3,
                 punto.precio_energia_p4, punto.precio_energia_p5, punto.precio_energia_p6]
    if not punto.energia_peajes_incluidos:
        atr = atr_vigente("energia", punto.tarifa, fecha, avisos)
        precios_e = [(p or ZERO) + a for p, a in zip(precios_e, atr)]
    d.energia = _coste_energia(consumos, precios_e)

    if punto.potencia_segun_atr:
        precios_p = atr_vigente("potencia", punto.tarifa, fecha, avisos)
    else:
        precios_p = [punto.precio_potencia_p1, punto.precio_potencia_p2, punto.precio_potencia_p3,
                     punto.precio_potencia_p4, punto.precio_potencia_p5, punto.precio_potencia_p6]
    d.potencia = _coste_potencia(punto, precios_p)

    d.iee = (d.potencia + d.energia) * iee_vigente(fecha, avisos)
    d.total = d.potencia + d.energia + d.iee
    return d


def _precios_oferta_para(oferta, punto):
    """Prioridad: precio del CUPS concreto > precio de su tarifa > precio genérico."""
    precios = list(oferta.precios.all())
    especifico = next((p for p in precios if p.punto_id == punto.pk), None)
    if especifico:
        return especifico
    por_tarifa = next((p for p in precios if p.punto_id is None and p.tarifa == punto.tarifa), None)
    if por_tarifa:
        return por_tarifa
    return next((p for p in precios if p.punto_id is None and not p.tarifa), None)


def calcular_oferta(oferta, punto, fecha, avisos):
    """Coste anual del punto con los precios de la oferta."""
    consumos, kwh = _consumos_por_periodo(punto)
    d = Desglose(kwh=kwh)
    precios = _precios_oferta_para(oferta, punto)
    if precios is None:
        avisos.add(f"La oferta {oferta.etiqueta} no tiene precios para {punto.cups}: se omite ese CUPS.")
        return None

    precios_e = [precios.energia_p1, precios.energia_p2, precios.energia_p3,
                 precios.energia_p4, precios.energia_p5, precios.energia_p6]
    if not oferta.atr_energia_incluido:
        atr = atr_vigente("energia", punto.tarifa, fecha, avisos)
        precios_e = [(p or ZERO) + a for p, a in zip(precios_e, atr)]
    d.energia = _coste_energia(consumos, precios_e)

    if oferta.atr_potencia_incluido:
        precios_p = [precios.potencia_p1, precios.potencia_p2, precios.potencia_p3,
                     precios.potencia_p4, precios.potencia_p5, precios.potencia_p6]
    else:
        precios_p = atr_vigente("potencia", punto.tarifa, fecha, avisos)
    d.potencia = _coste_potencia(punto, precios_p)

    base_iee = d.potencia + d.energia
    perdidas = None
    imp_local = None
    for concepto in oferta.conceptos.all():
        importe = ZERO
        if concepto.tipo == "eur_mwh":
            mwh = ZERO
            for _, _, valores in consumos:
                if concepto.con_perdidas:
                    if perdidas is None:
                        perdidas = perdidas_vigentes(punto.tarifa, fecha, avisos)
                    mwh += sum(kwh_p * (1 + c) for kwh_p, c in zip(valores, perdidas)) / 1000
                else:
                    mwh += sum(valores) / 1000
            importe = concepto.valor * mwh
        elif concepto.tipo == "fijo_mes":
            importe = concepto.valor * 12
        elif concepto.tipo == "pct":
            importe = (d.potencia + d.energia) * concepto.valor / 100
        if concepto.con_impuesto_local:
            if imp_local is None:
                imp_local = imp_local_vigente(punto.tarifa, fecha, avisos)
            importe *= (1 + imp_local)
        d.conceptos[concepto.nombre] = d.conceptos.get(concepto.nombre, ZERO) + importe
        if concepto.entra_en_iee:
            base_iee += importe

    # Regularización / coste de SSAA (línea propia; 0 si va incluido en el precio)
    d.ssaa = coste_ssaa(oferta, punto, consumos, fecha, avisos)
    base_iee += d.ssaa  # el SSAA forma parte de la base del IEE

    d.iee = base_iee * iee_vigente(fecha, avisos)
    d.total = d.potencia + d.energia + d.conceptos_total + d.ssaa + d.iee
    return d


def comparativo_expediente(expediente, fecha=None):
    """Comparativo completo: línea base + una columna por oferta, agregado y por CUPS."""
    fecha = fecha or date.today()
    avisos = set()
    puntos = list(expediente.puntos.all())

    actual_total = Desglose()
    actual_por_punto = {}
    baseline_completa = bool(puntos)
    for punto in puntos:
        d = calcular_actual(punto, fecha, avisos)
        if d is None:
            baseline_completa = False
            continue
        actual_por_punto[punto.pk] = d
        actual_total.acumular(d)
    if not baseline_completa:
        actual_total = None

    columnas = []
    for oferta in expediente.ofertas.filter(modalidad="fijo").prefetch_related("precios", "conceptos"):
        agregado = Desglose()
        por_punto = {}
        completa = bool(puntos)
        for punto in puntos:
            d = calcular_oferta(oferta, punto, fecha, avisos)
            if d is None:
                completa = False
                continue
            por_punto[punto.pk] = d
            agregado.acumular(d)
        ahorro = ahorro_pct = None
        if actual_total and actual_total.total and completa:
            ahorro = agregado.total - actual_total.total
            ahorro_pct = ahorro / actual_total.total * 100
        columnas.append({
            "oferta": oferta, "agregado": agregado, "por_punto": por_punto,
            "completa": completa, "ahorro": ahorro, "ahorro_pct": ahorro_pct,
        })

    completas = [c for c in columnas if c["completa"]]
    if completas:
        mejor = min(completas, key=lambda c: c["agregado"].total)
        for posicion, c in enumerate(sorted(completas, key=lambda c: c["agregado"].total), start=1):
            c["ranking"] = posicion
        mejor["mejor"] = True

    # Orden de presentación: ofertas completas de más barata a más cara, luego las incompletas.
    columnas.sort(key=lambda c: (not c["completa"], c["agregado"].total if c["completa"] else 0))

    # Nombres de conceptos adicionales presentes en cualquier oferta (para las filas del desglose).
    nombres = []
    for c in columnas:
        for nombre in c["agregado"].conceptos:
            if nombre not in nombres:
                nombres.append(nombre)

    return {
        "fecha": fecha,
        "puntos": puntos,
        "actual": actual_total,
        "actual_por_punto": actual_por_punto,
        "columnas": columnas,
        "conceptos_nombres": nombres,
        "avisos": sorted(avisos),
    }

import io
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from django.http import HttpResponse

from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.http import require_POST

from .calculo import comparativo_expediente
from .consumo import resumen_consumo
from .exportar import comparativo_a_excel, comparativo_a_pdf
from .forms import (
    ConceptoFormSet,
    ExpedienteForm,
    ImportarParametrosForm,
    ImportarPlantillaForm,
    OfertaCatalogoNombreForm,
    OfertaForm,
    UsuarioAltaForm,
    UsuarioForm,
    concepto_formset,
)
from .importador import importar_plantilla
from .models import (
    ConceptoCatalogo,
    ConsumoMensual,
    Expediente,
    Oferta,
    OfertaCatalogo,
    PrecioCatalogo,
    PrecioOferta,
    PuntoSuministro,
)
from .parametros_excel import generar_plantilla, importar_parametros

# Campos de condiciones que se copian entre oferta y oferta de catálogo.
CONDICIONES_OFERTA = [
    "comercializadora", "duracion_meses", "gdo", "atr_energia_incluido", "atr_potencia_incluido",
    "ssaa_tipo", "ssaa_modo", "ssaa_ref_superior", "ssaa_ref_inferior",
    "ssaa_perdidas_modo", "ssaa_perdidas_pct", "ssaa_apuntamiento", "ssaa_impuesto_municipal",
    "observaciones",
]
CAMPOS_CONCEPTO = ["nombre", "tipo", "valor", "con_perdidas", "con_impuesto_local", "entra_en_iee"]


def _detalle_cups(comparativo):
    return [
        {
            "punto": punto,
            "actual": comparativo["actual_por_punto"].get(punto.pk),
            "ofertas": [c["por_punto"].get(punto.pk) for c in comparativo["columnas"]],
        }
        for punto in comparativo["puntos"]
    ]


def _grafico(comparativo):
    """Barras de coste anual total: contrato actual + cada oferta completa."""
    filas = []
    if comparativo["actual"]:
        filas.append(("Contrato actual", comparativo["actual"].total, "actual", None))
    for c in comparativo["columnas"]:
        if c["completa"]:
            tipo = "mejor" if c.get("mejor") else "oferta"
            filas.append((c["oferta"].etiqueta, c["agregado"].total, tipo, c.get("ranking")))
    if not filas:
        return []
    maximo = max(total for _, total, _, _ in filas)
    return [
        {
            "label": label,
            "total": total,
            # Formateado con punto decimal (no coma): el ancho CSS lo exige.
            "pct": f"{(total / maximo * 100) if maximo else 0:.2f}",
            "tipo": tipo,
            "ranking": ranking,
        }
        for label, total, tipo, ranking in filas
    ]


@login_required
def inicio(request):
    es_admin = request.user.is_staff
    # Ámbito: "mios" filtra por gestor. Técnico -> "mios" por defecto; admin -> "todos".
    ambito = request.GET.get("ambito") or ("todos" if es_admin else "mios")
    estado = request.GET.get("estado") or "abiertos"
    q = (request.GET.get("q") or "").strip()

    ambito_qs = Expediente.objects.all()
    if ambito == "mios":
        ambito_qs = ambito_qs.filter(gestor=request.user)

    # --- Listado (aplica también estado y búsqueda) ---
    listado = ambito_qs
    if estado == "abiertos":
        listado = listado.filter(estado=Expediente.Estado.ABIERTO)
    elif estado == "cerrados":
        listado = listado.filter(estado=Expediente.Estado.CERRADO)
    if q:
        listado = listado.filter(Q(cliente_razon_social__icontains=q) | Q(codigo__icontains=q))
    expedientes = listado.select_related("gestor").annotate(
        num_puntos=Count("puntos", distinct=True),
        num_ofertas=Count("ofertas", distinct=True),
    )

    # --- KPIs (sobre el ámbito; agregaciones baratas, sin recalcular comparativos) ---
    kpis = ambito_qs.aggregate(
        abiertos=Count("id", filter=Q(estado=Expediente.Estado.ABIERTO)),
        cerrados=Count("id", filter=Q(estado=Expediente.Estado.CERRADO)),
    )
    sin_ofertas = ambito_qs.annotate(n=Count("ofertas")).filter(n=0).count()
    cups = PuntoSuministro.objects.filter(expediente__in=ambito_qs).count()
    n_ofertas = Oferta.objects.filter(expediente__in=ambito_qs).count()

    # --- Desglose por técnico (solo admin) ---
    por_tecnico = None
    if es_admin:
        por_tecnico = list(
            Expediente.objects.values("gestor", "gestor__first_name",
                                      "gestor__last_name", "gestor__username")
            .annotate(abiertos=Count("id", filter=Q(estado=Expediente.Estado.ABIERTO)),
                      cerrados=Count("id", filter=Q(estado=Expediente.Estado.CERRADO)))
            .order_by("gestor__username")
        )
        # CUPS por técnico en query aparte (evita inflar por el join de puntos).
        cups_gestor = dict(
            PuntoSuministro.objects.values_list("expediente__gestor")
            .annotate(n=Count("id")).values_list("expediente__gestor", "n")
        )
        for fila in por_tecnico:
            fila["cups"] = cups_gestor.get(fila["gestor"], 0)

    return render(request, "estudios/inicio.html", {
        "expedientes": expedientes,
        "es_admin": es_admin,
        "ambito": ambito, "estado": estado, "q": q,
        "kpi_abiertos": kpis["abiertos"], "kpi_cerrados": kpis["cerrados"],
        "kpi_sin_ofertas": sin_ofertas, "kpi_cups": cups, "kpi_ofertas": n_ofertas,
        "por_tecnico": por_tecnico,
    })


@login_required
def expediente_nuevo(request):
    if request.method == "POST":
        form = ExpedienteForm(request.POST)
        if form.is_valid():
            expediente = form.save(commit=False)
            expediente.gestor = request.user
            expediente.save()
            return redirect("expediente_detalle", pk=expediente.pk)
    else:
        form = ExpedienteForm()
    return render(request, "estudios/expediente_form.html", {"form": form})


@login_required
def expediente_editar(request, pk):
    expediente = get_object_or_404(Expediente, pk=pk)
    if request.method == "POST":
        form = ExpedienteForm(request.POST, instance=expediente)
        if form.is_valid():
            form.save()
            messages.success(request, "Expediente actualizado.")
            return redirect("expediente_detalle", pk=pk)
    else:
        form = ExpedienteForm(instance=expediente)
    return render(request, "estudios/expediente_form.html", {
        "form": form, "titulo": f"Editar {expediente.codigo}",
    })


def _ambitos_precio(expediente, modo):
    """Lista de (key, título, ('tarifa', t) | ('cups', punto)) según el modo."""
    if modo == "cups":
        return [(f"cups{p.pk}", f"{p.cups} ({p.tarifa})", ("cups", p))
                for p in expediente.puntos.all()]
    tarifas = sorted({p.tarifa for p in expediente.puntos.all()})
    return [(t.replace(".", "_"), f"Tarifa {t}", ("tarifa", t)) for t in tarifas]


def _parse_precio_post(post, key):
    def dec(nombre):
        v = post.get(nombre, "").strip().replace(",", ".")
        if not v:
            return None
        try:
            return Decimal(v)
        except (InvalidOperation, ValueError):
            return None
    e = [dec(f"e_{key}_p{i}") for i in range(1, 7)]
    p = [dec(f"p_{key}_p{i}") for i in range(1, 7)]
    return e, p


def _valores_precio(precio):
    if precio is None:
        return [""] * 6, [""] * 6
    e = ["" if getattr(precio, f"energia_p{i}") is None else getattr(precio, f"energia_p{i}") for i in range(1, 7)]
    p = ["" if getattr(precio, f"potencia_p{i}") is None else getattr(precio, f"potencia_p{i}") for i in range(1, 7)]
    return e, p


def _bloques_precio(expediente, modo, oferta, post, catalogo=None):
    """Construye los bloques de precios para la plantilla (prefijados).

    Fuente de los valores, por orden: POST (reenvío del formulario) > catálogo
    (precios por tarifa de una OfertaCatalogo) > precios de la propia oferta.
    """
    precios = list(oferta.precios.all()) if oferta else []
    generico = next((p for p in precios if not p.tarifa and p.punto_id is None), None)
    precios_cat = {p.tarifa: p for p in catalogo.precios.all()} if catalogo else {}
    bloques = []
    for key, titulo, (ambito, ref) in _ambitos_precio(expediente, modo):
        if post is not None:
            e, p = _parse_precio_post(post, key)
            e = ["" if v is None else v for v in e]
            p = ["" if v is None else v for v in p]
        elif catalogo is not None:
            tarifa = ref if ambito == "tarifa" else ref.tarifa
            e, p = _valores_precio(precios_cat.get(tarifa))
        else:
            if ambito == "cups":
                pr = next((x for x in precios if x.punto_id == ref.pk), None) or generico
            else:
                pr = next((x for x in precios if not x.punto_id and x.tarifa == ref), None) or generico
            e, p = _valores_precio(pr)
        bloques.append({"key": key, "titulo": titulo, "energia": e, "potencia": p})
    return bloques


@login_required
def oferta_editar(request, expediente_pk, pk=None):
    expediente = get_object_or_404(Expediente, pk=expediente_pk)
    oferta = get_object_or_404(Oferta, pk=pk, expediente=expediente) if pk else None

    if request.method == "POST":
        form = OfertaForm(request.POST, instance=oferta)
        formset = ConceptoFormSet(request.POST, instance=oferta)
        modo = request.POST.get("modo_precios", "tarifa")
        if form.is_valid() and formset.is_valid():
            oferta = form.save(commit=False)
            oferta.expediente = expediente
            oferta.save()
            formset.instance = oferta
            formset.save()
            # Precios: se borran y se recrean según el modo elegido.
            oferta.precios.all().delete()
            for key, _titulo, (ambito, ref) in _ambitos_precio(expediente, modo):
                e, p = _parse_precio_post(request.POST, key)
                if not any(v is not None for v in e + p):
                    continue
                campos = {f"energia_p{i+1}": e[i] for i in range(6)}
                campos.update({f"potencia_p{i+1}": p[i] for i in range(6)})
                if ambito == "cups":
                    PrecioOferta.objects.create(oferta=oferta, punto=ref, tarifa="", **campos)
                else:
                    PrecioOferta.objects.create(oferta=oferta, tarifa=ref, **campos)
            messages.success(request, f"Oferta {oferta.etiqueta} guardada.")
            return redirect("expediente_detalle", pk=expediente.pk)
        bloques_tarifa = _bloques_precio(expediente, "tarifa", oferta, request.POST if modo == "tarifa" else None)
        bloques_cups = _bloques_precio(expediente, "cups", oferta, request.POST if modo == "cups" else None)
    else:
        cargado = None
        if not oferta and request.GET.get("catalogo"):
            cargado = get_object_or_404(OfertaCatalogo, pk=request.GET["catalogo"])
        if cargado:
            form = OfertaForm(initial={c: getattr(cargado, c) for c in CONDICIONES_OFERTA})
            conceptos_ini = [{c: getattr(x, c) for c in CAMPOS_CONCEPTO} for x in cargado.conceptos.all()]
            formset = concepto_formset(max(len(conceptos_ini), 1))(initial=conceptos_ini)
            modo = "tarifa"
            bloques_tarifa = _bloques_precio(expediente, "tarifa", None, None, catalogo=cargado)
            bloques_cups = _bloques_precio(expediente, "cups", None, None, catalogo=cargado)
        else:
            form = OfertaForm(instance=oferta)
            formset = ConceptoFormSet(instance=oferta)
            modo = "cups" if oferta and oferta.precios.filter(punto__isnull=False).exists() else "tarifa"
            bloques_tarifa = _bloques_precio(expediente, "tarifa", oferta, None)
            bloques_cups = _bloques_precio(expediente, "cups", oferta, None)

    return render(request, "estudios/oferta_form.html", {
        "expediente": expediente, "oferta": oferta, "form": form, "formset": formset,
        "modo": modo, "bloques_tarifa": bloques_tarifa, "bloques_cups": bloques_cups,
        "periodos": range(1, 7),
        "catalogo": OfertaCatalogo.objects.all() if not oferta else None,
        "cargado": cargado if request.method == "GET" else None,
    })


@login_required
@require_POST
def oferta_borrar(request, expediente_pk, pk):
    oferta = get_object_or_404(Oferta, pk=pk, expediente_id=expediente_pk)
    etiqueta = oferta.etiqueta
    oferta.delete()
    messages.success(request, f"Oferta {etiqueta} eliminada.")
    return redirect("expediente_detalle", pk=expediente_pk)


# --- Catálogo de ofertas reutilizables ---------------------------------

def copiar_oferta_a_catalogo(oferta, nombre, observaciones="", creado_por=None):
    """Copia una `Oferta` a una `OfertaCatalogo` reutilizable: condiciones + SSAA,
    conceptos y precios POR TARIFA (precedencia genérico < por tarifa < por CUPS).
    Devuelve la OfertaCatalogo creada. Reutilizable desde vistas y comandos."""
    cat = OfertaCatalogo(**{c: getattr(oferta, c) for c in CONDICIONES_OFERTA})
    cat.nombre = nombre
    cat.observaciones = observaciones
    cat.creado_por = creado_por
    cat.save()
    for con in oferta.conceptos.all():
        ConceptoCatalogo.objects.create(oferta_catalogo=cat,
                                        **{c: getattr(con, c) for c in CAMPOS_CONCEPTO})
    tarifas_exp = {p.tarifa for p in oferta.expediente.puntos.all()}
    precios = list(oferta.precios.all())
    por_tarifa = {}
    for pr in precios:  # genérico → todas las tarifas del expediente
        if not pr.tarifa and not pr.punto_id:
            for t in tarifas_exp:
                por_tarifa[t] = pr
    for pr in precios:  # por tarifa
        if pr.tarifa and not pr.punto_id:
            por_tarifa[pr.tarifa] = pr
    for pr in precios:  # por CUPS concreto (override)
        if pr.punto_id:
            por_tarifa[pr.punto.tarifa] = pr
    for tarifa, pr in por_tarifa.items():
        PrecioCatalogo.objects.create(
            oferta_catalogo=cat, tarifa=tarifa,
            **{f"{t}_p{i}": getattr(pr, f"{t}_p{i}")
               for t in ("energia", "potencia") for i in range(1, 7)},
        )
    return cat


@login_required
def oferta_a_catalogo(request, expediente_pk, pk):
    """Guarda una oferta del expediente como oferta de catálogo reutilizable."""
    oferta = get_object_or_404(Oferta, pk=pk, expediente_id=expediente_pk)
    if request.method == "POST":
        form = OfertaCatalogoNombreForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                cat = copiar_oferta_a_catalogo(
                    oferta, form.cleaned_data["nombre"],
                    form.cleaned_data["observaciones"], request.user)
            messages.success(request, f"Oferta guardada en el catálogo como «{cat.nombre}».")
            return redirect("expediente_detalle", pk=expediente_pk)
    else:
        form = OfertaCatalogoNombreForm(initial={"nombre": oferta.etiqueta,
                                                 "observaciones": oferta.observaciones})
    return render(request, "estudios/catalogo_guardar.html",
                  {"form": form, "oferta": oferta, "expediente": oferta.expediente})


@login_required
def catalogo(request):
    return render(request, "estudios/catalogo.html",
                  {"ofertas": OfertaCatalogo.objects.prefetch_related("precios", "conceptos")})


@login_required
def catalogo_detalle(request, pk):
    cat = get_object_or_404(OfertaCatalogo.objects.prefetch_related("precios", "conceptos"), pk=pk)
    return render(request, "estudios/catalogo_detalle.html", {"cat": cat})


@login_required
def catalogo_editar(request, pk):
    cat = get_object_or_404(OfertaCatalogo, pk=pk)
    if request.method == "POST":
        form = OfertaCatalogoNombreForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, "Oferta de catálogo actualizada.")
            return redirect("catalogo")
    else:
        form = OfertaCatalogoNombreForm(instance=cat)
    return render(request, "estudios/catalogo_guardar.html", {"form": form, "catalogo_obj": cat})


@login_required
@require_POST
def catalogo_borrar(request, pk):
    cat = get_object_or_404(OfertaCatalogo, pk=pk)
    nombre = cat.nombre
    cat.delete()
    messages.success(request, f"Oferta de catálogo «{nombre}» eliminada.")
    return redirect("catalogo")


def _es_staff(user):
    return user.is_staff


@login_required
@user_passes_test(_es_staff)
def parametros(request):
    resultado = None
    if request.method == "POST":
        form = ImportarParametrosForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                creados, actualizados, errores = importar_parametros(form.cleaned_data["fichero"])
                if errores:
                    transaction.set_rollback(True)
                    resultado = {"errores": errores}
                else:
                    messages.success(
                        request,
                        f"Parámetros importados: {creados} nuevos, {actualizados} actualizados. "
                        "Quedan pendientes de validar.",
                    )
                    return redirect("parametros")
    else:
        form = ImportarParametrosForm()
    return render(request, "estudios/parametros.html", {"form": form, "resultado": resultado})


@login_required
@user_passes_test(_es_staff)
def parametros_plantilla(request):
    respuesta = HttpResponse(
        generar_plantilla(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = 'attachment; filename="Plantilla_Parametros.xlsx"'
    return respuesta


@login_required
def expediente_excel(request, pk):
    expediente = get_object_or_404(
        Expediente.objects.prefetch_related("puntos__consumos", "ofertas"), pk=pk
    )
    comparativo = comparativo_expediente(expediente)
    contenido = comparativo_a_excel(expediente, comparativo)
    respuesta = HttpResponse(
        contenido,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = f'attachment; filename="Comparativo_{expediente.codigo}.xlsx"'
    return respuesta


@login_required
def expediente_pdf(request, pk):
    expediente = get_object_or_404(
        Expediente.objects.prefetch_related("puntos__consumos", "ofertas"), pk=pk
    )
    comparativo = comparativo_expediente(expediente)
    contenido = comparativo_a_pdf(expediente, comparativo, _detalle_cups(comparativo),
                                  resumen_consumo(expediente))
    respuesta = HttpResponse(contenido, content_type="application/pdf")
    respuesta["Content-Disposition"] = f'attachment; filename="Comparativo_{expediente.codigo}.pdf"'
    return respuesta


def _crear_puntos(expediente, puntos):
    """Crea los PuntoSuministro y sus consumos a partir de los datos parseados."""
    for p in puntos:
        punto = PuntoSuministro.objects.create(
            expediente=expediente,
            titular=p.titular, cif_titular=p.cif_titular, cups=p.cups, direccion=p.direccion,
            tarifa=p.tarifa, origen_datos=PuntoSuministro.Origen.EXCEL,
            potencia_p1=p.potencias[0], potencia_p2=p.potencias[1], potencia_p3=p.potencias[2],
            potencia_p4=p.potencias[3], potencia_p5=p.potencias[4], potencia_p6=p.potencias[5],
            comercializadora_actual=p.comercializadora, modalidad_actual=p.modalidad,
            fecha_fin_contrato=p.fecha_fin, energia_peajes_incluidos=p.energia_peajes_incluidos,
            precio_energia_p1=p.precios_energia[0], precio_energia_p2=p.precios_energia[1],
            precio_energia_p3=p.precios_energia[2], precio_energia_p4=p.precios_energia[3],
            precio_energia_p5=p.precios_energia[4], precio_energia_p6=p.precios_energia[5],
            potencia_segun_atr=p.potencia_segun_atr,
            precio_potencia_p1=p.precios_potencia[0], precio_potencia_p2=p.precios_potencia[1],
            precio_potencia_p3=p.precios_potencia[2], precio_potencia_p4=p.precios_potencia[3],
            precio_potencia_p5=p.precios_potencia[4], precio_potencia_p6=p.precios_potencia[5],
        )
        ConsumoMensual.objects.bulk_create([
            ConsumoMensual(punto=punto, anio=anio, mes=mes,
                           p1=v[0], p2=v[1], p3=v[2], p4=v[3], p5=v[4], p6=v[5])
            for anio, mes, v in p.consumos
        ])


@login_required
def plantilla_estudio_descargar(request):
    """Descarga la plantilla Excel en blanco para rellenar CUPS y consumos."""
    ruta = settings.BASE_DIR / "estudios" / "plantillas" / "Plantilla_Estudio_Renovacion.xlsx"
    with open(ruta, "rb") as f:
        respuesta = HttpResponse(
            f.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    respuesta["Content-Disposition"] = 'attachment; filename="Plantilla_Estudio_Renovacion.xlsx"'
    return respuesta


@login_required
def expediente_importar(request):
    resultado = None
    if request.method == "POST":
        form = ImportarPlantillaForm(request.POST, request.FILES)
        if form.is_valid():
            raw = form.cleaned_data["fichero"].read()
            resultado = importar_plantilla(io.BytesIO(raw))
            if resultado.valido:
                with transaction.atomic():
                    expediente = Expediente.objects.create(
                        cliente_razon_social=resultado.cliente.razon_social,
                        cliente_cif=resultado.cliente.cif,
                        cliente_direccion=resultado.cliente.direccion,
                        gestor=request.user,
                        observaciones=(
                            f"Importado de plantilla Excel. Gestor en plantilla: "
                            f"{resultado.cliente.gestor or '—'} ({resultado.cliente.gestor_email or '—'})"
                        ),
                    )
                    _crear_puntos(expediente, resultado.puntos)
                    expediente.archivo_original.save(f"{expediente.codigo}.xlsx", ContentFile(raw), save=True)
                messages.success(
                    request,
                    f"Expediente {expediente.codigo} creado con {len(resultado.puntos)} "
                    f"punto(s) de suministro.",
                )
                for aviso in resultado.avisos:
                    messages.warning(request, aviso)
                return redirect("expediente_detalle", pk=expediente.pk)
    else:
        form = ImportarPlantillaForm()
    return render(request, "estudios/importar.html", {"form": form, "resultado": resultado})


@login_required
def expediente_importar_puntos(request, pk):
    """Importa CUPS y consumos de la plantilla Excel sobre un expediente ya existente."""
    expediente = get_object_or_404(Expediente, pk=pk)
    resultado = None
    if request.method == "POST":
        form = ImportarPlantillaForm(request.POST, request.FILES)
        if form.is_valid():
            raw = form.cleaned_data["fichero"].read()
            resultado = importar_plantilla(io.BytesIO(raw), requiere_cliente=False)
            if resultado.valido:
                # Añade los CUPS nuevos y omite (informando) los que ya estén.
                existentes = set(expediente.puntos.values_list("cups", flat=True))
                nuevos = [p for p in resultado.puntos if p.cups not in existentes]
                duplicados = [p.cups for p in resultado.puntos if p.cups in existentes]
                # Guarda (o actualiza) el Excel original en el expediente.
                expediente.archivo_original.save(f"{expediente.codigo}.xlsx", ContentFile(raw), save=True)
                if nuevos:
                    with transaction.atomic():
                        _crear_puntos(expediente, nuevos)
                    messages.success(
                        request, f"Añadidos {len(nuevos)} punto(s) de suministro al expediente."
                    )
                else:
                    messages.warning(
                        request,
                        "No se añadió ningún CUPS: todos los del archivo ya estaban en el expediente.",
                    )
                if duplicados:
                    messages.warning(
                        request,
                        f"Se omitieron {len(duplicados)} CUPS que ya estaban: " + ", ".join(duplicados) + ".",
                    )
                for aviso in resultado.avisos:
                    messages.warning(request, aviso)
                return redirect("expediente_detalle", pk=expediente.pk)
    else:
        form = ImportarPlantillaForm()
    return render(request, "estudios/importar_puntos.html", {
        "form": form, "resultado": resultado, "expediente": expediente,
    })


@login_required
def expediente_detalle(request, pk):
    expediente = get_object_or_404(
        Expediente.objects.prefetch_related("puntos__consumos", "ofertas"), pk=pk
    )
    comparativo = None
    detalle_cups = []
    grafico = []
    mejor = None
    if expediente.ofertas.exists() and expediente.puntos.exists():
        comparativo = comparativo_expediente(expediente)
        detalle_cups = _detalle_cups(comparativo)
        grafico = _grafico(comparativo)
        mejor = next((c for c in comparativo["columnas"] if c.get("mejor")), None)
        if mejor and mejor["ahorro"] is not None:
            mejor["ahorro_abs"] = abs(mejor["ahorro"])
    return render(request, "estudios/expediente_detalle.html", {
        "expediente": expediente,
        "comparativo": comparativo,
        "detalle_cups": detalle_cups,
        "grafico": grafico,
        "mejor": mejor,
    })


# ------------------------------------------------------------------ Usuarios

def _es_admin(u):
    return u.is_active and u.is_staff


@user_passes_test(_es_admin)
def usuarios(request):
    lista = (User.objects.annotate(n_expedientes=Count("expedientes", distinct=True))
             .order_by("-is_active", "-is_staff", "username"))
    return render(request, "estudios/usuarios.html", {"usuarios": lista})


@user_passes_test(_es_admin)
def usuario_nuevo(request):
    if request.method == "POST":
        form = UsuarioAltaForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(request, f"Usuario «{usuario.username}» creado como "
                                      f"{'administrador' if usuario.is_staff else 'técnico'}.")
            return redirect("usuarios")
    else:
        form = UsuarioAltaForm(initial={"rol": "tecnico", "is_active": True})
    return render(request, "estudios/usuario_form.html", {"form": form, "modo": "nuevo"})


@user_passes_test(_es_admin)
def usuario_editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            # Salvaguardas: un admin no puede degradarse ni desactivarse a sí mismo
            # (evita que el equipo se quede sin administradores).
            if usuario == request.user:
                if form.cleaned_data.get("rol") != "admin":
                    form.add_error("rol", "No puedes retirarte a ti mismo el rol de administrador.")
                if not form.cleaned_data.get("is_active"):
                    form.add_error("is_active", "No puedes desactivar tu propia cuenta.")
            if form.is_valid():
                form.save()
                messages.success(request, f"Usuario «{usuario.username}» actualizado.")
                return redirect("usuarios")
    else:
        form = UsuarioForm(instance=usuario)
    return render(request, "estudios/usuario_form.html",
                  {"form": form, "modo": "editar", "usuario": usuario})

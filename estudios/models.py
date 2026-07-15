from django.conf import settings
from django.db import models


class Tarifa(models.TextChoices):
    T20TD = "2.0TD", "2.0TD"
    T30TD = "3.0TD", "3.0TD"
    T61TD = "6.1TD", "6.1TD"
    T62TD = "6.2TD", "6.2TD"
    T63TD = "6.3TD", "6.3TD"
    T64TD = "6.4TD", "6.4TD"


class Expediente(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "abierto", "Abierto"
        CERRADO = "cerrado", "Cerrado"

    codigo = models.CharField("código", max_length=20, unique=True, editable=False)
    cliente_razon_social = models.CharField("razón social", max_length=200)
    cliente_cif = models.CharField("CIF/NIF", max_length=20)
    cliente_direccion = models.CharField("dirección fiscal", max_length=250, blank=True)
    gestor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="expedientes", verbose_name="gestor"
    )
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.ABIERTO)
    oferta_adjudicataria = models.ForeignKey(
        "Oferta", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="oferta adjudicataria",
        help_text="Al cerrar el expediente: oferta aceptada (vacío = sin adjudicación).",
    )
    observaciones = models.TextField(blank=True)
    archivo_original = models.FileField(
        "archivo Excel original", upload_to="expedientes/", null=True, blank=True,
        help_text="Copia del Excel subido al crear o reimportar el expediente.",
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "expediente"
        ordering = ["-creado"]

    @property
    def adjudicada(self):
        return self.estado == self.Estado.CERRADO and self.oferta_adjudicataria_id is not None

    def save(self, *args, **kwargs):
        if not self.codigo:
            from django.utils import timezone

            anio = timezone.now().year
            ultimo = (
                Expediente.objects.filter(codigo__startswith=f"EXP-{anio}-")
                .order_by("-codigo")
                .values_list("codigo", flat=True)
                .first()
            )
            seq = int(ultimo.rsplit("-", 1)[1]) + 1 if ultimo else 1
            self.codigo = f"EXP-{anio}-{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} · {self.cliente_razon_social}"


class PuntoSuministro(models.Model):
    class Modalidad(models.TextChoices):
        FIJO = "fijo", "Precio fijo"
        INDEXADO = "indexado", "Indexado"

    class Origen(models.TextChoices):
        EXCEL = "excel", "Plantilla Excel"
        API = "api", "API externa"
        MANUAL = "manual", "Manual"

    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="puntos")
    titular = models.CharField("titular del contrato", max_length=200, blank=True)
    cif_titular = models.CharField("CIF del titular", max_length=20, blank=True)
    cups = models.CharField("CUPS", max_length=22)
    direccion = models.CharField("dirección del suministro", max_length=250, blank=True)
    tarifa = models.CharField(max_length=6, choices=Tarifa.choices)
    origen_datos = models.CharField(max_length=10, choices=Origen.choices, default=Origen.MANUAL)

    # Potencias contratadas (kW)
    potencia_p1 = models.DecimalField("potencia P1 (kW)", max_digits=9, decimal_places=2, null=True, blank=True)
    potencia_p2 = models.DecimalField("potencia P2 (kW)", max_digits=9, decimal_places=2, null=True, blank=True)
    potencia_p3 = models.DecimalField("potencia P3 (kW)", max_digits=9, decimal_places=2, null=True, blank=True)
    potencia_p4 = models.DecimalField("potencia P4 (kW)", max_digits=9, decimal_places=2, null=True, blank=True)
    potencia_p5 = models.DecimalField("potencia P5 (kW)", max_digits=9, decimal_places=2, null=True, blank=True)
    potencia_p6 = models.DecimalField("potencia P6 (kW)", max_digits=9, decimal_places=2, null=True, blank=True)

    # Contrato actual
    comercializadora_actual = models.CharField(max_length=100, blank=True)
    modalidad_actual = models.CharField(max_length=10, choices=Modalidad.choices, default=Modalidad.FIJO)
    fecha_fin_contrato = models.DateField(null=True, blank=True)

    # Condiciones actuales: energía
    energia_peajes_incluidos = models.BooleanField(
        "peajes y cargos incluidos en precio de energía", default=True
    )
    precio_energia_p1 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_energia_p2 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_energia_p3 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_energia_p4 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_energia_p5 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_energia_p6 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    # Condiciones actuales: potencia. Si va "según ATR" se aplican los parámetros regulados vigentes.
    potencia_segun_atr = models.BooleanField("precio de potencia según ATR", default=True)
    precio_potencia_p1 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_potencia_p2 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_potencia_p3 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_potencia_p4 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_potencia_p5 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    precio_potencia_p6 = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "punto de suministro"
        verbose_name_plural = "puntos de suministro"
        constraints = [
            models.UniqueConstraint(fields=["expediente", "cups"], name="unico_cups_por_expediente"),
        ]

    def __str__(self):
        return f"{self.cups} ({self.tarifa})"


class ConsumoMensual(models.Model):
    MESES = [(i, n) for i, n in enumerate(
        ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], start=1)]

    punto = models.ForeignKey(PuntoSuministro, on_delete=models.CASCADE, related_name="consumos")
    anio = models.PositiveSmallIntegerField("año")
    mes = models.PositiveSmallIntegerField(choices=MESES)
    p1 = models.DecimalField("P1 (kWh)", max_digits=12, decimal_places=2, default=0)
    p2 = models.DecimalField("P2 (kWh)", max_digits=12, decimal_places=2, default=0)
    p3 = models.DecimalField("P3 (kWh)", max_digits=12, decimal_places=2, default=0)
    p4 = models.DecimalField("P4 (kWh)", max_digits=12, decimal_places=2, default=0)
    p5 = models.DecimalField("P5 (kWh)", max_digits=12, decimal_places=2, default=0)
    p6 = models.DecimalField("P6 (kWh)", max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "consumo mensual"
        verbose_name_plural = "consumos mensuales"
        constraints = [
            models.UniqueConstraint(fields=["punto", "anio", "mes"], name="unico_mes_por_punto"),
        ]
        ordering = ["anio", "mes"]

    @property
    def total(self):
        return self.p1 + self.p2 + self.p3 + self.p4 + self.p5 + self.p6

    def __str__(self):
        return f"{self.punto.cups} {self.get_mes_display()} {self.anio}"


class CondicionesOfertaBase(models.Model):
    """Condiciones comunes a una oferta de expediente y a una oferta de catálogo:
    comercializadora, duración, GdO, inclusión de ATR y todo el tratamiento de SSAA."""

    class SsaaTipo(models.TextChoices):
        INCLUIDO = "incluido", "Incluidos en el precio de energía"
        TECHO = "techo", "Con techo (regulariza por encima)"
        BANDA = "banda", "Con banda (ref. mínima y máxima)"
        INDEXADO = "indexado", "Indexados completos"

    class SsaaModo(models.TextChoices):
        MENSUAL = "mensual", "Promedio mensual"
        HORARIO = "horario", "Horario (con profile factors)"

    class PerdidasModo(models.TextChoices):
        CIRCULAR = "circular", "Circular CNMC 3/2020 (por periodo)"
        FIJA = "fija", "Porcentaje fijo (indicar)"

    comercializadora = models.CharField(max_length=100)
    duracion_meses = models.PositiveSmallIntegerField("duración (meses)", default=12)
    gdo = models.BooleanField("GdO (energía verde)", default=False)

    # Qué incluyen los precios ofertados
    atr_energia_incluido = models.BooleanField(
        "ATR de energía incluido en precios", default=True,
        help_text="Si no está incluido, el cálculo suma los peajes y cargos de energía vigentes.",
    )
    atr_potencia_incluido = models.BooleanField(
        "la oferta cotiza precio propio de potencia", default=False,
        help_text="Si no, la potencia se factura al ATR regulado vigente (peajes + cargos).",
    )
    # --- Tratamiento de los Servicios de Ajuste (SSAA) ---
    ssaa_tipo = models.CharField(
        "tratamiento SSAA", max_length=10, choices=SsaaTipo.choices, default=SsaaTipo.INCLUIDO
    )
    ssaa_modo = models.CharField(
        "modo SSAA", max_length=8, choices=SsaaModo.choices, default=SsaaModo.MENSUAL,
        help_text="Mensual usa el SSAA del mes; horario lo reparte por periodos con los profile factors.",
    )
    ssaa_ref_superior = models.DecimalField(
        "referencia superior SSAA (€/MWh)", max_digits=8, decimal_places=3, null=True, blank=True,
        help_text="Techo (tipo «con techo») o referencia máxima (tipo «con banda»).",
    )
    ssaa_ref_inferior = models.DecimalField(
        "referencia inferior SSAA (€/MWh)", max_digits=8, decimal_places=3, null=True, blank=True,
        help_text="Referencia mínima (solo tipo «con banda»).",
    )
    ssaa_perdidas_modo = models.CharField(
        "pérdidas en SSAA", max_length=8, choices=PerdidasModo.choices, default=PerdidasModo.CIRCULAR
    )
    ssaa_perdidas_pct = models.DecimalField(
        "pérdidas fijas (%)", max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Solo si las pérdidas son un porcentaje fijo (p. ej. 7 para AT, 17 para BT).",
    )
    ssaa_apuntamiento = models.DecimalField(
        "apuntamiento", max_digits=6, decimal_places=4, null=True, blank=True,
        help_text="Constante multiplicadora (p. ej. 1,02). Vacío = no se aplica (×1).",
    )
    ssaa_impuesto_municipal = models.BooleanField(
        "aplicar impuesto municipal (Hacienda Local)", default=False,
        help_text="Multiplica la regularización SSAA por (1 + impuesto local), p. ej. ×1,015.",
    )
    observaciones = models.TextField(
        blank=True, help_text="Letra pequeña de la oferta: cierres, condiciones, etc. Se muestra en el comparativo."
    )

    class Meta:
        abstract = True

    @property
    def etiqueta(self):
        sufijo = f" {self.duracion_meses} M" if self.duracion_meses != 12 else ""
        return f"{self.comercializadora}{sufijo}"


class Oferta(CondicionesOfertaBase):
    class Modalidad(models.TextChoices):
        FIJO = "fijo", "Precio fijo"
        INDEXADO = "indexado", "Indexado"  # fase futura

    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="ofertas")
    modalidad = models.CharField(max_length=10, choices=Modalidad.choices, default=Modalidad.FIJO)
    fecha_validez = models.DateField("válida hasta", null=True, blank=True)
    gestor_nombre = models.CharField("gestor comercial", max_length=150, blank=True)
    gestor_telefono = models.CharField("teléfono", max_length=30, blank=True)
    gestor_email = models.EmailField("email", blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "oferta"
        ordering = ["comercializadora", "duracion_meses"]

    def __str__(self):
        return f"{self.etiqueta} ({self.expediente.codigo})"


class OfertaCatalogo(CondicionesOfertaBase):
    """Oferta guardada en el catálogo, reutilizable al crear ofertas en cualquier expediente."""

    nombre = models.CharField("nombre en el catálogo", max_length=150)
    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        verbose_name = "oferta de catálogo"
        verbose_name_plural = "ofertas de catálogo"
        ordering = ["comercializadora", "nombre"]

    def __str__(self):
        return self.nombre or self.etiqueta


class PrecioOferta(models.Model):
    """Precios de una oferta, con tres niveles de aplicación (de mayor a menor prioridad):
    1) un CUPS concreto (punto), 2) todos los CUPS de una tarifa (tarifa), 3) genérico.
    """

    oferta = models.ForeignKey(Oferta, on_delete=models.CASCADE, related_name="precios")
    tarifa = models.CharField(
        max_length=6, choices=Tarifa.choices, blank=True, default="",
        help_text="Si se indica, aplica a todos los CUPS de esa tarifa del expediente.",
    )
    punto = models.ForeignKey(
        PuntoSuministro, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Si se indica, aplica solo a ese CUPS (tiene prioridad sobre la tarifa).",
    )
    energia_p1 = models.DecimalField("energía P1 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p2 = models.DecimalField("energía P2 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p3 = models.DecimalField("energía P3 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p4 = models.DecimalField("energía P4 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p5 = models.DecimalField("energía P5 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p6 = models.DecimalField("energía P6 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p1 = models.DecimalField("potencia P1 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p2 = models.DecimalField("potencia P2 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p3 = models.DecimalField("potencia P3 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p4 = models.DecimalField("potencia P4 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p5 = models.DecimalField("potencia P5 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p6 = models.DecimalField("potencia P6 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "precios de oferta"
        verbose_name_plural = "precios de oferta"
        constraints = [
            models.UniqueConstraint(fields=["oferta", "tarifa", "punto"], name="unico_precio_oferta_ambito"),
        ]

    def __str__(self):
        destino = self.punto.cups if self.punto else "todos los CUPS"
        return f"{self.oferta.etiqueta} → {destino}"


class PrecioCatalogo(models.Model):
    """Precios de una oferta de catálogo, siempre por tarifa (reutilizables entre expedientes)."""

    oferta_catalogo = models.ForeignKey("OfertaCatalogo", on_delete=models.CASCADE, related_name="precios")
    tarifa = models.CharField(max_length=6, choices=Tarifa.choices)
    energia_p1 = models.DecimalField("energía P1 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p2 = models.DecimalField("energía P2 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p3 = models.DecimalField("energía P3 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p4 = models.DecimalField("energía P4 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p5 = models.DecimalField("energía P5 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    energia_p6 = models.DecimalField("energía P6 (€/kWh)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p1 = models.DecimalField("potencia P1 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p2 = models.DecimalField("potencia P2 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p3 = models.DecimalField("potencia P3 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p4 = models.DecimalField("potencia P4 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p5 = models.DecimalField("potencia P5 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)
    potencia_p6 = models.DecimalField("potencia P6 (€/kW·año)", max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = "precios de catálogo"
        verbose_name_plural = "precios de catálogo"
        constraints = [
            models.UniqueConstraint(fields=["oferta_catalogo", "tarifa"], name="unico_precio_catalogo_tarifa"),
        ]

    def __str__(self):
        return f"{self.oferta_catalogo} → {self.tarifa}"


class ConceptoBase(models.Model):
    """Campos comunes a un concepto adicional de una oferta y de una oferta de catálogo."""

    class Tipo(models.TextChoices):
        EUR_MWH = "eur_mwh", "€/MWh sobre consumo"
        FIJO_MES = "fijo_mes", "€ fijo al mes"
        PCT_SUBTOTAL = "pct", "% sobre subtotal (potencia + energía)"

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.EUR_MWH)
    valor = models.DecimalField(
        max_digits=12, decimal_places=6,
        help_text="€/MWh, umbral €/MWh (SSAA), €/mes o % según el tipo elegido.",
    )
    con_perdidas = models.BooleanField(
        "aplicar pérdidas", default=False,
        help_text="Eleva el consumo a barras de central con los coeficientes de pérdidas vigentes.",
    )
    con_impuesto_local = models.BooleanField(
        "× impuesto local", default=False,
        help_text="Multiplica el importe por (1 + impuesto local), p. ej. ×1,015. Lo usan algunas regularizaciones de SSAA.",
    )
    entra_en_iee = models.BooleanField("forma parte de la base del IEE", default=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


class ConceptoAdicional(ConceptoBase):
    """Costes extra de una oferta: FNEE, coste GdO, gestión…"""

    oferta = models.ForeignKey(Oferta, on_delete=models.CASCADE, related_name="conceptos")

    class Meta:
        verbose_name = "concepto adicional"
        verbose_name_plural = "conceptos adicionales"


class ConceptoCatalogo(ConceptoBase):
    """Concepto adicional de una oferta de catálogo."""

    oferta_catalogo = models.ForeignKey("OfertaCatalogo", on_delete=models.CASCADE, related_name="conceptos")

    class Meta:
        verbose_name = "concepto de catálogo"
        verbose_name_plural = "conceptos de catálogo"


class ParametroRegulado(models.Model):
    """Valores regulados por periodo y tarifa, versionados por vigencia. Mantenidos por el administrador."""

    class Tipo(models.TextChoices):
        PEAJE = "peaje", "Peaje (CNMC)"
        CARGO = "cargo", "Cargo (Ministerio)"
        PERDIDAS = "perdidas", "Coeficiente de pérdidas (tanto por uno)"
        IMP_LOCAL = "imp_local", "Impuesto local (tanto por uno)"

    class Termino(models.TextChoices):
        ENERGIA = "energia", "Energía (€/kWh)"
        POTENCIA = "potencia", "Potencia (€/kW·año)"

    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    termino = models.CharField(max_length=10, choices=Termino.choices)
    tarifa = models.CharField(max_length=6, choices=Tarifa.choices)
    vigencia_inicio = models.DateField()
    vigencia_fin = models.DateField(null=True, blank=True, help_text="Vacío = sigue vigente.")
    p1 = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    p2 = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    p3 = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    p4 = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    p5 = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    p6 = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    fuente = models.CharField(max_length=250, blank=True, help_text="BOE/Resolución de origen.")
    validado = models.BooleanField(default=False, help_text="Revisado por el administrador.")

    class Meta:
        verbose_name = "parámetro regulado"
        verbose_name_plural = "parámetros regulados"
        ordering = ["tarifa", "tipo", "termino", "-vigencia_inicio"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.get_termino_display()} {self.tarifa} desde {self.vigencia_inicio}"


class ParametroGeneral(models.Model):
    """Valores escalares con vigencia: tipo del IEE, etc."""

    class Clave(models.TextChoices):
        IEE = "iee", "Impuesto especial de electricidad (tanto por uno)"

    clave = models.CharField(max_length=20, choices=Clave.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=9)
    vigencia_inicio = models.DateField()
    vigencia_fin = models.DateField(null=True, blank=True)
    fuente = models.CharField(max_length=250, blank=True)
    validado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "parámetro general"
        verbose_name_plural = "parámetros generales"
        ordering = ["clave", "-vigencia_inicio"]

    def __str__(self):
        return f"{self.get_clave_display()} = {self.valor} desde {self.vigencia_inicio}"


class SerieSSAA(models.Model):
    """Servicios de ajuste estimados por mes (€/MWh). Es un perfil mensual que se
    aplica igual sea cual sea el año del contrato (no depende del año de los consumos)."""

    mes = models.PositiveSmallIntegerField(choices=ConsumoMensual.MESES, unique=True)
    valor_considerado = models.DecimalField("SSAA estimado (€/MWh)", max_digits=8, decimal_places=3)
    valor_real = models.DecimalField("SSAA real (€/MWh, referencia)", max_digits=8, decimal_places=3, null=True, blank=True)
    anio = models.PositiveSmallIntegerField(
        "año de referencia", null=True, blank=True,
        help_text="Informativo: de qué año son estos valores (para saber lo actualizados que están).",
    )

    class Meta:
        verbose_name = "SSAA mensual"
        verbose_name_plural = "serie SSAA mensual (por mes)"
        ordering = ["mes"]

    def __str__(self):
        return f"SSAA {self.get_mes_display()}: {self.valor_considerado} €/MWh"


class ProfileFactor(models.Model):
    """Perfiles horarios (profile factors) por mes y periodo. Reparten el SSAA
    mensual entre los periodos cuando la oferta aplica los SSAA de forma horaria.
    Un mismo ámbito cubre varias tarifas (p. ej. Península 3.0TD y 6.xTD)."""

    class Ambito(models.TextChoices):
        PENINSULA_3_6 = "peninsula_3_6", "Península 3.0TD y 6.xTD"
        PENINSULA_20 = "peninsula_20", "Península 2.0TD"
        CANARIAS = "canarias", "Canarias"
        BALEARES = "baleares", "Baleares"

    ambito = models.CharField(max_length=20, choices=Ambito.choices, default=Ambito.PENINSULA_3_6)
    mes = models.PositiveSmallIntegerField(choices=ConsumoMensual.MESES)
    anio = models.PositiveSmallIntegerField(
        "año de referencia", null=True, blank=True,
        help_text="Informativo: de qué año es este perfil.",
    )
    p1 = models.DecimalField("P1", max_digits=8, decimal_places=4, null=True, blank=True)
    p2 = models.DecimalField("P2", max_digits=8, decimal_places=4, null=True, blank=True)
    p3 = models.DecimalField("P3", max_digits=8, decimal_places=4, null=True, blank=True)
    p4 = models.DecimalField("P4", max_digits=8, decimal_places=4, null=True, blank=True)
    p5 = models.DecimalField("P5", max_digits=8, decimal_places=4, null=True, blank=True)
    p6 = models.DecimalField("P6", max_digits=8, decimal_places=4, null=True, blank=True)

    # Tarifas que usan cada ámbito (para mapear un CUPS a su perfil).
    TARIFAS_POR_AMBITO = {
        "peninsula_3_6": ("3.0TD", "6.1TD", "6.2TD", "6.3TD", "6.4TD"),
        "peninsula_20": ("2.0TD",),
    }

    class Meta:
        verbose_name = "profile factor mensual"
        verbose_name_plural = "profile factors (perfiles horarios)"
        ordering = ["ambito", "mes"]
        constraints = [
            models.UniqueConstraint(fields=["ambito", "mes"], name="unico_profile_ambito_mes"),
        ]

    def __str__(self):
        return f"PF {self.get_ambito_display()} {self.get_mes_display()}"

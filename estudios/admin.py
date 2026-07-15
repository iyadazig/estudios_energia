from django.contrib import admin

from .models import (
    ConceptoAdicional,
    ConsumoMensual,
    Expediente,
    Oferta,
    ParametroGeneral,
    ParametroRegulado,
    ConceptoCatalogo,
    OfertaCatalogo,
    PrecioCatalogo,
    PrecioOferta,
    ProfileFactor,
    PuntoSuministro,
    SerieSSAA,
)

admin.site.site_header = "Estudios Energía GEYPE — Administración"
admin.site.site_title = "Estudios Energía GEYPE"
admin.site.index_title = "Parámetros y datos del sistema"


@admin.register(ParametroRegulado)
class ParametroReguladoAdmin(admin.ModelAdmin):
    list_display = ("tarifa", "tipo", "termino", "vigencia_inicio", "vigencia_fin",
                    "p1", "p2", "p3", "p4", "p5", "p6", "validado")
    list_filter = ("tarifa", "tipo", "termino", "validado")
    list_editable = ("validado",)
    ordering = ("tarifa", "tipo", "termino", "-vigencia_inicio")


@admin.register(ParametroGeneral)
class ParametroGeneralAdmin(admin.ModelAdmin):
    list_display = ("clave", "valor", "vigencia_inicio", "vigencia_fin", "validado")
    list_editable = ("validado",)


@admin.register(SerieSSAA)
class SerieSSAAAdmin(admin.ModelAdmin):
    list_display = ("mes", "valor_considerado", "valor_real", "anio")
    list_editable = ("valor_considerado", "valor_real", "anio")


@admin.register(ProfileFactor)
class ProfileFactorAdmin(admin.ModelAdmin):
    list_display = ("ambito", "mes", "p1", "p2", "p3", "p4", "p5", "p6", "anio")
    list_editable = ("p1", "p2", "p3", "p4", "p5", "p6")
    list_filter = ("ambito",)
    ordering = ("ambito", "mes")


class ConsumoInline(admin.TabularInline):
    model = ConsumoMensual
    extra = 0


@admin.register(PuntoSuministro)
class PuntoSuministroAdmin(admin.ModelAdmin):
    list_display = ("cups", "expediente", "titular", "tarifa", "comercializadora_actual",
                    "modalidad_actual", "potencia_segun_atr", "origen_datos")
    list_filter = ("tarifa", "modalidad_actual", "origen_datos")
    search_fields = ("cups", "titular", "expediente__cliente_razon_social")
    inlines = [ConsumoInline]


class PuntoInline(admin.TabularInline):
    model = PuntoSuministro
    extra = 0
    fields = ("cups", "titular", "tarifa", "comercializadora_actual", "modalidad_actual")
    show_change_link = True


class OfertaInline(admin.TabularInline):
    model = Oferta
    extra = 0
    fields = ("comercializadora", "duracion_meses", "gdo", "fecha_validez")
    show_change_link = True


@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    list_display = ("codigo", "cliente_razon_social", "cliente_cif", "gestor", "estado", "creado")
    list_filter = ("estado", "gestor")
    search_fields = ("codigo", "cliente_razon_social", "cliente_cif")
    inlines = [PuntoInline, OfertaInline]


class PrecioOfertaInline(admin.TabularInline):
    model = PrecioOferta
    extra = 0


class ConceptoAdicionalInline(admin.TabularInline):
    model = ConceptoAdicional
    extra = 0


@admin.register(Oferta)
class OfertaAdmin(admin.ModelAdmin):
    list_display = ("comercializadora", "expediente", "duracion_meses", "modalidad", "gdo",
                    "atr_energia_incluido", "atr_potencia_incluido", "fecha_validez")
    list_filter = ("modalidad", "gdo", "comercializadora")
    search_fields = ("comercializadora", "expediente__codigo", "expediente__cliente_razon_social")
    inlines = [PrecioOfertaInline, ConceptoAdicionalInline]


class PrecioCatalogoInline(admin.TabularInline):
    model = PrecioCatalogo
    extra = 0


class ConceptoCatalogoInline(admin.TabularInline):
    model = ConceptoCatalogo
    extra = 0


@admin.register(OfertaCatalogo)
class OfertaCatalogoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "comercializadora", "duracion_meses", "gdo", "ssaa_tipo", "creado_por", "creado")
    list_filter = ("comercializadora", "ssaa_tipo", "gdo")
    search_fields = ("nombre", "comercializadora")
    inlines = [PrecioCatalogoInline, ConceptoCatalogoInline]

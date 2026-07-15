from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Devuelve d[key] en plantillas (Django no permite indexar por variable)."""
    if not d:
        return None
    return d.get(key)


@register.filter
def incluye(d, key):
    """True si el concepto `key` existe en el desglose (aunque valga 0).

    Sirve para distinguir "esta oferta no lleva este concepto" (se muestra
    'incluido precio energía') de "lo lleva con importe 0".
    """
    return bool(d) and key in d

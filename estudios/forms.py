from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from .models import ConceptoAdicional, Expediente, Oferta, OfertaCatalogo


class ExpedienteForm(forms.ModelForm):
    class Meta:
        model = Expediente
        fields = ["cliente_razon_social", "cliente_cif", "cliente_direccion",
                  "estado", "oferta_adjudicataria", "observaciones"]
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La oferta adjudicataria solo puede ser una de las ofertas de este expediente.
        campo = self.fields["oferta_adjudicataria"]
        campo.required = False
        campo.empty_label = "— Sin adjudicación —"
        if self.instance and self.instance.pk:
            campo.queryset = self.instance.ofertas.all()
        else:
            campo.queryset = Oferta.objects.none()

    def clean(self):
        datos = super().clean()
        # Si el expediente queda abierto, no hay adjudicataria.
        if datos.get("estado") != Expediente.Estado.CERRADO:
            datos["oferta_adjudicataria"] = None
        return datos


class ImportarPlantillaForm(forms.Form):
    fichero = forms.FileField(
        label="Plantilla rellenada (.xlsx)",
        help_text="Plantilla de Estudio de Renovación v2 con las hojas Cliente, Suministros y Consumos.",
    )


class ImportarParametrosForm(forms.Form):
    fichero = forms.FileField(
        label="Plantilla de parámetros (.xlsx)",
        help_text="Con las hojas Regulados, Generales y SSAA.",
    )


class OfertaForm(forms.ModelForm):
    class Meta:
        model = Oferta
        fields = ["comercializadora", "duracion_meses", "gdo", "fecha_validez",
                  "gestor_nombre", "gestor_telefono", "gestor_email",
                  "atr_energia_incluido", "atr_potencia_incluido",
                  "ssaa_tipo", "ssaa_modo", "ssaa_ref_superior", "ssaa_ref_inferior",
                  "ssaa_perdidas_modo", "ssaa_perdidas_pct", "ssaa_apuntamiento",
                  "ssaa_impuesto_municipal", "observaciones"]
        widgets = {
            "observaciones": forms.Textarea(attrs={"rows": 2}),
            "fecha_validez": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean(self):
        datos = super().clean()
        tipo = datos.get("ssaa_tipo")
        if tipo == "techo" and datos.get("ssaa_ref_superior") is None:
            self.add_error("ssaa_ref_superior", "Indica el techo (referencia superior) del SSAA.")
        if tipo == "banda":
            if datos.get("ssaa_ref_superior") is None or datos.get("ssaa_ref_inferior") is None:
                self.add_error("ssaa_ref_inferior", "La banda necesita referencia mínima y máxima.")
        if datos.get("ssaa_perdidas_modo") == "fija" and datos.get("ssaa_perdidas_pct") is None:
            self.add_error("ssaa_perdidas_pct", "Indica el porcentaje de pérdidas fijo.")
        return datos


def concepto_formset(extra=1):
    """Formset de conceptos de una oferta; extra ajustable para prerellenar desde catálogo."""
    return inlineformset_factory(
        Oferta, ConceptoAdicional,
        fields=["nombre", "tipo", "valor", "con_perdidas", "con_impuesto_local", "entra_en_iee"],
        extra=extra, can_delete=True,
    )


ConceptoFormSet = concepto_formset(1)


class OfertaCatalogoNombreForm(forms.ModelForm):
    """Nombre (y observaciones) para guardar/renombrar una oferta de catálogo."""

    class Meta:
        model = OfertaCatalogo
        fields = ["nombre", "observaciones"]
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 2})}


# ------------------------------------------------------------------ Usuarios

ROLES_USUARIO = [("tecnico", "Técnico"), ("admin", "Administrador")]


class UsuarioForm(forms.ModelForm):
    """Alta/edición de usuarios desde la app (solo admin).

    El rol se mapea a `is_staff`: Técnico = usuario normal, Administrador = acceso
    a Parámetros/Usuarios. La contraseña es opcional al editar (en blanco = no cambia)
    y obligatoria al dar de alta (subclase `UsuarioAltaForm`). No se expone
    `is_superuser` para evitar escaladas de privilegios.
    """

    requiere_password = False

    rol = forms.ChoiceField(choices=ROLES_USUARIO, label="Rol")
    password1 = forms.CharField(
        label="Contraseña", widget=forms.PasswordInput, required=False,
        help_text="Al editar, déjala en blanco para no cambiarla.",
    )
    password2 = forms.CharField(label="Repetir contraseña", widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]
        labels = {"username": "Usuario", "first_name": "Nombre", "last_name": "Apellidos",
                  "email": "Email", "is_active": "Cuenta activa"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        if self.instance and self.instance.pk and not self.is_bound:
            self.fields["rol"].initial = "admin" if self.instance.is_staff else "tecnico"

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if self.requiere_password and not p1:
            self.add_error("password1", "La contraseña es obligatoria al crear el usuario.")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Las contraseñas no coinciden.")
            else:
                try:
                    validate_password(p1, self.instance)
                except ValidationError as e:
                    self.add_error("password1", e)
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.is_staff = self.cleaned_data["rol"] == "admin"
        clave = self.cleaned_data.get("password1")
        if clave:
            usuario.set_password(clave)
        if commit:
            usuario.save()
        return usuario


class UsuarioAltaForm(UsuarioForm):
    """Alta de usuario: la contraseña es obligatoria."""

    requiere_password = True

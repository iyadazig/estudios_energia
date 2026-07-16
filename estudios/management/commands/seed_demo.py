"""Siembra datos de DEMOSTRACIÓN para el despliegue público (TFM).

Crea (de forma idempotente):
- un usuario administrador de prueba y un usuario técnico de prueba, con
  credenciales conocidas (ver README) para que el revisor pueda entrar;
- los parámetros regulados vigentes (llama a `cargar_parametros_2026`);
- un expediente de ejemplo con un CUPS, 12 meses de consumo y dos ofertas,
  para que la portada y el comparativo se vean con datos.

NO usar en la instalación real de la empresa (usa datos sintéticos). Pensado
para la instancia de demostración desplegada.

Uso:
    python manage.py seed_demo
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand

from estudios.importador import LETRAS_CONTROL_CUPS
from estudios.models import ConsumoMensual, Expediente, Oferta, PrecioOferta, PuntoSuministro

# Credenciales de demostración (documentadas en el README). Cámbialas con variables
# de entorno DEMO_ADMIN_PASS / DEMO_TECNICO_PASS si quieres otras.
from decouple import config

DEMO_ADMIN = ("demo", config("DEMO_ADMIN_PASS", default="Demo.2026"))
DEMO_TECNICO = ("tecnico", config("DEMO_TECNICO_PASS", default="Demo.2026"))


def _cups(digitos16):
    resto = int(digitos16) % 529
    c, m = divmod(resto, 23)
    return "ES" + digitos16 + LETRAS_CONTROL_CUPS[c] + LETRAS_CONTROL_CUPS[m]


class Command(BaseCommand):
    help = "Crea usuarios, parámetros y un expediente de demostración (para el despliegue)."

    def handle(self, *args, **options):
        # 1) Usuarios de prueba
        admin, _ = User.objects.get_or_create(
            username=DEMO_ADMIN[0],
            defaults={"first_name": "Admin", "last_name": "Demo", "email": "demo@example.com"},
        )
        admin.is_staff = admin.is_superuser = admin.is_active = True
        admin.set_password(DEMO_ADMIN[1])
        admin.save()

        tecnico, _ = User.objects.get_or_create(
            username=DEMO_TECNICO[0],
            defaults={"first_name": "Técnico", "last_name": "Demo", "email": "tecnico@example.com"},
        )
        tecnico.is_staff = False
        tecnico.is_active = True
        tecnico.set_password(DEMO_TECNICO[1])
        tecnico.save()
        self.stdout.write(self.style.SUCCESS("Usuarios demo creados: demo (admin) y tecnico."))

        # 2) Parámetros regulados vigentes
        call_command("cargar_parametros_2026")

        # 3) Expediente de ejemplo (datos sintéticos)
        if Expediente.objects.filter(cliente_cif="B00000000").exists():
            self.stdout.write("El expediente de ejemplo ya existe; no se recrea.")
            return

        exp = Expediente.objects.create(
            cliente_razon_social="Panadería La Espiga (DEMO)", cliente_cif="B00000000",
            cliente_direccion="C/ Mayor 1, 28001 Madrid", gestor=tecnico,
        )
        punto = PuntoSuministro.objects.create(
            expediente=exp, cups=_cups("0011000000000042"), tarifa="6.1TD",
            direccion="C/ Mayor 1, 28001 Madrid", titular="Panadería La Espiga S.L.",
            comercializadora_actual="IBERDROLA", energia_peajes_incluidos=True, potencia_segun_atr=True,
            potencia_p1=40, potencia_p2=40, potencia_p3=40, potencia_p4=40, potencia_p5=40, potencia_p6=60,
            precio_energia_p1=Decimal("0.16"), precio_energia_p2=Decimal("0.14"),
            precio_energia_p3=Decimal("0.12"), precio_energia_p4=Decimal("0.10"),
            precio_energia_p5=Decimal("0.09"), precio_energia_p6=Decimal("0.11"),
        )
        perfil = [3200, 2600, 2100, 1800, 1500, 2800]
        for mes in range(1, 13):
            ConsumoMensual.objects.create(
                punto=punto, anio=2025, mes=mes,
                p1=perfil[0] + mes * 20, p2=perfil[1] + mes * 15, p3=perfil[2] + mes * 10,
                p4=perfil[3] + mes * 8, p5=perfil[4] + mes * 5, p6=perfil[5] + mes * 25,
            )

        for nombre, e in (("EDP Fijo 12M", "0.135"), ("NATURGY Fijo 24M", "0.148")):
            oferta = Oferta.objects.create(
                expediente=exp, comercializadora=nombre, duracion_meses=12,
                atr_energia_incluido=True, ssaa_tipo="incluido",
            )
            PrecioOferta.objects.create(
                oferta=oferta, tarifa="6.1TD",
                energia_p1=Decimal(e), energia_p2=Decimal(e), energia_p3=Decimal(e),
                energia_p4=Decimal(e), energia_p5=Decimal(e), energia_p6=Decimal(e),
            )
        self.stdout.write(self.style.SUCCESS(
            f"Expediente de ejemplo creado: {exp.codigo} con 1 CUPS y 2 ofertas."))

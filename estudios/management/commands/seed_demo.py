"""Siembra datos de DEMOSTRACIÓN para el despliegue público (TFM).

Deja SIEMPRE el mismo conjunto (es idempotente: borra los datos demo previos y los
vuelve a crear, sin tocar datos que no sean de demostración):
- Un administrador de prueba (`demo`) y dos técnicos de prueba (`tecnico` y `noelia`),
  con credenciales conocidas (ver README) para poder entrar y probar los filtros.
- Los parámetros regulados vigentes (llama a `cargar_parametros_2026`).
- Cuatro expedientes de ejemplo (dos por técnico); uno de ellos con DOS CUPS (multipunto)
  y otro cerrado con oferta adjudicataria. Cada CUPS con 12 meses de consumo, y cada
  expediente con 4–5 ofertas. Para ver la portada, el comparativo y los filtros.

NO usar en la instalación real de la empresa (usa datos sintéticos). Pensado para la
instancia de demostración desplegada.

Uso:
    python manage.py seed_demo
"""
from decimal import Decimal

from decouple import config
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand

from estudios.importador import LETRAS_CONTROL_CUPS
from estudios.models import ConsumoMensual, Expediente, Oferta, PrecioOferta, PuntoSuministro

# Credenciales de demostración (documentadas en el README). Se pueden sobreescribir con
# variables de entorno DEMO_ADMIN_PASS / DEMO_TECNICO_PASS / DEMO_NOELIA_PASS.
DEMO_ADMIN = ("demo", config("DEMO_ADMIN_PASS", default="Demo.2026"))
DEMO_TECNICO = ("tecnico", config("DEMO_TECNICO_PASS", default="Demo.2026"))
DEMO_NOELIA = ("noelia", config("DEMO_NOELIA_PASS", default="Noelia.2026"))

# Potencias contratadas por tarifa (kW, no decrecientes P1..P6).
POTENCIAS = {
    "6.1TD": [40, 40, 40, 40, 40, 60],
    "3.0TD": [15, 15, 15, 15, 15, 20],
}
INC = ("incluido", None, None)   # oferta con SSAA incluido en el precio


def _cups(digitos16):
    resto = int(digitos16) % 529
    c, m = divmod(resto, 23)
    return "ES" + digitos16 + LETRAS_CONTROL_CUPS[c] + LETRAS_CONTROL_CUPS[m]


class Command(BaseCommand):
    help = "Crea usuarios, parámetros y expedientes de demostración (para el despliegue)."

    def handle(self, *args, **options):
        # 1) Usuarios --------------------------------------------------------
        admin = self._usuario(DEMO_ADMIN, "Admin", "Demo", staff=True)
        tecnico = self._usuario(DEMO_TECNICO, "Técnico", "Demo", staff=False)
        noelia = self._usuario(DEMO_NOELIA, "Noelia", "Librero", staff=False)
        self.stdout.write(self.style.SUCCESS("Usuarios demo: demo (admin), tecnico, noelia."))

        # 2) Parámetros regulados -------------------------------------------
        call_command("cargar_parametros_2026")

        # 3) Expedientes de ejemplo -----------------------------------------
        # Se borran los demo previos (por su CIF sintético) y se recrean, para que el
        # conjunto sea siempre el mismo aunque se ejecute varias veces.
        cifs = ["B00000000", "B00000001", "A00000002", "B00000003"]
        Expediente.objects.filter(cliente_cif__in=cifs).delete()

        # puntos = lista de (dígitos CUPS, tarifa, dirección, escala de consumo)
        self._expediente(
            gestor=tecnico, razon="Panadería La Espiga (DEMO)", cif="B00000000",
            direccion="C/ Mayor 1, 28001 Madrid", estado="abierto",
            puntos=[("0011000000000042", "6.1TD", "C/ Mayor 1, 28001 Madrid", 1.0)],
            ofertas=[
                ("EDP", "0.135", *INC),
                ("NATURGY", "0.142", "techo", "16", None),
                ("IBERDROLA", "0.138", *INC),
                ("ENDESA", "0.149", *INC),
                ("TOTALENERGIES", "0.133", "banda", "22", "16"),
            ])
        self._expediente(
            gestor=tecnico, razon="Talleres Martín, S.L.", cif="B00000001",
            direccion="Polígono Industrial Sur, 45600 Talavera", estado="abierto",
            puntos=[
                ("0011000000000135", "6.1TD", "Polígono Industrial Sur, nave 7, 45600 Talavera", 1.7),
                ("0011000000000143", "3.0TD", "C/ Comercio 4, oficina, 45600 Talavera", 0.5),
            ],
            ofertas=[
                ("REPSOL", "0.128", *INC),
                ("IBERDROLA", "0.134", "techo", "16", None),
                ("ENDESA", "0.140", *INC),
                ("ACCIONA", "0.131", *INC),
                ("NATURGY", "0.137", *INC),
            ])
        self._expediente(
            gestor=noelia, razon="Hotel Costa Azul, S.A.", cif="A00000002",
            direccion="Paseo Marítimo 20, 29620 Torremolinos", estado="abierto",
            puntos=[("0011000000000228", "6.1TD", "Paseo Marítimo 20, 29620 Torremolinos", 2.4)],
            ofertas=[
                ("EDP", "0.145", *INC),
                ("NATURGY", "0.151", "banda", "22", "16"),
                ("IBERDROLA", "0.148", *INC),
                ("TOTALENERGIES", "0.143", *INC),
                ("ENDESA", "0.156", "techo", "16", None),
            ])
        self._expediente(
            gestor=noelia, razon="Supermercados del Valle", cif="B00000003",
            direccion="Avda. de la Constitución 15, 47001 Valladolid", estado="cerrado",
            puntos=[("0011000000000317", "6.1TD", "Avda. de la Constitución 15, 47001 Valladolid", 3.1)],
            ofertas=[
                ("ACCIONA", "0.126", *INC),
                ("IBERDROLA", "0.132", *INC),
                ("REPSOL", "0.129", "techo", "16", None),
                ("ENDESA", "0.138", *INC),
            ])
        self.stdout.write(self.style.SUCCESS(
            "Creados 4 expedientes de ejemplo (2 por técnico; Talleres Martín con 2 CUPS)."))

    # ------------------------------------------------------------------ helpers
    def _usuario(self, cred, nombre, apellido, staff):
        usuario, _ = User.objects.get_or_create(
            username=cred[0],
            defaults={"first_name": nombre, "last_name": apellido, "email": f"{cred[0]}@example.com"},
        )
        usuario.first_name, usuario.last_name = nombre, apellido
        usuario.is_staff = usuario.is_superuser = staff
        usuario.is_active = True
        usuario.set_password(cred[1])
        usuario.save()
        return usuario

    def _expediente(self, *, gestor, razon, cif, direccion, puntos, ofertas, estado):
        exp = Expediente.objects.create(
            cliente_razon_social=razon, cliente_cif=cif, cliente_direccion=direccion,
            gestor=gestor, estado=estado,
        )
        tarifas = []
        for digitos, tarifa, dir_punto, escala in puntos:
            self._punto(exp, digitos, tarifa, dir_punto, razon, escala)
            if tarifa not in tarifas:
                tarifas.append(tarifa)
        creadas = [self._oferta(exp, tarifas, *spec) for spec in ofertas]
        if estado == "cerrado" and creadas:
            # Adjudica (proxy) la oferta de menor precio de energía.
            exp.oferta_adjudicataria = min(creadas, key=lambda t: t[1])[0]
            exp.save()
        return exp

    def _punto(self, exp, digitos, tarifa, direccion, titular, escala):
        pot = POTENCIAS[tarifa]
        punto = PuntoSuministro.objects.create(
            expediente=exp, cups=_cups(digitos), tarifa=tarifa, direccion=direccion,
            titular=titular, comercializadora_actual="IBERDROLA",
            energia_peajes_incluidos=True, potencia_segun_atr=True,
            potencia_p1=pot[0], potencia_p2=pot[1], potencia_p3=pot[2],
            potencia_p4=pot[3], potencia_p5=pot[4], potencia_p6=pot[5],
            precio_energia_p1=Decimal("0.165"), precio_energia_p2=Decimal("0.150"),
            precio_energia_p3=Decimal("0.140"), precio_energia_p4=Decimal("0.120"),
            precio_energia_p5=Decimal("0.110"), precio_energia_p6=Decimal("0.130"),
        )
        base = [3200, 2600, 2100, 1800, 1500, 2800]
        for mes in range(1, 13):
            ConsumoMensual.objects.create(
                punto=punto, anio=2025, mes=mes,
                p1=int((base[0] + mes * 20) * escala), p2=int((base[1] + mes * 15) * escala),
                p3=int((base[2] + mes * 10) * escala), p4=int((base[3] + mes * 8) * escala),
                p5=int((base[4] + mes * 5) * escala), p6=int((base[5] + mes * 25) * escala),
            )
        return punto

    def _oferta(self, exp, tarifas, comercializadora, precio, ssaa_tipo, ref_sup, ref_inf):
        kw = dict(expediente=exp, comercializadora=comercializadora, duracion_meses=12,
                  atr_energia_incluido=True, ssaa_tipo=ssaa_tipo)
        if ssaa_tipo in ("techo", "banda"):
            kw.update(ssaa_modo="mensual", ssaa_perdidas_modo="fija", ssaa_perdidas_pct=Decimal("7"),
                      ssaa_impuesto_municipal=True, ssaa_ref_superior=Decimal(ref_sup))
            if ssaa_tipo == "banda":
                kw["ssaa_ref_inferior"] = Decimal(ref_inf)
        oferta = Oferta.objects.create(**kw)
        p = Decimal(precio)
        for tarifa in tarifas:   # precio por cada tarifa presente en el expediente
            PrecioOferta.objects.create(
                oferta=oferta, tarifa=tarifa,
                energia_p1=p, energia_p2=p, energia_p3=p, energia_p4=p, energia_p5=p, energia_p6=p,
            )
        return oferta, p

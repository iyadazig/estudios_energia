"""Carga inicial de parámetros regulados vigentes desde el 1/1/2026.

Fuentes oficiales:
- Peajes: Resolución CNMC 18/12/2025 (BOE-A-2025-26348).
- Cargos: Orden TED/1524/2025 (BOE-A-2025-26705).
Quedan con validado=False para que el administrador los revise en el panel.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from estudios.models import ParametroGeneral, ParametroRegulado, ProfileFactor, SerieSSAA

VIGENCIA = date(2026, 1, 1)
FUENTE_PEAJES = "Resolución CNMC 18/12/2025 (BOE-A-2025-26348)"
FUENTE_CARGOS = "Orden TED/1524/2025 (BOE-A-2025-26705)"

# tarifa -> [P1..P6] (2.0TD: potencia punta/valle en p1/p2; energía P1-P3)
PEAJES_POTENCIA = {
    "2.0TD": ["23.324952", "0.443770", "0", "0", "0", "0"],
    "3.0TD": ["14.935084", "7.894323", "2.502996", "1.907795", "0.535313", "0.535313"],
    "6.1TD": ["23.946498", "12.687713", "4.747747", "3.339695", "0.070979", "0.062703"],
    "6.2TD": ["16.786379", "9.455297", "2.502855", "1.521894", "0.059359", "0.052513"],
    "6.3TD": ["10.397365", "6.258717", "2.096386", "1.366437", "0.044362", "0.038723"],
    "6.4TD": ["6.606205", "3.935625", "0.987554", "0.686109", "0.020376", "0.013971"],
}
PEAJES_ENERGIA = {
    "2.0TD": ["0.033261", "0.016409", "0.000077", "0", "0", "0"],
    "3.0TD": ["0.027511", "0.012376", "0.004943", "0.002627", "0.000111", "0.000031"],
    "6.1TD": ["0.026785", "0.012281", "0.005133", "0.002780", "0.000120", "0.000029"],
    "6.2TD": ["0.014736", "0.007202", "0.002542", "0.001254", "0.000062", "0.000020"],
    "6.3TD": ["0.011279", "0.005324", "0.001994", "0.000995", "0.000048", "0.000014"],
    "6.4TD": ["0.008427", "0.003946", "0.001458", "0.000716", "0.000038", "0.000004"],
}
CARGOS_POTENCIA = {
    "2.0TD": ["4.379461", "0.281653", "0", "0", "0", "0"],
    "3.0TD": ["5.441843", "2.723298", "1.978538", "1.978538", "1.978538", "0.906974"],
    "6.1TD": ["5.648870", "2.826996", "2.054134", "2.054134", "2.054134", "0.941478"],
    "6.2TD": ["3.317209", "1.660371", "1.206258", "1.206258", "1.206258", "0.552868"],
    "6.3TD": ["2.656027", "1.329146", "0.965679", "0.965679", "0.965679", "0.442671"],
    "6.4TD": ["1.299240", "0.650162", "0.472451", "0.472451", "0.472451", "0.216540"],
}
CARGOS_ENERGIA = {
    "2.0TD": ["0.064292", "0.012858", "0.003215", "0", "0", "0"],
    "3.0TD": ["0.035841", "0.026538", "0.014336", "0.007168", "0.004595", "0.002867"],
    "6.1TD": ["0.019489", "0.014436", "0.007795", "0.003898", "0.002499", "0.001559"],
    "6.2TD": ["0.009144", "0.006773", "0.003658", "0.001829", "0.001172", "0.000732"],
    "6.3TD": ["0.007496", "0.005552", "0.002998", "0.001499", "0.000961", "0.000600"],
    "6.4TD": ["0.002848", "0.002109", "0.001139", "0.000570", "0.000365", "0.000228"],
}
# Coeficientes de pérdidas (Circular CNMC 3/2020). En "tanto por uno" (porcentaje/100),
# como el resto de coeficientes. 2.0TD solo tiene P1-P3.
PERDIDAS = {
    "2.0TD": ["0.167", "0.163", "0.180", "0", "0", "0"],
    "3.0TD": ["0.166", "0.175", "0.165", "0.165", "0.138", "0.180"],
    "6.1TD": ["0.067", "0.068", "0.065", "0.065", "0.043", "0.077"],
    "6.2TD": ["0.052", "0.054", "0.049", "0.050", "0.035", "0.054"],
    "6.3TD": ["0.042", "0.043", "0.040", "0.040", "0.030", "0.044"],
    "6.4TD": ["0.016", "0.016", "0.016", "0.016", "0.015", "0.017"],
}
# Impuesto local (Orden ETU/1976/2016), 1,5 % en todos los periodos. En "tanto por uno".
# Se almacena como parámetro; aún NO se aplica al cálculo de precio fijo.
IMP_LOCAL = {
    "2.0TD": ["0.015", "0.015", "0.015", "0", "0", "0"],
    "3.0TD": ["0.015", "0.015", "0.015", "0.015", "0.015", "0.015"],
    "6.1TD": ["0.015", "0.015", "0.015", "0.015", "0.015", "0.015"],
    "6.2TD": ["0.015", "0.015", "0.015", "0.015", "0.015", "0.015"],
    "6.3TD": ["0.015", "0.015", "0.015", "0.015", "0.015", "0.015"],
    "6.4TD": ["0.015", "0.015", "0.015", "0.015", "0.015", "0.015"],
}

# Serie SSAA estimada por mes (€/MWh) — estimación vigente (estudios de renovación 2026).
# mes -> (año informativo, SSAA estimado)
SSAA_SERIE = {
    1: (2026, "16.56"), 2: (2026, "26.15"), 3: (2026, "29.73"), 4: (2026, "23.89"),
    5: (2025, "23.44"), 6: (2025, "18.46"), 7: (2025, "18.09"), 8: (2025, "16.66"),
    9: (2025, "20.03"), 10: (2025, "21.36"), 11: (2025, "19.64"), 12: (2025, "17.25"),
}

# Profile factors Península 3.0TD y 6.xTD (perfiles horarios). mes -> (año, [P1..P6], None donde no aplica)
PROFILE_FACTORS = {
    1: (2026, ["1.1855", "1.0569", None, None, None, "0.9025"]),
    2: (2026, ["1.6519", "0.8137", None, None, None, "0.7408"]),
    3: (2026, [None, "1.2583", "0.9401", None, None, "0.8954"]),
    4: (2026, [None, None, None, "0.8839", "0.8305", "1.1336"]),
    5: (2026, [None, None, None, "0.7821", "0.8784", "1.1325"]),
    6: (2025, [None, None, "0.9805", "0.9430", None, "1.0314"]),
    7: (2025, ["0.9509", "0.9979", None, None, None, "1.0279"]),
    8: (2025, [None, None, "0.9759", "0.9249", None, "1.0350"]),
    9: (2025, [None, None, "1.0208", "0.8453", None, "1.0535"]),
    10: (2025, [None, None, None, "1.1386", "0.9644", "0.9391"]),
    11: (2025, [None, "1.1027", "1.0780", None, None, "0.9265"]),
    12: (2025, ["1.1747", "1.2960", None, None, None, "0.8723"]),
}


def _dec(v):
    return Decimal(v) if v is not None else None


class Command(BaseCommand):
    help = "Carga peajes, cargos e IEE vigentes desde el 1/1/2026 (pendientes de validar)."

    def handle(self, *args, **options):
        creados = 0
        bloques = [
            ("peaje", "potencia", PEAJES_POTENCIA, FUENTE_PEAJES),
            ("peaje", "energia", PEAJES_ENERGIA, FUENTE_PEAJES),
            ("cargo", "potencia", CARGOS_POTENCIA, FUENTE_CARGOS),
            ("cargo", "energia", CARGOS_ENERGIA, FUENTE_CARGOS),
            ("perdidas", "energia", PERDIDAS, "Circular CNMC 3/2020, de 15 de enero"),
            ("imp_local", "energia", IMP_LOCAL, "Orden ETU/1976/2016, de 23 de diciembre"),
        ]
        for tipo, termino, tabla, fuente in bloques:
            for tarifa, valores in tabla.items():
                _, nuevo = ParametroRegulado.objects.get_or_create(
                    tipo=tipo, termino=termino, tarifa=tarifa, vigencia_inicio=VIGENCIA,
                    defaults={
                        "p1": Decimal(valores[0]), "p2": Decimal(valores[1]),
                        "p3": Decimal(valores[2]), "p4": Decimal(valores[3]),
                        "p5": Decimal(valores[4]), "p6": Decimal(valores[5]),
                        "fuente": fuente, "validado": False,
                    },
                )
                creados += nuevo

        _, nuevo = ParametroGeneral.objects.get_or_create(
            clave="iee", vigencia_inicio=date(2024, 1, 1),
            defaults={
                "valor": Decimal("0.0511269632"),
                "fuente": "Ley 38/1992, art. 99 (tipo pleno restablecido)",
                "validado": False,
            },
        )
        creados += nuevo

        # Serie SSAA estimada por mes (con año informativo)
        for mes, (anio, valor) in SSAA_SERIE.items():
            _, nuevo = SerieSSAA.objects.get_or_create(
                mes=mes, defaults={"valor_considerado": Decimal(valor), "anio": anio},
            )
            creados += nuevo

        # Profile factors Península 3.0TD/6.xTD
        for mes, (anio, valores) in PROFILE_FACTORS.items():
            _, nuevo = ProfileFactor.objects.get_or_create(
                ambito=ProfileFactor.Ambito.PENINSULA_3_6, mes=mes,
                defaults={
                    "anio": anio,
                    "p1": _dec(valores[0]), "p2": _dec(valores[1]), "p3": _dec(valores[2]),
                    "p4": _dec(valores[3]), "p5": _dec(valores[4]), "p6": _dec(valores[5]),
                },
            )
            creados += nuevo

        self.stdout.write(self.style.SUCCESS(f"Parámetros creados: {creados} (pendientes de validar en el admin)"))

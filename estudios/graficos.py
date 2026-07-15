"""Gráficos en PNG para el informe PDF.

xhtml2pdf no sabe dibujar: ignora el ancho de los <div> y revienta con tablas
anidadas estrechas. La vía fiable es incrustar una imagen ya renderizada, así que
el gráfico se dibuja aquí con Pillow y se inserta como <img>.
"""
import io

from PIL import Image, ImageDraw, ImageFont

# Un color por periodo tarifario, en gama pastel (mismos tonos que el gráfico del Excel).
COLORES_PERIODO = [
    (228, 149, 158),  # P1 rosa
    (242, 184, 128),  # P2 naranja
    (240, 220, 150),  # P3 amarillo
    (168, 213, 181),  # P4 verde
    (158, 197, 222),  # P5 azul
    (185, 167, 212),  # P6 lila
]
GRIS = (77, 77, 79)
GRIS_SUAVE = (176, 183, 195)
BLANCO = (255, 255, 255)

ESCALA = 2  # se dibuja al doble y se reduce: bordes y texto sin dientes de sierra


def _fuente(tam):
    for nombre in ("arial.ttf", "calibri.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def _miles(v):
    return f"{int(round(v)):,}".replace(",", ".")


def _escalon(maximo):
    """Paso 'redondo' del eje Y (1-2-5 × 10^n) para tener 4-6 marcas."""
    if maximo <= 0:
        return 1
    from math import floor, log10
    exp = floor(log10(maximo / 4))
    base = 10 ** exp
    for mult in (1, 2, 2.5, 5, 10):
        if maximo / (base * mult) <= 6:
            return base * mult
    return base * 10


def grafico_consumo_apilado(meses, ancho=1000, alto=520):
    """Barras verticales apiladas por periodo (P1–P6), una barra por mes.

    `meses`: lista de dicts con 'abr' (etiqueta) y 'periodos' (6 valores en kWh),
    ya ordenados de enero a diciembre. Devuelve los bytes de un PNG.
    """
    if not meses:
        return None

    W, H = ancho * ESCALA, alto * ESCALA
    img = Image.new("RGB", (W, H), BLANCO)
    d = ImageDraw.Draw(img)
    f_eje = _fuente(15 * ESCALA)
    f_ley = _fuente(16 * ESCALA)

    # Márgenes del área de dibujo
    izq, der = 95 * ESCALA, 20 * ESCALA
    arriba, abajo = 34 * ESCALA, 78 * ESCALA
    x0, x1 = izq, W - der
    y0, y1 = arriba, H - abajo

    totales = [float(sum(m["periodos"])) for m in meses]
    maximo = max(totales) if totales else 0
    paso = _escalon(maximo)
    tope = (int(maximo / paso) + 1) * paso if maximo else paso

    # Eje Y: marcas, rejilla y etiquetas
    marca = 0
    while marca <= tope + 1e-9:
        y = y1 - (marca / tope) * (y1 - y0)
        d.line([(x0, y), (x1, y)], fill=GRIS_SUAVE, width=1 * ESCALA)
        etiqueta = _miles(marca)
        caja = d.textbbox((0, 0), etiqueta, font=f_eje)
        d.text((x0 - 10 * ESCALA - (caja[2] - caja[0]), y - (caja[3] - caja[1]) / 2 - 2 * ESCALA),
               etiqueta, font=f_eje, fill=GRIS)
        marca += paso
    d.text((10 * ESCALA, 6 * ESCALA), "kWh", font=f_eje, fill=GRIS)

    # Barras apiladas: P1 abajo, P6 arriba
    n = len(meses)
    hueco = (x1 - x0) / n
    barra = hueco * 0.62
    for i, m in enumerate(meses):
        cx = x0 + hueco * (i + 0.5)
        bx0, bx1 = cx - barra / 2, cx + barra / 2
        base = y1
        for p, valor in enumerate(m["periodos"]):
            v = float(valor)
            if v <= 0:
                continue
            altura = (v / tope) * (y1 - y0)
            # Filo blanco: en gama pastel los tramos contiguos se confundirían.
            d.rectangle([bx0, base - altura, bx1, base], fill=COLORES_PERIODO[p],
                        outline=BLANCO, width=1 * ESCALA)
            base -= altura
        # Total encima de la barra
        total = _miles(totales[i])
        caja = d.textbbox((0, 0), total, font=f_eje)
        d.text((cx - (caja[2] - caja[0]) / 2, base - 20 * ESCALA), total, font=f_eje, fill=GRIS)
        # Etiqueta del mes
        caja = d.textbbox((0, 0), m["abr"], font=f_eje)
        d.text((cx - (caja[2] - caja[0]) / 2, y1 + 8 * ESCALA), m["abr"], font=f_eje, fill=GRIS)

    d.line([(x0, y1), (x1, y1)], fill=GRIS, width=2 * ESCALA)

    # Leyenda de periodos (solo los que tienen consumo)
    usados = [p for p in range(6) if any(float(m["periodos"][p]) > 0 for m in meses)]
    ancho_item = 70 * ESCALA
    total_leyenda = len(usados) * ancho_item
    lx = (W - total_leyenda) / 2
    ly = H - 30 * ESCALA
    for p in usados:
        d.rectangle([lx, ly, lx + 14 * ESCALA, ly + 14 * ESCALA], fill=COLORES_PERIODO[p])
        d.text((lx + 20 * ESCALA, ly - 1 * ESCALA), f"P{p + 1}", font=f_ley, fill=GRIS)
        lx += ancho_item

    img = img.resize((ancho, alto), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

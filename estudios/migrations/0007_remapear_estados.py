from django.db import migrations


def remapear(apps, schema_editor):
    Expediente = apps.get_model("estudios", "Expediente")
    Expediente.objects.filter(estado="presentado").update(estado="abierto")
    Expediente.objects.filter(estado__in=["ganado", "perdido"]).update(estado="cerrado")


def revertir(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("estudios", "0006_expediente_oferta_adjudicataria_and_more"),
    ]
    operations = [
        migrations.RunPython(remapear, revertir),
    ]

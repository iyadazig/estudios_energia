from django.db import migrations


def borrar(apps, schema_editor):
    ConceptoAdicional = apps.get_model("estudios", "ConceptoAdicional")
    ConceptoAdicional.objects.filter(tipo="ssaa_umbral").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("estudios", "0008_oferta_ssaa_apuntamiento_and_more"),
    ]
    operations = [
        migrations.RunPython(borrar, migrations.RunPython.noop),
    ]

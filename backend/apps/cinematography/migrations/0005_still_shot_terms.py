from django.db import migrations


def add_terms(apps, schema_editor):
    Technique = apps.get_model('cinematography', 'Technique')
    for slug, name, description in [
        ('extreme-close-up', 'Extreme close-up', 'A small facial feature or subject detail occupies most of the image.'),
        ('medium-close-up', 'Medium close-up', 'The principal person is framed approximately from the chest or shoulders upward.'),
        ('medium-shot', 'Medium shot', 'The principal person is framed approximately from the waist upward.'),
        ('full-shot', 'Full shot', 'The principal person is visible from head to feet.'),
    ]:
        Technique.objects.get_or_create(slug=slug, defaults=dict(name=name, description=description, category='Framing', automatic=False))


class Migration(migrations.Migration):
    dependencies = [('cinematography', '0004_technique_traileranalysis_studycard_and_more')]
    operations = [migrations.RunPython(add_terms, migrations.RunPython.noop)]

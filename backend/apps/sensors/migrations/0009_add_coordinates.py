# Generated manually to add longitude and latitude fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sensors", "0008_manual_sensor_data"),
    ]

    operations = [
        migrations.AddField(
            model_name='manualsensordata',
            name='longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='东经为正，西经为负',
                max_digits=10,
                null=True,
                verbose_name='经度'
            ),
        ),
        migrations.AddField(
            model_name='manualsensordata',
            name='latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='北纬为正，南纬为负',
                max_digits=10,
                null=True,
                verbose_name='纬度'
            ),
        ),
        migrations.AddField(
            model_name='sensordata',
            name='longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='东经为正，西经为负',
                max_digits=10,
                null=True,
                verbose_name='经度'
            ),
        ),
        migrations.AddField(
            model_name='sensordata',
            name='latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='北纬为正，南纬为负',
                max_digits=10,
                null=True,
                verbose_name='纬度'
            ),
        ),
    ]

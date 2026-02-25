from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='DataSourcePreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mode', models.CharField(choices=[('auto', '自动'), ('manual', '手动')], default='auto', max_length=20, verbose_name='数据源模式')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '数据源偏好',
                'verbose_name_plural': '数据源偏好',
            },
        ),
    ]

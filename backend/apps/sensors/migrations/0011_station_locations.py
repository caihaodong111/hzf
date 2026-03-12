from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sensors", "0010_station_snapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="StationLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "station_id",
                    models.CharField(
                        blank=True,
                        help_text="优先用于匹配；允许为空（部分来源可能没有稳定ID）",
                        max_length=50,
                        null=True,
                        unique=True,
                        verbose_name="站点ID",
                    ),
                ),
                (
                    "station_name",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=100,
                        null=True,
                        verbose_name="站点名称/断面名称",
                    ),
                ),
                ("province", models.CharField(blank=True, db_index=True, max_length=50, null=True, verbose_name="省份")),
                ("city", models.CharField(blank=True, db_index=True, max_length=50, null=True, verbose_name="城市")),
                (
                    "longitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=7,
                        help_text="东经为正，西经为负",
                        max_digits=10,
                        null=True,
                        verbose_name="经度",
                    ),
                ),
                (
                    "latitude",
                    models.DecimalField(
                        blank=True,
                        decimal_places=7,
                        help_text="北纬为正，南纬为负",
                        max_digits=10,
                        null=True,
                        verbose_name="纬度",
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        help_text="amap/manual/import/other",
                        max_length=20,
                        null=True,
                        verbose_name="坐标来源",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "站点坐标",
                "verbose_name_plural": "站点坐标",
                "db_table": "station_locations",
            },
        ),
        migrations.AddIndex(
            model_name="stationlocation",
            index=models.Index(fields=["station_name", "province", "city"], name="station_loc_name_area_idx"),
        ),
        migrations.AddIndex(
            model_name="stationlocation",
            index=models.Index(fields=["province", "city"], name="station_loc_area_idx"),
        ),
    ]


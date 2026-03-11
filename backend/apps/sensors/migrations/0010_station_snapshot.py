from django.db import migrations, models
from django.db.utils import OperationalError


def _column_exists(cursor, table, column):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND column_name = %s
        """,
        [table, column],
    )
    return cursor.fetchone()[0] > 0


def _index_exists(cursor, table, index_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND index_name = %s
        """,
        [table, index_name],
    )
    return cursor.fetchone()[0] > 0


def _rename_column(schema_editor, table, old_name, new_name):
    cursor = schema_editor.connection.cursor()
    if not _column_exists(cursor, table, old_name):
        return
    if _column_exists(cursor, table, new_name):
        return
    try:
        schema_editor.execute(
            f"ALTER TABLE `{table}` RENAME COLUMN `{old_name}` TO `{new_name}`"
        )
        return
    except OperationalError:
        pass

    cursor.execute(
        """
        SELECT COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND column_name = %s
        """,
        [table, old_name],
    )
    row = cursor.fetchone()
    if not row:
        return
    column_type, is_nullable, default_value, extra = row
    null_clause = "NULL" if is_nullable == "YES" else "NOT NULL"
    default_clause = ""
    if default_value is not None:
        default_clause = f" DEFAULT {schema_editor.connection.ops.quote_value(default_value)}"
    extra_clause = f" {extra}" if extra else ""
    sql = (
        f"ALTER TABLE `{table}` CHANGE COLUMN `{old_name}` `{new_name}` "
        f"{column_type} {null_clause}{default_clause}{extra_clause}"
    )
    schema_editor.execute(sql)


def _sync_station_columns(apps, schema_editor):
    _rename_column(schema_editor, "sensor_data", "device_id", "station_id")
    _rename_column(schema_editor, "sensor_data", "device_name", "station_name")
    _rename_column(schema_editor, "alerts", "device_id", "station_id")
    _rename_column(schema_editor, "alerts", "device_name", "station_name")

    cursor = schema_editor.connection.cursor()
    if _index_exists(cursor, "sensor_data", "sensor_data_device_time_idx"):
        schema_editor.execute(
            "DROP INDEX `sensor_data_device_time_idx` ON `sensor_data`"
        )
    if not _index_exists(cursor, "sensor_data", "sensor_data_station_time_idx"):
        schema_editor.execute(
            "CREATE INDEX `sensor_data_station_time_idx` ON `sensor_data` (`station_id`, `recorded_at`)"
        )

    if _index_exists(cursor, "alerts", "alerts_device_time_idx"):
        schema_editor.execute(
            "DROP INDEX `alerts_device_time_idx` ON `alerts`"
        )
    if not _index_exists(cursor, "alerts", "alerts_station_time_idx"):
        schema_editor.execute(
            "CREATE INDEX `alerts_station_time_idx` ON `alerts` (`station_id`, `created_at`)"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("sensors", "0009_add_coordinates"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name="sensordata",
                    old_name="device_id",
                    new_name="station_id",
                ),
                migrations.RenameField(
                    model_name="sensordata",
                    old_name="device_name",
                    new_name="station_name",
                ),
                migrations.RenameField(
                    model_name="alert",
                    old_name="device_id",
                    new_name="station_id",
                ),
                migrations.RenameField(
                    model_name="alert",
                    old_name="device_name",
                    new_name="station_name",
                ),
                migrations.RemoveIndex(
                    model_name="sensordata",
                    name="sensor_data_device_time_idx",
                ),
                migrations.AddIndex(
                    model_name="sensordata",
                    index=models.Index(fields=["station_id", "-recorded_at"], name="sensor_data_station_time_idx"),
                ),
                migrations.RemoveIndex(
                    model_name="alert",
                    name="alerts_device_time_idx",
                ),
                migrations.AddIndex(
                    model_name="alert",
                    index=models.Index(fields=["station_id", "-created_at"], name="alerts_station_time_idx"),
                ),
            ],
            database_operations=[
                migrations.RunPython(_sync_station_columns, migrations.RunPython.noop),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="ManualSensorData"),
            ],
            database_operations=[],
        ),
        migrations.CreateModel(
            name="SensorSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("station_id", models.CharField(blank=True, db_index=True, max_length=50, null=True, verbose_name="站点ID")),
                ("station_name", models.CharField(blank=True, max_length=100, null=True, verbose_name="站点名称/断面名称")),
                ("location", models.CharField(blank=True, max_length=200, null=True, verbose_name="位置")),
                ("province", models.CharField(blank=True, max_length=50, null=True, verbose_name="省份")),
                ("city", models.CharField(blank=True, max_length=50, null=True, verbose_name="城市")),
                ("river_basin", models.CharField(blank=True, max_length=50, null=True, verbose_name="流域")),
                ("longitude", models.DecimalField(blank=True, decimal_places=7, help_text="东经为正，西经为负", max_digits=10, null=True, verbose_name="经度")),
                ("latitude", models.DecimalField(blank=True, decimal_places=7, help_text="北纬为正，南纬为负", max_digits=10, null=True, verbose_name="纬度")),
                ("temperature", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name="水温(℃)")),
                ("ph", models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True, verbose_name="pH值")),
                ("dissolved_oxygen", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name="溶解氧(mg/L)")),
                ("conductivity", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name="电导率(μS/cm)")),
                ("turbidity", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name="浊度(NTU)")),
                ("salinity", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name="盐度(‰)")),
                ("water_quality", models.CharField(blank=True, max_length=10, null=True, verbose_name="水质类别")),
                ("permanganate", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name="高锰酸盐指数(mg/L)")),
                ("ammonia_nitrogen", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name="氨氮(mg/L)")),
                ("total_phosphorus", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name="总磷(mg/L)")),
                ("total_nitrogen", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name="总氮(mg/L)")),
                ("chlorophyll_a", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, verbose_name="叶绿素a(mg/L)")),
                ("algae_density", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="藻密度(cells/L)")),
                ("data_source", models.CharField(blank=True, help_text="national/huawei/manual", max_length=50, null=True, verbose_name="数据来源")),
                ("recorded_at", models.DateTimeField(db_index=True, verbose_name="监测时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="快照更新时间")),
            ],
            options={
                "verbose_name": "传感器最新快照",
                "verbose_name_plural": "传感器最新快照",
                "db_table": "sensor_data_latest",
                "ordering": ["-recorded_at"],
            },
        ),
        migrations.AddIndex(
            model_name="sensorsnapshot",
            index=models.Index(fields=["station_id"], name="snapshot_station_idx"),
        ),
        migrations.AddIndex(
            model_name="sensorsnapshot",
            index=models.Index(fields=["recorded_at"], name="snapshot_time_idx"),
        ),
        migrations.AddIndex(
            model_name="sensorsnapshot",
            index=models.Index(fields=["province"], name="snapshot_province_idx"),
        ),
        migrations.AddIndex(
            model_name="sensorsnapshot",
            index=models.Index(fields=["city"], name="snapshot_city_idx"),
        ),
        migrations.AddIndex(
            model_name="sensorsnapshot",
            index=models.Index(fields=["river_basin"], name="snapshot_river_idx"),
        ),
        migrations.AddConstraint(
            model_name="sensorsnapshot",
            constraint=models.UniqueConstraint(fields=("station_id",), name="snapshot_station_uniq"),
        ),
    ]

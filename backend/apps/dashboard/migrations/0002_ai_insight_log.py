from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AiInsightLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("question", models.TextField(verbose_name="问题")),
                ("answer", models.TextField(blank=True, null=True, verbose_name="回答")),
                ("model", models.CharField(blank=True, max_length=100, null=True, verbose_name="模型")),
                ("success", models.BooleanField(default=False, verbose_name="是否成功")),
                ("error_message", models.TextField(blank=True, null=True, verbose_name="错误信息")),
                ("request_payload", models.JSONField(blank=True, null=True, verbose_name="请求上下文")),
                ("response_meta", models.JSONField(blank=True, null=True, verbose_name="响应元信息")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP地址")),
                ("user_agent", models.TextField(blank=True, null=True, verbose_name="User-Agent")),
                ("duration_ms", models.IntegerField(blank=True, null=True, verbose_name="耗时(ms)")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
            ],
            options={
                "verbose_name": "AI问答记录",
                "verbose_name_plural": "AI问答记录",
                "db_table": "ai_insight_logs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="aiinsightlog",
            index=models.Index(fields=["-created_at"], name="ai_log_created_idx"),
        ),
        migrations.AddIndex(
            model_name="aiinsightlog",
            index=models.Index(fields=["success", "-created_at"], name="ai_log_success_idx"),
        ),
        migrations.AddIndex(
            model_name="aiinsightlog",
            index=models.Index(fields=["model", "-created_at"], name="ai_log_model_idx"),
        ),
    ]


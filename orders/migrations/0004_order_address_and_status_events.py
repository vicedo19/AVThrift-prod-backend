from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0003_update_idempotency_scope_and_constraints"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="shipping_address",
            field=models.JSONField(null=True, blank=True),
        ),
        migrations.CreateModel(
            name="OrderStatusEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "from_status",
                    models.CharField(
                        max_length=16, choices=[("pending", "Pending"), ("paid", "Paid"), ("cancelled", "Cancelled")]
                    ),
                ),
                (
                    "to_status",
                    models.CharField(
                        max_length=16, choices=[("pending", "Pending"), ("paid", "Paid"), ("cancelled", "Cancelled")]
                    ),
                ),
                ("reason", models.CharField(max_length=200, blank=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, related_name="status_events", to="orders.order"
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="orderstatusevent",
            index=models.Index(fields=["order", "created_at"], name="orders_event_order_created_idx"),
        ),
    ]

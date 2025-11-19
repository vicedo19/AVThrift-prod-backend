from django.db import migrations, models


def populate_scope(apps, schema_editor):
    IdempotencyKey = apps.get_model("orders", "IdempotencyKey")
    for idem in IdempotencyKey.objects.all().iterator():
        if not getattr(idem, "scope", None):
            if getattr(idem, "user_id", None):
                idem.scope = f"user:{idem.user_id}"
            else:
                idem.scope = "anon"
            idem.save(update_fields=["scope"])


def noop_reverse(apps, schema_editor):
    # No-op reverse; scope values can remain as-is
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_remove_order_discount_total_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="idempotencykey",
            name="scope",
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="idempotencykey",
            name="request_hash",
            field=models.CharField(max_length=64, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="idempotencykey",
            name="expires_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.RemoveConstraint(
            model_name="idempotencykey",
            name="uniq_idem_user_path_method",
        ),
        migrations.RunPython(populate_scope, noop_reverse),
        migrations.AlterField(
            model_name="idempotencykey",
            name="scope",
            field=models.CharField(max_length=128),
        ),
        migrations.AddConstraint(
            model_name="idempotencykey",
            constraint=models.UniqueConstraint(
                fields=("key", "scope", "path", "method"), name="uniq_idem_scope_path_method"
            ),
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentintent",
            name="order",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payment_intents",
                to="orders.order",
                db_index=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentintent",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gte", 0)), name="paymentintent_amount_non_negative"
            ),
        ),
    ]

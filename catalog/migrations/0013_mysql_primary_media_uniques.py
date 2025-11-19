from django.db import migrations


def forwards(apps, schema_editor):
    # Apply only on MySQL: emulate partial unique constraints using generated columns + unique indexes
    if schema_editor.connection.vendor != "mysql":
        return

    # Add stored generated columns that project IDs only when the row is a primary
    # product media (variant is NULL) or a primary variant media.
    # Then add unique indexes on these generated columns.
    statements = [
        (
            "ALTER TABLE `catalog_media` "
            "ADD COLUMN `primary_product_id` INT GENERATED ALWAYS AS ("
            "CASE WHEN (`is_primary` AND `variant_id` IS NULL) THEN `product_id` ELSE NULL END) STORED, "
            "ADD COLUMN `primary_variant_id` INT GENERATED ALWAYS AS ("
            "CASE WHEN (`is_primary`) THEN `variant_id` ELSE NULL END) STORED"
        ),
        ("CREATE UNIQUE INDEX `uniq_primary_media_per_product_mysql` " "ON `catalog_media` (`primary_product_id`)"),
        ("CREATE UNIQUE INDEX `uniq_primary_media_per_variant_mysql` " "ON `catalog_media` (`primary_variant_id`)"),
    ]

    cursor = schema_editor.connection.cursor()
    try:
        for sql in statements:
            cursor.execute(sql)
    finally:
        cursor.close()


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return

    statements = [
        "DROP INDEX `uniq_primary_media_per_product_mysql` ON `catalog_media`",
        "DROP INDEX `uniq_primary_media_per_variant_mysql` ON `catalog_media`",
        "ALTER TABLE `catalog_media` DROP COLUMN `primary_product_id`, DROP COLUMN `primary_variant_id`",
    ]

    cursor = schema_editor.connection.cursor()
    try:
        for sql in statements:
            cursor.execute(sql)
    finally:
        cursor.close()


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0012_productvariant_catalog_pro_product_7cdb45_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

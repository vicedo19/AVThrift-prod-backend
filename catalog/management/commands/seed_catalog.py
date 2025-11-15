"""Seed initial catalog data for development sanity-check.

Creates a few categories, products with media, and a collection.
Re-running is idempotent; existing items are reused by slug/sku.
"""

from catalog.models import Category, Collection, CollectionProduct, Media, Product
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Seed initial catalog data (categories, products, media, collections)"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding catalog data...")

        # Categories
        categories = [
            ("Audio", "Audio equipment and accessories"),
            ("Video", "Video gear and accessories"),
            ("Accessories", "Cables, mounts, and other accessories"),
        ]

        cat_objs = {}
        for name, desc in categories:
            slug = slugify(name)
            cat, _ = Category.objects.get_or_create(
                slug=slug, defaults={"name": name, "description": desc, "is_active": True}
            )
            cat_objs[slug] = cat

        # Products
        products = [
            {
                "title": "Studio Monitor Speakers",
                "description": "High-fidelity nearfield monitors for accurate mixing.",
                "default_price": 299.99,
                "currency": "NGN",
                "categories": ["Audio"],
                "media": [
                    {
                        "url": "https://images.example.com/monitor-speakers-primary.jpg",
                        "alt": "Studio monitor speakers",
                        "primary": True,
                    },
                    {
                        "url": "https://images.example.com/monitor-speakers-angle.jpg",
                        "alt": "Studio monitor angled view",
                        "primary": False,
                    },
                ],
            },
            {
                "title": "HDMI 2.1 Cable 2m",
                "description": "Ultra High Speed HDMI cable supporting 8K video.",
                "default_price": 19.99,
                "currency": "NGN",
                "categories": ["Accessories", "Video"],
                "media": [
                    {
                        "url": "https://images.example.com/hdmi-cable-primary.jpg",
                        "alt": "HDMI cable",
                        "primary": True,
                    }
                ],
            },
            {
                "title": "4K Camcorder",
                "description": "Compact camcorder with 4K recording and optical stabilization.",
                "default_price": 799.0,
                "currency": "NGN",
                "categories": ["Video"],
                "media": [
                    {
                        "url": "https://images.example.com/camcorder-primary.jpg",
                        "alt": "4K camcorder",
                        "primary": True,
                    }
                ],
            },
        ]

        prod_objs = []
        for p in products:
            slug = slugify(p["title"])  # ensure uniqueness per product title
            prod, _ = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": p["title"],
                    "description": p["description"],
                    "status": Product.STATUS_PUBLISHED,
                    "default_price": p["default_price"],
                    "currency": p["currency"],
                    "seo_title": p["title"],
                },
            )
            # Categories
            for cat_name in p["categories"]:
                cat_slug = slugify(cat_name)
                cat = cat_objs.get(cat_slug)
                if cat:
                    prod.categories.add(cat)
            # Media
            if not prod.media.exists():
                for m in p["media"]:
                    Media.objects.get_or_create(
                        product=prod,
                        url=m["url"],
                        defaults={
                            "alt_text": m["alt"],
                            "is_primary": m["primary"],
                            "sort_order": 0,
                        },
                    )
            prod_objs.append(prod)

        # Collections
        featured, _ = Collection.objects.get_or_create(
            slug="featured",
            defaults={"name": "Featured", "description": "Featured products", "is_active": True, "sort_order": 0},
        )
        # Add all products to featured in curated order
        for idx, prod in enumerate(prod_objs):
            CollectionProduct.objects.get_or_create(
                collection=featured,
                product=prod,
                defaults={"sort_order": idx},
            )

        self.stdout.write(self.style.SUCCESS("Catalog seed complete."))

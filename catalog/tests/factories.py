import factory
from catalog.models import Attribute, Category, Collection, CollectionProduct, Media, Product, ProductVariant
from factory import Faker
from factory.django import DjangoModelFactory


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = Faker("word")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))
    description = Faker("sentence")
    is_active = True
    sort_order = 0


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    title = Faker("sentence", nb_words=3)
    slug = factory.LazyAttribute(lambda o: "-".join(o.title.lower().split()))
    description = Faker("paragraph")
    status = Product.STATUS_PUBLISHED
    seo_title = factory.LazyAttribute(lambda o: o.title)

    @factory.post_generation
    def categories(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for cat in extracted:
                self.categories.add(cat)


class MediaFactory(DjangoModelFactory):
    class Meta:
        model = Media

    product = factory.SubFactory(ProductFactory)
    url = Faker("image_url")
    alt_text = Faker("sentence")
    is_primary = False
    sort_order = 0


class AttributeFactory(DjangoModelFactory):
    class Meta:
        model = Attribute

    name = Faker("word")
    code = factory.LazyAttribute(lambda o: o.name.lower())
    input_type = Attribute.INPUT_SELECT
    is_filterable = True
    allowed_values = factory.LazyFunction(lambda: ["Black", "Silver"])
    sort_order = 0


class ProductVariantFactory(DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    sku = factory.Faker("bothify", text="SKU-####-???")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    # currency now owned by Product; variant inherits implicitly
    barcode = factory.Faker("ean")
    status = ProductVariant.STATUS_ACTIVE


class CollectionFactory(DjangoModelFactory):
    class Meta:
        model = Collection

    name = Faker("word")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))
    description = Faker("sentence")
    is_active = True
    sort_order = 0

    @factory.post_generation
    def products(self, create, extracted, **kwargs):
        # Backwards-compatible: allow 'products' argument to create curated ordering
        if not create:
            return
        if extracted:
            for idx, p in enumerate(extracted):
                CollectionProduct.objects.get_or_create(collection=self, product=p, defaults={"sort_order": idx})

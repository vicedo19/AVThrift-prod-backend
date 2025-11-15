import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory
from inventory.models import StockItem


class UserFactory(DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Faker("user_name")
    email = factory.Faker("email")
    password = factory.PostGenerationMethodCall("set_password", "pass")


class StockItemFactory(DjangoModelFactory):
    class Meta:
        model = StockItem

    variant = factory.SubFactory("catalog.tests.factories.ProductVariantFactory")
    quantity = 10
    reserved = 0

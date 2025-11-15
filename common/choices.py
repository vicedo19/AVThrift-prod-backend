"""Shared enumerations and choices used across apps."""

from django.db import models


class ActiveInactive(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class DraftPublished(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"


class MovementType(models.TextChoices):
    INBOUND = "in", "Inbound"
    OUTBOUND = "out", "Outbound"
    ADJUST = "adjust", "Adjust"


class ReservationState(models.TextChoices):
    ACTIVE = "active", "Active"
    RELEASED = "released", "Released"
    CONVERTED = "converted", "Converted"


class CartStatus(models.TextChoices):
    """Statuses for shopping carts."""

    ACTIVE = "active", "Active"
    ORDERED = "ordered", "Ordered"
    ABANDONED = "abandoned", "Abandoned"


class OrderStatus(models.TextChoices):
    """Lifecycle statuses for orders."""

    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


class NigerianState(models.TextChoices):
    """All Nigerian states plus FCT for address normalization."""

    ABIA = "Abia", "Abia"
    ADAMAWA = "Adamawa", "Adamawa"
    AKWA_IBOM = "Akwa Ibom", "Akwa Ibom"
    ANAMBRA = "Anambra", "Anambra"
    BAUCHI = "Bauchi", "Bauchi"
    BAYELSA = "Bayelsa", "Bayelsa"
    BENUE = "Benue", "Benue"
    BORNO = "Borno", "Borno"
    CROSS_RIVER = "Cross River", "Cross River"
    DELTA = "Delta", "Delta"
    EBONYI = "Ebonyi", "Ebonyi"
    EDO = "Edo", "Edo"
    EKITI = "Ekiti", "Ekiti"
    ENUGU = "Enugu", "Enugu"
    GOMBE = "Gombe", "Gombe"
    IMO = "Imo", "Imo"
    JIGAWA = "Jigawa", "Jigawa"
    KADUNA = "Kaduna", "Kaduna"
    KANO = "Kano", "Kano"
    KATSINA = "Katsina", "Katsina"
    KEBBI = "Kebbi", "Kebbi"
    KOGI = "Kogi", "Kogi"
    KWARA = "Kwara", "Kwara"
    LAGOS = "Lagos", "Lagos"
    NASARAWA = "Nasarawa", "Nasarawa"
    NIGER = "Niger", "Niger"
    OGUN = "Ogun", "Ogun"
    ONDO = "Ondo", "Ondo"
    OSUN = "Osun", "Osun"
    OYO = "Oyo", "Oyo"
    PLATEAU = "Plateau", "Plateau"
    RIVERS = "Rivers", "Rivers"
    SOKOTO = "Sokoto", "Sokoto"
    TARABA = "Taraba", "Taraba"
    YOBE = "Yobe", "Yobe"
    ZAMFARA = "Zamfara", "Zamfara"
    FCT = "FCT", "FCT"

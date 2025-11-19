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
    ACTIVE = "active", "Active"
    ORDERED = "ordered", "Ordered"
    ABANDONED = "abandoned", "Abandoned"


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


class PaymentIntentStatus(models.TextChoices):
    INITIALIZED = "initialized", "Initialized"
    PROCESSING = "processing", "Processing"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class PaymentProvider(models.TextChoices):
    PAYSTACK = "paystack", "Paystack"


class Currency(models.TextChoices):
    NGN = "NGN", "Nigerian Naira"
    USD = "USD", "US Dollar"
    GHS = "GHS", "Ghanaian Cedi"
    ZAR = "ZAR", "South African Rand"
    KES = "KES", "Kenyan Shilling"
    XOF = "XOF", "West African CFA Franc"


class AttributeInputType(models.TextChoices):
    TEXT = "text", "Text"
    NUMBER = "number", "Number"
    BOOLEAN = "boolean", "Boolean"
    SELECT = "select", "Select"

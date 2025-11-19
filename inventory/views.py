"""Inventory health, roadmap, and read-only list views."""

from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StockItem, StockMovement, StockReservation
from .serializers import StockItemSerializer, StockMovementSerializer, StockReservationSerializer


class InventoryHealthView(APIView):
    throttle_classes = []

    @extend_schema(
        tags=["Inventory Endpoints"],
        summary="Inventory health",
        description="Simple healthcheck endpoint for the inventory app",
        examples=[OpenApiExample("Health OK", value={"status": "ok", "app": "inventory"})],
    )
    def get(self, request):
        return Response({"status": "ok", "app": "inventory"})


class InventoryRoadmapView(APIView):
    throttle_classes = []

    @extend_schema(
        tags=["Inventory Endpoints"],
        summary="Inventory API scaffold",
        description="Placeholder endpoint describing upcoming inventory resources and endpoints.",
    )
    def get(self, request):
        return Response(
            {
                "endpoints": [
                    {"path": "/api/v1/inventory/stock-items/", "status": "planned"},
                    {"path": "/api/v1/inventory/movements/", "status": "planned"},
                ]
            }
        )


class StockItemListView(generics.ListAPIView):
    throttle_classes = []
    serializer_class = StockItemSerializer

    @extend_schema(
        tags=["Inventory Endpoints"],
        summary="List stock items",
        description=("List current stock per variant. Filters: product_id, variant_id, sku, updated_after (ISO)."),
        examples=[
            OpenApiExample(
                "Stock Items",
                value={
                    "results": [
                        {
                            "id": 1,
                            "variant": 10,
                            "sku": "SKU-0001-ABC",
                            "quantity": 5,
                            "reserved": 2,
                            "available": 3,
                            "updated_at": "2025-01-01T12:00:00Z",
                        }
                    ]
                },
            )
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = StockItem.objects.select_related("variant").order_by("-updated_at", "id")
        product_id = self.request.query_params.get("product_id")
        variant_id = self.request.query_params.get("variant_id")
        sku = self.request.query_params.get("sku")
        updated_after = self.request.query_params.get("updated_after")

        if product_id:
            qs = qs.filter(variant__product_id=product_id)
        if variant_id:
            qs = qs.filter(variant_id=variant_id)
        if sku:
            qs = qs.filter(variant__sku__iexact=sku)
        if updated_after:
            dt = parse_datetime(updated_after)
            if dt:
                qs = qs.filter(updated_at__gte=dt)
        return qs


class MovementListView(generics.ListAPIView):
    throttle_classes = []
    serializer_class = StockMovementSerializer

    @extend_schema(
        tags=["Inventory Endpoints"],
        summary="List stock movements",
        description=(
            "List movements (inbound/outbound/adjust). Filters: stock_item, movement_type, created_after (ISO)."
        ),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = StockMovement.objects.select_related("stock_item").order_by("-created_at", "id")
        stock_item = self.request.query_params.get("stock_item")
        movement_type = self.request.query_params.get("movement_type")
        created_after = self.request.query_params.get("created_after")

        if stock_item:
            qs = qs.filter(stock_item_id=stock_item)
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        if created_after:
            dt = parse_datetime(created_after)
            if dt:
                qs = qs.filter(created_at__gte=dt)
        return qs

    # Read-only list


class ReservationListView(generics.ListAPIView):
    throttle_classes = []
    serializer_class = StockReservationSerializer

    @extend_schema(
        tags=["Inventory Endpoints"],
        summary="List stock reservations",
        description=(
            "List reservations. Filters: variant_id, state (active/released/converted), expires_before (ISO)."
        ),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = StockReservation.objects.select_related("variant").order_by("-created_at", "id")
        variant_id = self.request.query_params.get("variant_id")
        state = self.request.query_params.get("state")
        expires_before = self.request.query_params.get("expires_before")

        if variant_id:
            qs = qs.filter(variant_id=variant_id)
        if state:
            qs = qs.filter(state=state)
        if expires_before:
            dt = parse_datetime(expires_before)
            if dt:
                qs = qs.filter(expires_at__lte=dt)
        return qs

    # Read-only list


# EOF

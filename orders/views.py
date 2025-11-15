"""Orders API endpoints.

Provides Order detail with optional pricing inputs via query params.
"""

from django.http import Http404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .serializers import OrderSerializer
from .services import cancel_order, compute_request_hash, pay_order, with_idempotency


class OrderDetailView(generics.RetrieveAPIView):
    """Retrieve a single order for the authenticated user.

    Optional query params: `tax`, `shipping`, `discount` to influence API totals.
    These do not persist; they only affect the response.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "orders"
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user_id=self.request.user.id)

    def get_object(self):
        try:
            return self.get_queryset().get(id=int(self.kwargs["order_id"]))
        except (Order.DoesNotExist, ValueError):
            raise Http404("Not found.")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Collect pricing overrides from query params
        pricing = {}
        for name in ("tax", "shipping", "discount"):
            val = self.request.query_params.get(name)
            if val is not None:
                pricing[name] = val
        if pricing:
            ctx["pricing"] = pricing
        return ctx

    @extend_schema(
        tags=["Orders"],
        summary="Get order detail",
        description=(
            "Retrieve a single order for the authenticated user.\n\n"
            "Optional query params `tax`, `shipping`, `discount` adjust the computed `total` in the response."
        ),
        parameters=[
            OpenApiParameter(name="tax", description="Tax amount", required=False, type=str),
            OpenApiParameter(name="shipping", description="Shipping amount", required=False, type=str),
            OpenApiParameter(name="discount", description="Discount amount", required=False, type=str),
        ],
        examples=[
            OpenApiExample(
                "With pricing inputs",
                value={
                    "id": 123,
                    "number": "ORD-000123",
                    "status": "pending",
                    "email": "user@example.com",
                    "created_at": "2025-01-01T12:00:00Z",
                    "items": [
                        {
                            "id": 10,
                            "variant": 555,
                            "product_title": "Vintage Jacket",
                            "variant_sku": "JCK-001",
                            "quantity": 2,
                            "unit_price": "25.00",
                            "line_total": "50.00",
                        }
                    ],
                    "subtotal": "50.00",
                    "tax": "4.00",
                    "shipping": "5.00",
                    "discount": "3.00",
                    "total": "56.00",
                },
            )
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class OrderPayView(APIView):
    """Mark an order as paid for the authenticated owner.

    Idempotent when `Idempotency-Key` is provided. Returns 409 on key reuse with different payload.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "orders_write"

    @extend_schema(
        tags=["Orders"],
        summary="Pay order",
        description="Marks the order as paid. Idempotent when Idempotency-Key header is set.",
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                location=OpenApiParameter.HEADER,
                required=False,
                description="Makes the request idempotent within scope+path+method",
                type=str,
            )
        ],
        responses={
            200: OrderSerializer,
            400: OrderSerializer,  # generic error shape below
        },
        examples=[
            OpenApiExample("Paid", value={"id": 1, "status": "paid"}, response_only=True),
            OpenApiExample("Mutation Error", value={"detail": "Unable to update order."}, response_only=True),
        ],
    )
    def post(self, request, order_id: int):
        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            raise Http404

        def _handler():
            try:
                updated = pay_order(order)
                data = OrderSerializer(updated, context={"request": request}).data
                return data, 200
            except ValueError:
                return {"detail": "Unable to update order."}, 400

        idem_key = request.headers.get("Idempotency-Key")
        if idem_key:
            body, code = with_idempotency(
                key=idem_key,
                user=request.user,
                path=str(request.path),
                method=str(request.method),
                request_hash=compute_request_hash(getattr(request, "data", None)),
                handler=_handler,
            )
            return Response(body, status=code)

        body, code = _handler()
        return Response(body, status=code)


class OrderCancelView(APIView):
    """Cancel an order for the authenticated owner.

    Idempotent when `Idempotency-Key` is provided. Returns 409 on key reuse with different payload.
    """

    permission_classes = [IsAuthenticated]
    throttle_scope = "orders_write"

    @extend_schema(
        tags=["Orders"],
        summary="Cancel order",
        description="Cancels the order unless it is paid. Idempotent when Idempotency-Key header is set.",
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                location=OpenApiParameter.HEADER,
                required=False,
                description="Makes the request idempotent within scope+path+method",
                type=str,
            )
        ],
        responses={
            200: OrderSerializer,
            400: OrderSerializer,
        },
        examples=[
            OpenApiExample("Cancelled", value={"id": 1, "status": "cancelled"}, response_only=True),
            OpenApiExample("Mutation Error", value={"detail": "Unable to update order."}, response_only=True),
        ],
    )
    def post(self, request, order_id: int):
        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            raise Http404

        def _handler():
            try:
                updated = cancel_order(order)
                data = OrderSerializer(updated, context={"request": request}).data
                return data, 200
            except ValueError:
                return {"detail": "Unable to update order."}, 400

        idem_key = request.headers.get("Idempotency-Key")
        if idem_key:
            body, code = with_idempotency(
                key=idem_key,
                user=request.user,
                path=str(request.path),
                method=str(request.method),
                request_hash=compute_request_hash(getattr(request, "data", None)),
                handler=_handler,
            )
            return Response(body, status=code)

        body, code = _handler()
        return Response(body, status=code)


class DefaultPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"


class OrderListView(generics.ListAPIView):
    """List authenticated user's orders with basic filters.

    Filters:
    - `status`: one of the OrderStatus values
    - `number`: exact match of order number
    - `start`: ISO date/time string; filters `created_at >= start`
    - `end`: ISO date/time string; filters `created_at <= end`
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    pagination_class = DefaultPagination
    throttle_scope = "orders"

    def get_queryset(self):
        qs = Order.objects.filter(user_id=self.request.user.id).order_by("-id").prefetch_related("items")
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        number = self.request.query_params.get("number")
        if number:
            qs = qs.filter(number=number)
        start = self.request.query_params.get("start")
        if start:
            qs = qs.filter(created_at__gte=start)
        end = self.request.query_params.get("end")
        if end:
            qs = qs.filter(created_at__lte=end)
        return qs

    @extend_schema(
        tags=["Orders"],
        summary="List orders",
        description="List current user's orders with optional filters and pagination.",
        parameters=[
            OpenApiParameter(name="status", description="Order status filter", required=False, type=str),
            OpenApiParameter(name="number", description="Order number exact match", required=False, type=str),
            OpenApiParameter(name="start", description="Created at >= start (ISO)", required=False, type=str),
            OpenApiParameter(name="end", description="Created at <= end (ISO)", required=False, type=str),
            OpenApiParameter(name="page", description="Page number", required=False, type=int),
            OpenApiParameter(name="page_size", description="Items per page", required=False, type=int),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class OrderPaymentWebhookView(APIView):
    """Webhook endpoint to mark orders as paid from payment provider events.

    This is a minimal stub for production readiness; in real deployments,
    verify signatures and restrict by IP or shared secret. Idempotent when
    `Idempotency-Key` header is provided.
    """

    permission_classes = [AllowAny]
    throttle_scope = "orders_write"

    @extend_schema(
        tags=["Orders"],
        summary="Payment webhook",
        description=(
            "Consumes a payment provider webhook and marks the order as paid.\n"
            "Expects JSON with `order_id` and `event`='payment_succeeded'.\n"
            "Idempotent when Idempotency-Key header is provided."
        ),
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                location=OpenApiParameter.HEADER,
                required=False,
                description="Makes the request idempotent within scope+path+method",
                type=str,
            )
        ],
        examples=[
            OpenApiExample(
                "Webhook Success",
                value={"order_id": 123, "event": "payment_succeeded"},
                request_only=True,
            ),
            OpenApiExample(
                "Paid",
                value={"id": 123, "status": "paid"},
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        data = getattr(request, "data", {}) or {}
        order_id = data.get("order_id")
        event = data.get("event")
        if not order_id or not event:
            return Response({"detail": "Missing order_id or event"}, status=400)
        if str(event).lower() not in {"payment_succeeded", "payment.succeeded"}:
            return Response({"detail": "Unsupported event"}, status=400)

        try:
            order = Order.objects.get(pk=int(order_id))
        except (Order.DoesNotExist, ValueError):
            raise Http404

        def _handler():
            try:
                updated = pay_order(order)
                data = OrderSerializer(updated, context={"request": request}).data
                return data, 200
            except ValueError:
                return {"detail": "Unable to update order."}, 400

        idem_key = request.headers.get("Idempotency-Key")
        if idem_key:
            body, code = with_idempotency(
                key=idem_key,
                user=getattr(request, "user", None),
                path=str(request.path),
                method=str(request.method),
                request_hash=compute_request_hash(getattr(request, "data", None)),
                handler=_handler,
            )
            return Response(body, status=code)

        body, code = _handler()
        return Response(body, status=code)

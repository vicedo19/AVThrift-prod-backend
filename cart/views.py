"""DRF views for cart operations."""

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, inline_serializer
from inventory.services import MovementError
from rest_framework import serializers as rf_serializers
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CartItem
from .selectors import get_active_cart_for_session, get_active_cart_for_user
from .serializers import (
    AddItemGuestSerializer,
    AddItemSerializer,
    CartReadSerializer,
    UpdateItemQuantityGuestSerializer,
    UpdateItemQuantitySerializer,
)
from .services import (
    CartError,
    abandon_cart,
    checkout_cart,
    clear_cart,
    clear_cart_guest,
    merge_guest_cart_to_user,
    remove_item,
    remove_item_guest,
)


class CartDetailView(APIView):
    """Return the authenticated user's active cart."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "cart"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Get active cart",
        description="Returns the authenticated user's active cart including items and totals.",
        examples=[
            OpenApiExample(
                "Cart",
                value={
                    "id": 1,
                    "items": [
                        {
                            "id": 10,
                            "variant_id": 100,
                            "quantity": 2,
                            "unit_price": "4999.00",
                            "line_total": "9998.00",
                        }
                    ],
                    "subtotal": "9998.00",
                    "total": "9998.00",
                },
            )
        ],
    )
    def get(self, request):
        cart = get_active_cart_for_user(user=request.user)
        data = CartReadSerializer.from_cart(cart=cart).data
        return Response(data, status=status.HTTP_200_OK)


class CartAddItemView(APIView):
    """Add an item to the cart."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Add item to cart",
        description="Adds a product variant to the user's cart and reserves stock.",
        request=AddItemSerializer,
        responses={
            201: inline_serializer(
                name="CartItemCreatedResponse",
                fields={"id": rf_serializers.IntegerField()},
            ),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
            404: inline_serializer(name="NotFoundError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[OpenApiExample("Added", value={"id": 10})],
    )
    def post(self, request):
        serializer = AddItemSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            item = serializer.save()
            return Response({"id": item.id}, status=status.HTTP_201_CREATED)
        except (MovementError, CartError):
            # Generic error response for reservation or cart failures
            return Response({"detail": "Unable to update cart."}, status=status.HTTP_400_BAD_REQUEST)


class CartItemUpdateView(APIView):
    """Update a cart item's quantity."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Update cart item quantity",
        description="Updates quantity and re-syncs reservation for a cart item.",
        request=UpdateItemQuantitySerializer,
        responses={
            200: inline_serializer(
                name="CartItemUpdatedResponse",
                fields={"id": rf_serializers.IntegerField()},
            ),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
            404: inline_serializer(name="NotFoundError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[OpenApiExample("Updated", value={"id": 10})],
    )
    def patch(self, request, item_id: int):
        try:
            item = CartItem.objects.get(id=item_id, cart__user_id=request.user.id)
        except CartItem.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UpdateItemQuantitySerializer(instance=item, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return Response({"id": item.id}, status=status.HTTP_200_OK)
        except (MovementError, CartError):
            return Response({"detail": "Unable to update cart."}, status=status.HTTP_400_BAD_REQUEST)


class CartItemDeleteView(APIView):
    """Remove an item from the cart."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Delete cart item",
        description="Removes a cart item and releases its reservation.",
        responses={
            204: None,
            404: inline_serializer(name="NotFoundError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[OpenApiExample("No Content", value=None)],
    )
    def delete(self, request, item_id: int):
        # Ensure item belongs to the authenticated user; otherwise return 404
        if not CartItem.objects.filter(id=item_id, cart__user_id=request.user.id).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        remove_item(user=request.user, item_id=item_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartCheckoutView(APIView):
    """Checkout the active cart and mark it ordered."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Checkout cart",
        description="Converts reservations to orders and marks the active cart as ordered.",
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                location=OpenApiParameter.HEADER,
                required=False,
                description="When provided, checkout becomes idempotent for this user+path+method",
                type=str,
            )
        ],
        responses={
            200: inline_serializer(name="CartStatusOrdered", fields={"status": rf_serializers.CharField()}),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[
            OpenApiExample("Ordered", value={"status": "ordered"}),
            OpenApiExample("Mutation Error", value={"detail": "Unable to update cart."}),
        ],
    )
    def post(self, request):
        # Idempotent checkout using orders' idempotency service when header provided
        idem_key = request.headers.get("Idempotency-Key")

        def _checkout_handler():
            order_id = checkout_cart(user=request.user)
            return {"status": "ordered", "order_id": order_id}, 200

        if idem_key:
            from orders.services import with_idempotency

            body, code = with_idempotency(
                key=idem_key,
                user=request.user,
                path=str(request.path),
                method=str(request.method),
                handler=_checkout_handler,
            )
            return Response(body, status=code)
        # Fallback: non-idempotent
        body, code = _checkout_handler()
        return Response(body, status=code)


class CartAbandonView(APIView):
    """Abandon the active cart and release reservations."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Abandon cart",
        description="Releases reservations and marks the active cart as abandoned.",
        responses={
            200: inline_serializer(name="CartStatusAbandoned", fields={"status": rf_serializers.CharField()}),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[
            OpenApiExample("Abandoned", value={"status": "abandoned"}),
            OpenApiExample("Mutation Error", value={"detail": "Unable to update cart."}),
        ],
    )
    def post(self, request):
        abandon_cart(user=request.user)
        return Response({"status": "abandoned"}, status=status.HTTP_200_OK)


class CartClearView(APIView):
    """Clear the active cart: delete items and release reservations."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Clear cart",
        description="Deletes items and releases any active reservations in the cart.",
        responses={
            200: inline_serializer(name="CartStatusCleared", fields={"status": rf_serializers.CharField()}),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[
            OpenApiExample("Cleared", value={"status": "cleared"}),
            OpenApiExample("Mutation Error", value={"detail": "Unable to update cart."}),
        ],
    )
    def post(self, request):
        clear_cart(user=request.user)
        return Response({"status": "cleared"}, status=status.HTTP_200_OK)


class GuestCartDetailView(APIView):
    """Return the guest session's active cart."""

    permission_classes = [AllowAny]
    throttle_scope = "cart"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Get guest cart",
        description="Returns the guest session cart. Provide X-Session-Id header.",
        parameters=[
            OpenApiParameter(
                name="X-Session-Id",
                location=OpenApiParameter.HEADER,
                required=True,
                description="Guest session identifier",
                type=str,
            )
        ],
        examples=[
            OpenApiExample(
                "Guest Cart",
                value={"id": 1, "items": [], "subtotal": "0.00", "total": "0.00"},
            )
        ],
    )
    def get(self, request):
        session_id = request.headers.get("X-Session-Id")
        if not session_id:
            return Response({"detail": "Missing X-Session-Id."}, status=status.HTTP_400_BAD_REQUEST)
        cart = get_active_cart_for_session(session_id=session_id)
        data = CartReadSerializer.from_cart(cart=cart).data
        return Response(data, status=status.HTTP_200_OK)


class GuestCartAddItemView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Add item to guest cart",
        description="Provide X-Session-Id header or session_id in body.",
        request=AddItemGuestSerializer,
        parameters=[
            OpenApiParameter(
                name="X-Session-Id",
                location=OpenApiParameter.HEADER,
                required=False,
                description="Guest session identifier (optional if provided in body)",
                type=str,
            )
        ],
        responses={
            201: inline_serializer(name="CartItemCreatedResponse", fields={"id": rf_serializers.IntegerField()}),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[
            OpenApiExample(
                "Guest Add",
                value={"session_id": "08b73e...", "variant_id": 123, "quantity": 2},
            )
        ],
    )
    def post(self, request):
        payload = request.data.copy()
        payload.setdefault("session_id", request.headers.get("X-Session-Id"))
        serializer = AddItemGuestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            item = serializer.save()
            return Response({"id": item.id}, status=status.HTTP_201_CREATED)
        except (MovementError, CartError):
            return Response({"detail": "Unable to update cart."}, status=status.HTTP_400_BAD_REQUEST)


class GuestCartItemUpdateView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Update guest cart item quantity",
        request=UpdateItemQuantityGuestSerializer,
        parameters=[
            OpenApiParameter(
                name="X-Session-Id",
                location=OpenApiParameter.HEADER,
                required=False,
                description="Guest session identifier (required here unless in body)",
                type=str,
            )
        ],
        responses={
            200: inline_serializer(name="CartItemUpdatedResponse", fields={"id": rf_serializers.IntegerField()}),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
            404: inline_serializer(name="NotFoundError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[
            OpenApiExample(
                "Guest Update",
                value={"session_id": "08b73e...", "quantity": 3},
            )
        ],
    )
    def patch(self, request, item_id: int):
        payload = request.data.copy()
        payload.setdefault("session_id", request.headers.get("X-Session-Id"))
        session_id = payload.get("session_id")
        if not session_id:
            return Response({"detail": "Missing X-Session-Id."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Ensure the item belongs to the guest cart
            cart = get_active_cart_for_session(session_id=session_id)
            item = CartItem.objects.get(id=item_id, cart=cart)
        except CartItem.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = UpdateItemQuantityGuestSerializer(instance=item, data=payload)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
            return Response({"id": item.id}, status=status.HTTP_200_OK)
        except (MovementError, CartError):
            return Response({"detail": "Unable to update cart."}, status=status.HTTP_400_BAD_REQUEST)


class GuestCartItemDeleteView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Delete guest cart item",
        parameters=[
            OpenApiParameter(
                name="X-Session-Id",
                location=OpenApiParameter.HEADER,
                required=True,
                description="Guest session identifier",
                type=str,
            )
        ],
        responses={
            204: None,
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
            404: inline_serializer(name="NotFoundError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[OpenApiExample("No Content", value=None)],
    )
    def delete(self, request, item_id: int):
        session_id = request.headers.get("X-Session-Id")
        if not session_id:
            return Response({"detail": "Missing X-Session-Id."}, status=status.HTTP_400_BAD_REQUEST)
        # 404 if not in this guest cart
        if not CartItem.objects.filter(id=item_id, cart__session_id=session_id).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        remove_item_guest(session_id=session_id, item_id=item_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GuestCartClearView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Clear guest cart",
        parameters=[
            OpenApiParameter(
                name="X-Session-Id",
                location=OpenApiParameter.HEADER,
                required=True,
                description="Guest session identifier",
                type=str,
            )
        ],
        responses={
            200: inline_serializer(name="CartStatusCleared", fields={"status": rf_serializers.CharField()}),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[OpenApiExample("Cleared", value={"status": "cleared"})],
    )
    def post(self, request):
        session_id = request.headers.get("X-Session-Id")
        if not session_id:
            return Response({"detail": "Missing X-Session-Id."}, status=status.HTTP_400_BAD_REQUEST)
        clear_cart_guest(session_id=session_id)
        return Response({"status": "cleared"}, status=status.HTTP_200_OK)


class MergeGuestCartView(APIView):
    """Authenticated endpoint to merge a guest cart into the user's cart."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "cart_write"

    @extend_schema(
        tags=["Cart Endpoints"],
        summary="Merge guest cart into user cart",
        description="Provide X-Session-Id header; merges guest items and reservations.",
        parameters=[
            OpenApiParameter(
                name="X-Session-Id",
                location=OpenApiParameter.HEADER,
                required=True,
                description="Guest session identifier",
                type=str,
            )
        ],
        responses={
            200: inline_serializer(name="CartStatusMerged", fields={"status": rf_serializers.CharField()}),
            400: inline_serializer(name="CartMutationError", fields={"detail": rf_serializers.CharField()}),
        },
        examples=[OpenApiExample("Merged", value={"status": "merged"})],
    )
    def post(self, request):
        session_id = request.headers.get("X-Session-Id")
        if not session_id:
            return Response({"detail": "Missing X-Session-Id."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            merge_guest_cart_to_user(session_id=session_id, user=request.user)
            return Response({"status": "merged"}, status=status.HTTP_200_OK)
        except (MovementError, CartError):
            return Response({"detail": "Unable to merge cart."}, status=status.HTTP_400_BAD_REQUEST)

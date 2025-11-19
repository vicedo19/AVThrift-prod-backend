"""Customer API views for profile and addresses.

Endpoints are authenticated and scoped to the current user. Views stay thin
and delegate business rules to services/selectors.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import Address, Profile
from .selectors import get_profile, list_addresses
from .serializers import AddressSerializer, ProfileSerializer
from .services import ensure_address_belongs_to_profile_user


class ProfileView(generics.RetrieveUpdateAPIView):
    """Retrieve and update the authenticated user's profile.

    Supports updating opt-in flags and default shipping/billing addresses.
    Exposes a read-only `shipping_contact` based on the default shipping address.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProfileSerializer

    @extend_schema(
        tags=["Customer Endpoints"],
        summary="Get current user's profile",
        parameters=[
            OpenApiParameter(
                name="Authorization",
                location=OpenApiParameter.HEADER,
                required=True,
                type=OpenApiTypes.STR,
                description="Bearer <access_token>",
            )
        ],
        examples=[
            OpenApiExample(
                "Profile",
                value={
                    "id": 42,
                    "email_opt_in": False,
                    "sms_opt_in": False,
                    "shipping_address": 10,
                    "billing_address": 11,
                    "shipping_contact": "+2348032222222",
                },
            )
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        # Return or create the profile for the current user
        profile = get_profile(self.request.user.id)
        if profile is None:
            profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile

    @extend_schema(
        tags=["Customer Endpoints"],
        summary="Update profile defaults and opt-ins",
        description=(
            "Update `email_opt_in`, `sms_opt_in`, and default addresses via "
            "`shipping_address`/`billing_address` (PKs). Ownership is validated."
        ),
        parameters=[
            OpenApiParameter(
                name="Authorization",
                location=OpenApiParameter.HEADER,
                required=True,
                type=OpenApiTypes.STR,
                description="Bearer <access_token>",
            )
        ],
        examples=[
            OpenApiExample(
                "Update defaults",
                value={"shipping_address": 10, "billing_address": 11, "email_opt_in": True},
                request_only=True,
            )
        ],
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        tags=["Customer Endpoints"],
        summary="Replace profile defaults and opt-ins",
        description=(
            "Full update using `email_opt_in`, `sms_opt_in`, `shipping_address`, and "
            "`billing_address`. Provide all writable fields (PUT semantics)."
        ),
        parameters=[
            OpenApiParameter(
                name="Authorization",
                location=OpenApiParameter.HEADER,
                required=True,
                type=OpenApiTypes.STR,
                description="Bearer <access_token>",
            )
        ],
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    def perform_update(self, serializer: ProfileSerializer) -> None:
        # Validate address ownership before saving
        instance: Profile = serializer.instance
        shipping = serializer.validated_data.get("default_shipping_address", instance.default_shipping_address)
        billing = serializer.validated_data.get("default_billing_address", instance.default_billing_address)

        try:
            ensure_address_belongs_to_profile_user(instance, shipping)
            ensure_address_belongs_to_profile_user(instance, billing)
        except DjangoValidationError as exc:
            # Normalize Django's ValidationError to DRF's for a 400 response
            raise DRFValidationError(detail=list(exc))

        # Save remaining fields (opt-ins, etc.)
        serializer.save()


class AddressListCreateView(generics.ListCreateAPIView):
    """List and create addresses for the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddressSerializer
    filterset_fields = ["city", "state", "country_code"]
    search_fields = ["name", "addr1", "city", "postal_code"]
    ordering_fields = ["updated_at", "id", "city", "state"]
    throttle_scope = "addresses"

    @extend_schema(
        tags=["Customer Endpoints"],
        summary="List current user's addresses",
        parameters=[
            OpenApiParameter(
                name="Authorization",
                location=OpenApiParameter.HEADER,
                required=True,
                type=OpenApiTypes.STR,
                description="Bearer <access_token>",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description="Search by name, addr1, city, or postal_code",
            ),
            OpenApiParameter(
                name="ordering",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description="Order by updated_at,id,city,state (prefix with '-' for desc)",
            ),
            OpenApiParameter(
                name="city",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description="Filter by city",
            ),
            OpenApiParameter(
                name="state",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description="Filter by state",
            ),
            OpenApiParameter(
                name="country_code",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description="Filter by ISO country code",
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return list_addresses(self.request.user.id)

    @extend_schema(
        tags=["Customer Endpoints"],
        summary="Create a new address",
        parameters=[
            OpenApiParameter(
                name="Authorization",
                location=OpenApiParameter.HEADER,
                required=True,
                type=OpenApiTypes.STR,
                description="Bearer <access_token>",
            )
        ],
        responses={
            201: AddressSerializer,
            400: OpenApiExample(
                "Invalid address",
                value={"detail": ["Validation error details..."]},
                response_only=True,
            ),
            401: OpenApiExample(
                "Unauthorized",
                value={"detail": "Authentication credentials were not provided."},
                response_only=True,
            ),
        },
        examples=[
            OpenApiExample(
                "Create address",
                value={
                    "name": "John Doe",
                    "addr1": "123 Main St",
                    "city": "Lagos",
                    "state": "Lagos",
                    "postal_code": "123456",
                    "country_code": "NG",
                    "phone": "+2347012345678",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer: AddressSerializer) -> None:
        serializer.save(user=self.request.user)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an address owned by the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddressSerializer
    throttle_scope = "addresses_write"

    def get_queryset(self):
        # Scope to the current user's addresses
        return Address.objects.filter(user_id=self.request.user.id).order_by("-updated_at", "id")

    @extend_schema(tags=["Customer Endpoints"], summary="Get an address")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Customer Endpoints"],
        summary="Update an address",
        parameters=[
            OpenApiParameter(
                name="Authorization",
                location=OpenApiParameter.HEADER,
                required=True,
                type=OpenApiTypes.STR,
                description="Bearer <access_token>",
            )
        ],
        responses={
            200: AddressSerializer,
            400: OpenApiExample(
                "Invalid update",
                value={"detail": ["Validation error details..."]},
                response_only=True,
            ),
            401: OpenApiExample(
                "Unauthorized",
                value={"detail": "Authentication credentials were not provided."},
                response_only=True,
            ),
            404: OpenApiExample(
                "Not found",
                value={"detail": "Not found."},
                response_only=True,
            ),
        },
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        tags=["Customer Endpoints"],
        summary="Replace an address",
        parameters=[
            OpenApiParameter(
                name="Authorization",
                location=OpenApiParameter.HEADER,
                required=True,
                type=OpenApiTypes.STR,
                description="Bearer <access_token>",
            )
        ],
        responses={
            200: AddressSerializer,
            400: OpenApiExample(
                "Invalid update",
                value={"detail": ["Validation error details..."]},
                response_only=True,
            ),
            401: OpenApiExample(
                "Unauthorized",
                value={"detail": "Authentication credentials were not provided."},
                response_only=True,
            ),
            404: OpenApiExample(
                "Not found",
                value={"detail": "Not found."},
                response_only=True,
            ),
        },
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        tags=["Customer Endpoints"],
        summary="Delete an address",
        parameters=[
            OpenApiParameter(
                name="Authorization",
                location=OpenApiParameter.HEADER,
                required=True,
                type=OpenApiTypes.STR,
                description="Bearer <access_token>",
            )
        ],
        responses={
            204: OpenApiExample("Deleted", value=None, response_only=True),
            401: OpenApiExample(
                "Unauthorized",
                value={"detail": "Authentication credentials were not provided."},
                response_only=True,
            ),
            404: OpenApiExample(
                "Not found",
                value={"detail": "Not found."},
                response_only=True,
            ),
        },
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

    def perform_destroy(self, instance: Address) -> None:
        profile = get_profile(self.request.user.id)
        if profile:
            updates = []
            if profile.default_shipping_address_id == instance.id:
                profile.default_shipping_address = None
                updates.append("default_shipping_address")
            if profile.default_billing_address_id == instance.id:
                profile.default_billing_address = None
                updates.append("default_billing_address")
            if updates:
                profile.save(update_fields=updates)
        super().perform_destroy(instance)


# EOF

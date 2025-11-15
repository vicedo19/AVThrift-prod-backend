"""Users app API views.

Endpoints include:
- me: returns the current authenticated user's profile.
- register: creates a new user and sends email verification.
- password-reset: initiates password reset without revealing account existence.
- password-reset/confirm: validates token and updates password.
- email-verify: sends verification for existing accounts.
- email-verify/confirm: confirms verification token.
- email-reset: authenticated request to change email (sends token to new email).
- email-reset/confirm: confirms change and finalizes email update.
- logout: blacklists refresh tokens for JWT logout.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from .logging import log_auth_event
from .serializers import EmailOrPhoneTokenObtainPairSerializer, RegistrationSerializer, UserMeSerializer
from .services import send_email_change, send_email_verification, send_password_reset_email
from .tokens import email_change_token, email_verification_token


@extend_schema(
    operation_id="users_current_user",
    summary="Get current user profile",
    description=(
        "Returns the current authenticated user's profile.\n\n"
        "Auth: Requires JWT (Authorization: Bearer <token>) or session auth.\n\n"
        "Response fields: id, username, email, first_name, last_name.\n\n"
        "Errors: 401 if authentication credentials are missing or invalid."
    ),
    tags=["User Endpoints"],
    responses={
        200: OpenApiResponse(description="User profile", response=UserMeSerializer),
        401: OpenApiResponse(description="Unauthorized"),
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def current_user(request):
    """Return the authenticated user's basic profile fields."""
    log_auth_event("profile", request, user=request.user)
    serializer = UserMeSerializer(request.user)
    return Response(serializer.data)


# Throttle scope for profile endpoint
current_user.throttle_scope = "profile"


@extend_schema(tags=["User Endpoints"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def register(request):
    """Register a new user and send verification token via email."""
    serializer = RegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        # send verification email after registration
        uid, token = send_email_verification(user)
        log_auth_event("register", request, user=user, status="success")
        data = UserMeSerializer(user).data
        data.update({"email_verification": {"uid": uid, "token": token}})
        return Response(data, status=status.HTTP_201_CREATED)
    log_auth_event("register", request, status="invalid")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Throttle scope for registration
register.throttle_scope = "register"


@extend_schema(tags=["User Endpoints"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def password_reset_request(request):
    """Initiate password reset flow; response is generic to prevent enumeration."""
    email = request.data.get("email", "").strip().lower()
    User = get_user_model()
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Do not reveal whether the email exists
        log_auth_event("password_reset_request", request, status="not_found")
        return Response({"detail": "If the email exists, a reset will be sent."})

    uid, token = send_password_reset_email(user)
    log_auth_event("password_reset_request", request, user=user, status="sent", extra={"uid": uid})
    return Response({"detail": "If the email exists, a reset will be sent.", "uid": uid, "token": token})


# Throttle scope for password reset request
password_reset_request.throttle_scope = "password_reset"


@extend_schema(tags=["User Endpoints"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def password_reset_confirm(request):
    """Validate password reset token and set a new password."""
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    new_password = request.data.get("new_password")

    if not uidb64 or not token or not new_password:
        return Response({"detail": "uid, token and new_password are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        User = get_user_model()
        user = User.objects.get(pk=uid)
    except Exception:
        log_auth_event("password_reset_confirm", request, status="invalid")
        return Response({"detail": "Invalid link."}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        log_auth_event("password_reset_confirm", request, user=user, status="invalid_token")
        return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

    from django.contrib.auth.password_validation import validate_password

    try:
        validate_password(new_password, user=user)
    except Exception as e:
        log_auth_event("password_reset_confirm", request, user=user, status="invalid_password")
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    log_auth_event("password_reset_confirm", request, user=user, status="success")
    return Response({"detail": "Password has been reset."})


# Throttle scope for password reset confirm
password_reset_confirm.throttle_scope = "password_reset"


@extend_schema(tags=["User Endpoints"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def email_verification_request(request):
    """Send an email verification token to the user's email address."""
    # Allow authenticated users to request, or anonymous provide email
    email = request.data.get("email")
    User = get_user_model()
    user = None
    if request.user and request.user.is_authenticated:
        user = request.user
    elif email:
        try:
            user = User.objects.get(email=email.strip().lower())
        except User.DoesNotExist:
            pass

    if not user:
        log_auth_event("email_verification_request", request, status="not_found")
        return Response({"detail": "If the account exists, a verification will be sent."})

    uid, token = send_email_verification(user)
    log_auth_event("email_verification_request", request, user=user, status="sent", extra={"uid": uid})
    return Response({"detail": "If the account exists, a verification will be sent.", "uid": uid, "token": token})


# Throttle scope for email verification request
email_verification_request.throttle_scope = "email_verify"


@extend_schema(tags=["User Endpoints"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def email_verification_confirm(request):
    """Confirm email verification using the provided uid and token."""
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    if not uidb64 or not token:
        return Response({"detail": "uid and token are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        User = get_user_model()
        user = User.objects.get(pk=uid)
    except Exception:
        log_auth_event("email_verification_confirm", request, status="invalid")
        return Response({"detail": "Invalid link."}, status=status.HTTP_400_BAD_REQUEST)

    if not email_verification_token.check_token(user, token):
        log_auth_event("email_verification_confirm", request, user=user, status="invalid_token")
        return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

    user.email_verified = True
    user.save(update_fields=["email_verified"])
    log_auth_event("email_verification_confirm", request, user=user, status="success")
    return Response({"detail": "Email verified."})


# Throttle scope for email verification confirm
email_verification_confirm.throttle_scope = "email_verify"


@extend_schema(tags=["User Endpoints"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def email_reset_request(request):
    """Request an email change; sends a token to the new address.

    Requires authentication and validates uniqueness and difference from
    the current email before sending a confirmation token.
    """
    new_email = (request.data.get("new_email") or "").strip().lower()
    if not new_email:
        return Response({"detail": "new_email is required."}, status=status.HTTP_400_BAD_REQUEST)
    User = get_user_model()
    # Must be different and unique
    if new_email == request.user.email:
        log_auth_event("email_reset_request", request, user=request.user, status="same_email")
        return Response(
            {"detail": "New email must be different from current email."}, status=status.HTTP_400_BAD_REQUEST
        )
    if User.objects.filter(email=new_email).exists():
        log_auth_event("email_reset_request", request, user=request.user, status="duplicate_email")
        return Response({"detail": "Email is already in use."}, status=status.HTTP_400_BAD_REQUEST)
    # Prevent two accounts from reserving the same pending email concurrently
    if User.objects.filter(pending_email=new_email).exclude(pk=request.user.pk).exists():
        log_auth_event("email_reset_request", request, user=request.user, status="duplicate_pending_email")
        return Response({"detail": "Email is already reserved for change."}, status=status.HTTP_400_BAD_REQUEST)

    request.user.pending_email = new_email
    request.user.save(update_fields=["pending_email"])
    uid, token = send_email_change(request.user)
    log_auth_event("email_reset_request", request, user=request.user, status="sent", extra={"uid": uid})
    return Response({"detail": "If the email is valid, a confirmation has been sent.", "uid": uid, "token": token})


# Throttle scope for email reset request
email_reset_request.throttle_scope = "email_reset"


@extend_schema(tags=["User Endpoints"])
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def email_reset_confirm(request):
    """Finalize email change using the email-bound token.

    Applies the `pending_email` as the primary email, clears pending state,
    and marks the new email as verified if the token is valid.
    """
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    if not uidb64 or not token:
        return Response({"detail": "uid and token are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        User = get_user_model()
        user = User.objects.get(pk=uid)
    except Exception:
        log_auth_event("email_reset_confirm", request, status="invalid")
        return Response({"detail": "Invalid link."}, status=status.HTTP_400_BAD_REQUEST)

    if not email_change_token.check_token(user, token):
        log_auth_event("email_reset_confirm", request, user=user, status="invalid_token")
        return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

    # Finalize change
    if not user.pending_email:
        log_auth_event("email_reset_confirm", request, user=user, status="no_pending")
        return Response({"detail": "No pending email change."}, status=status.HTTP_400_BAD_REQUEST)
    user.email = user.pending_email
    user.pending_email = None
    user.email_verified = True
    user.save(update_fields=["email", "pending_email", "email_verified"])
    log_auth_event("email_reset_confirm", request, user=user, status="success")
    return Response({"detail": "Email updated."})


# Throttle scope for email reset confirm
email_reset_confirm.throttle_scope = "email_reset"


class SignOutView(APIView):
    """Class-based view wrapper for sign-out to align auth view styles."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signout"
    permission_classes = [AllowAny]

    @extend_schema(tags=["User Endpoints"])
    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except TokenError:
            log_auth_event("signout", request, status="invalid_token")
            return Response({"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)
        log_auth_event("signout", request, status="success")
        return Response({"detail": "Signed out."}, status=status.HTTP_205_RESET_CONTENT)


class SignInView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "signin"
    serializer_class = EmailOrPhoneTokenObtainPairSerializer

    @extend_schema(tags=["User Endpoints"])
    def post(self, request, *args, **kwargs):
        resp = super().post(request, *args, **kwargs)
        status_label = "success" if resp.status_code == 200 else "failed"
        log_auth_event("signin", request, status=status_label)
        return resp


class RefreshView(TokenRefreshView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"

    @extend_schema(tags=["User Endpoints"])
    def post(self, request, *args, **kwargs):
        resp = super().post(request, *args, **kwargs)
        status_label = "success" if resp.status_code == 200 else "failed"
        log_auth_event("token_refresh", request, status=status_label)
        return resp


class VerifyView(TokenVerifyView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_verify"

    @extend_schema(tags=["User Endpoints"])
    def post(self, request, *args, **kwargs):
        resp = super().post(request, *args, **kwargs)
        status_label = "success" if resp.status_code == 200 else "failed"
        log_auth_event("token_verify", request, status=status_label)
        return resp

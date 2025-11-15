"""Serializers for user profile, registration, and validation flows.

- UserMeSerializer: read-only profile data for the authenticated user.
- RegistrationSerializer: action serializer to create users with
  strong password validation and unique email/username enforcement.
- EmailOrPhoneTokenObtainPairSerializer: obtain JWTs using email or phone.
"""

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class UserMeSerializer(serializers.ModelSerializer):
    """Serializer returning basic profile fields for the current user."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]


class RegistrationSerializer(serializers.Serializer):
    """Action serializer to register a new user.

    Validates uniqueness of `username` and `email` and enforces Django
    password validators. Uses `set_password` to hash provided password.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value: str) -> str:
        """Ensure the username is not already taken (case-insensitive)."""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username is already taken.")
        return value

    def validate_email(self, value: str) -> str:
        """Normalize and ensure the email is unique (case-insensitive)."""
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email is already registered.")
        return value

    def validate_password(self, value: str) -> str:
        """Run Django’s password validators against the provided password."""
        from django.contrib.auth.password_validation import validate_password

        user = User(username=self.initial_data.get("username", ""), email=self.initial_data.get("email", ""))
        validate_password(value, user=user)
        return value

    def create(self, validated_data):
        """Create a new user using secure password hashing."""
        user = User(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        user.set_password(validated_data["password"])
        user.save()
        return user


class SignOutSerializer(serializers.Serializer):
    """Request body for signing out (blacklisting refresh token).

    Accepts a single field `refresh` containing the JWT refresh token
    to invalidate via the blacklist mechanism.
    """

    refresh = serializers.CharField()


class EmailOrPhoneTokenObtainPairSerializer(serializers.Serializer):
    """Obtain JWTs by authenticating with either email or phone.

    Accepts a single `identifier` field which may be an email address
    (case-insensitive) or an E.164 phone number, and a `password`.
    Returns `access` and `refresh` tokens on success.
    """

    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = (attrs.get("identifier") or "").strip()
        password = attrs.get("password") or ""

        if not identifier or not password:
            raise serializers.ValidationError({"detail": "identifier and password are required."})

        # Determine lookup by email vs phone
        user = None
        if "@" in identifier:
            # Treat as email (normalize lowercase)
            email = identifier.lower()
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass
        else:
            # Treat as phone (stored as E.164, stripped on save)
            try:
                user = User.objects.get(phone=identifier)
            except User.DoesNotExist:
                pass

        if not user or not user.check_password(password) or not user.is_active:
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}

"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .health import health

admin.site.site_header = "AVThrift Admin"
admin.site.index_title = "Admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    # API schema and Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    # Healthcheck
    path("health/", health, name="health"),
    # Versioned v1 routes only
    path("api/v1/", include("users.urls")),
    path("api/v1/catalog/", include("catalog.urls")),
    path("api/v1/admin/catalog/", include("catalog.admin_urls")),
    path("api/v1/inventory/", include("inventory.urls")),
    path("api/v1/customer/", include("customer.urls")),
    path("api/v1/cart/", include("cart.urls")),
    path("api/v1/orders/", include("orders.urls")),
]

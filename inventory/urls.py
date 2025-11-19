from django.urls import path

from .views import InventoryHealthView, InventoryRoadmapView, MovementListView, ReservationListView, StockItemListView

urlpatterns = [
    path("health/", InventoryHealthView.as_view(), name="inventory-health"),
    path("", InventoryRoadmapView.as_view(), name="inventory-roadmap"),
    # Read-only endpoints
    path("stock-items/", StockItemListView.as_view(), name="stock-item-list"),
    path("movements/", MovementListView.as_view(), name="movement-list"),
    path("reservations/", ReservationListView.as_view(), name="reservation-list"),
]

# EOF

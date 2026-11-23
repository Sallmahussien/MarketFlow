from django.urls import path

from .views import FulfillmentDetailView, FulfillmentListView

app_name = "fulfillments"
urlpatterns = [
    path("", FulfillmentListView.as_view(), name="list"),
    path("<int:pk>/", FulfillmentDetailView.as_view(), name="detail"),
]

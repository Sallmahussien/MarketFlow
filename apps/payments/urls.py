from django.urls import path

from .views import AdminPaymentListView

app_name = "payments"
urlpatterns = [
    path("", AdminPaymentListView.as_view(), name="admin-list"),
]

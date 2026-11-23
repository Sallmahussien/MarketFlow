from django.urls import path

from apps.payments.mock_views import mock_session

from .views import CallbackView, CheckoutView

app_name = "checkout"
urlpatterns = [
    path("", CheckoutView.as_view(), name="start"),
    path("callback/", CallbackView.as_view(), name="callback"),
    path("mock/<uuid:token>/", mock_session, name="mock-session"),
]

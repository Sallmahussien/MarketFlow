from apps.shops.models import Shop
from apps.shops.permissions import IsSeller


class HasApprovedShop(IsSeller):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        view.approved_shop = Shop.objects.filter(user=request.user, status=Shop.Status.APPROVED).first()
        return view.approved_shop is not None

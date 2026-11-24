from django.conf import settings
from django.http import FileResponse
from django.views.decorators.http import require_safe


@require_safe
def openapi_schema(request):
    schema = settings.BASE_DIR / "design" / "openapi.json"
    return FileResponse(schema.open("rb"), content_type="application/json")

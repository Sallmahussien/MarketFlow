from django.utils.cache import patch_vary_headers


class LocalizedResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        patch_vary_headers(response, ("Accept-Language",))
        return response

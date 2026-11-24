import json
import re

from django.test import SimpleTestCase
from django.urls import URLPattern, get_resolver, reverse

from apps.payments.mock_views import mock_session


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def api_operations(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if not isinstance(pattern, URLPattern):
            if route != "admin/":
                yield from api_operations(pattern.url_patterns, route)
            continue
        if not route.startswith("api/v1/"):
            continue

        callback = pattern.callback
        if callback is mock_session:
            methods = {"get", "post"}
        elif hasattr(callback, "actions"):
            methods = set(callback.actions)
        else:
            view = callback.view_class
            methods = {method for method in view.http_method_names if hasattr(view, method)}

        path = "/" + re.sub(r"<[^>]+>", "{}", route)
        for method in methods & HTTP_METHODS:
            yield path, method


class APIDocumentationTests(SimpleTestCase):
    def test_swagger_page_loads_the_served_contract(self):
        response = self.client.get(reverse("swagger-ui"))
        self.assertContains(response, f'data-schema-url="{reverse("openapi-schema")}"')
        self.assertContains(response, "SwaggerUIBundle")

    def test_openapi_matches_all_registered_marketplace_operations(self):
        response = self.client.get(reverse("openapi-schema"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        schema = json.loads(b"".join(response.streaming_content))
        documented = {
            (re.sub(r"{[^}]+}", "{}", path), method)
            for path, operations in schema["paths"].items()
            for method in operations.keys() & HTTP_METHODS
        }
        self.assertEqual(documented, set(api_operations(get_resolver().url_patterns)))

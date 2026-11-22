from rest_framework import serializers

from .i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, get_localized_value, resolve_language


class LocalizedTextField(serializers.Field):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("Provide an object with language keys.")
        if data.keys() - SUPPORTED_LANGUAGES or any(not isinstance(value, str) for value in data.values()):
            raise serializers.ValidationError("Use only en and ar keys with string values.")
        if not data.get(DEFAULT_LANGUAGE, "").strip():
            raise serializers.ValidationError("A nonempty English value is required.")
        return {language: value.strip() for language, value in data.items()}

    def to_representation(self, value):
        request = self.context.get("request")
        language = resolve_language(request.headers.get("Accept-Language") if request else None)
        return get_localized_value(value, language)

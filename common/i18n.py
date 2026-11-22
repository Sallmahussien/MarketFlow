from collections.abc import Mapping

SUPPORTED_LANGUAGES = {"en", "ar"}
DEFAULT_LANGUAGE = "en"


def resolve_language(accept_language: str | None) -> str:
    if not accept_language:
        return DEFAULT_LANGUAGE

    preferences = []
    for position, part in enumerate(accept_language.split(",")):
        pieces = [piece.strip() for piece in part.split(";")]
        tag = pieces[0].lower().replace("_", "-")
        language = tag.split("-", 1)[0]
        if language not in SUPPORTED_LANGUAGES:
            continue

        quality = 1.0
        for param in pieces[1:]:
            if param.lower().startswith("q="):
                try:
                    quality = float(param[2:])
                except ValueError:
                    quality = 0.0
                break
        if not 0 < quality <= 1:
            continue
        preferences.append((-quality, position, language))

    if not preferences:
        return DEFAULT_LANGUAGE
    return min(preferences)[2]


def get_localized_value(value: Mapping | None, language: str = "en") -> str:
    if not isinstance(value, Mapping):
        return ""
    language = language.lower().split("-", 1)[0]
    selected = value.get(language)
    if isinstance(selected, str) and selected.strip():
        return selected
    fallback = value.get(DEFAULT_LANGUAGE)
    return fallback if isinstance(fallback, str) else ""

from app.utils.api_errors import strip_debug_error_fields


def test_strip_debug_error_fields_removes_internal_debug_fields_when_disabled():
    payload = {
        "success": False,
        "error": "boom",
        "details": "sensitive details",
        "traceback": "Traceback...",
    }

    sanitized = strip_debug_error_fields(payload, include_debug=False)

    assert sanitized == {
        "success": False,
        "error": "boom",
    }


def test_strip_debug_error_fields_keeps_debug_fields_when_enabled():
    payload = {
        "success": False,
        "error": "boom",
        "details": "sensitive details",
        "traceback": "Traceback...",
    }

    sanitized = strip_debug_error_fields(payload, include_debug=True)

    assert sanitized == {
        "success": False,
        "error": "boom",
        "details": "sensitive details",
    }

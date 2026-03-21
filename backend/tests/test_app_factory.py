from app import create_app


class TestConfig:
    DEBUG = True
    TESTING = True
    SECRET_KEY = "test"


def test_after_request_strips_traceback_from_json_response():
    app = create_app(TestConfig)

    @app.route("/_test/traceback")
    def traceback_response():
        return {
            "success": False,
            "error": "boom",
            "traceback": "internal stack",
        }, 500

    client = app.test_client()
    response = client.get("/_test/traceback")

    assert response.status_code == 500
    payload = response.get_json()

    assert payload["success"] is False
    assert payload["error"] == "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    assert "traceback" not in payload
    assert payload["request_id"]

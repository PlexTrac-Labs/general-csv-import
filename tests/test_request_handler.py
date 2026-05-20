from types import SimpleNamespace

import utils.request_handler as request_handler


class _Response:
    status_code = 200
    reason = "OK"

    def json(self):
        return {"status": "success"}


def test_post_with_files_uses_form_data_instead_of_json(monkeypatch):
    calls = []

    def fake_request(**kwargs):
        calls.append(kwargs)
        return _Response()

    monkeypatch.setattr(request_handler.requests, "request", fake_request)

    request_handler.post(
        base_url="https://example.test",
        headers={},
        endpoint="/upload",
        name="upload",
        data={"meta": "value"},
        files={"file": SimpleNamespace()},
    )

    assert calls[0]["data"] == {"meta": "value"}
    assert "json" not in calls[0] or calls[0]["json"] is None

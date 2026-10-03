import json

import pytest
from requests.structures import CaseInsensitiveDict

from plateapi import PlateAPI


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None, text=None):
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        self._body = body
        self.text = text if text is not None else (json.dumps(body) if body is not None else "")

    def json(self):
        if self._body is None:
            raise ValueError("no JSON")
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.queue = list(responses)
        self.calls = []
        self.headers = CaseInsensitiveDict()
        self.closed = False

    def request(self, method, url, params=None, headers=None, timeout=None):
        self.calls.append({
            "method": method, "url": url, "params": params,
            "headers": headers, "timeout": timeout,
        })
        if not self.queue:
            raise AssertionError("unexpected request: %s %s %r" % (method, url, params))
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed = True


def ok(body, headers=None):
    return FakeResponse(200, body, headers)


@pytest.fixture
def make_client():
    def _make(responses=(), **kwargs):
        client = PlateAPI("pk_live_test", **kwargs)
        fake = FakeSession(responses)
        fake.headers.update(client._transport.session.headers)
        client._transport.session = fake
        sleeps = []
        client._transport.sleep = sleeps.append
        return client, fake, sleeps
    return _make

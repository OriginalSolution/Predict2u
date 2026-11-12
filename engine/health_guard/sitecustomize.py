"""Loaded automatically (via PYTHONPATH) in every Python process of a health-check dry run.

Blocks every outgoing write request so no strategy can book a code, post to
Telegram, or send mail while the preflight exercises it: urllib / requests
POST|PUT|PATCH|DELETE raise, and smtplib refuses to connect. Plain GETs (fixtures,
odds, stats) go through. The companion `curl` shim in this folder does the same
for scripts that shell out to curl.
"""
import os

if os.environ.get("P2U_HEALTH_DRY_RUN") == "1":
    import urllib.error
    import urllib.request

    _urlopen = urllib.request.urlopen

    def _guarded_urlopen(url, data=None, *a, **k):
        method = getattr(url, "get_method", lambda: "POST" if data is not None else "GET")()
        if data is not None or method.upper() not in ("GET", "HEAD"):
            raise urllib.error.URLError("blocked by Predict2u health dry run (no booking/posting)")
        return _urlopen(url, data, *a, **k)

    urllib.request.urlopen = _guarded_urlopen

    try:
        import requests  # noqa: F401
        import requests.sessions as _rs

        _req = _rs.Session.request

        def _guarded_request(self, method, url, *a, **k):
            if str(method).upper() not in ("GET", "HEAD", "OPTIONS"):
                raise requests.exceptions.ConnectionError("blocked by Predict2u health dry run (no booking/posting)")
            return _req(self, method, url, *a, **k)

        _rs.Session.request = _guarded_request
    except Exception:
        pass

    try:
        import smtplib

        class _NoSMTP:
            def __init__(self, *a, **k):
                raise OSError("blocked by Predict2u health dry run (no email)")

        smtplib.SMTP = smtplib.SMTP_SSL = _NoSMTP
    except Exception:
        pass

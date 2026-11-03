"""Incremental Home Assistant GETs through the canvas worker's browser fetch."""

import json

from clock import elapsed
from config import parse_url, validate_secrets


# Keep network work in the worker's event loop so badge frames never wait on I/O.
FETCH = r"""
(function (url, headers, timeoutMs) {
    const controller = new AbortController();
    const job = {
        state: "pending", status: 0, headers: "{}", body: "", error: "",
        clock: "server",
        cancel() {
            if (this.state === "pending") this.state = "cancelled";
            clearTimeout(timer);
            controller.abort();
        }
    };
    function fail(message) {
        if (job.state !== "pending") return;
        job.error = message;
        job.state = "error";
        clearTimeout(timer);
        controller.abort();
    }
    const timer = setTimeout(
        () => fail("Home Assistant request timed out"), timeoutMs);
    (async () => {
        try {
            const response = await fetch(url, {
                method: "GET", headers: JSON.parse(headers),
                signal: controller.signal, redirect: "error",
                credentials: "omit", cache: "no-store"
            });
            if (job.state !== "pending") return;
            job.status = response.status;
            if (response.status !== 200) {
                job.state = "done";
                controller.abort();
                return;
            }
            const exposedHeaders = {};
            let headerSize = 0;
            response.headers.forEach((value, key) => {
                exposedHeaders[key.toLowerCase()] = value;
                headerSize += key.length + value.length + 4;
            });
            if (headerSize > 4096) return fail("HTTP headers exceed the memory limit");
            if (!exposedHeaders.date) {
                // Home Assistant's CORS setup cannot expose Date to browsers.
                exposedHeaders.date = new Date().toUTCString();
                job.clock = "browser";
            }
            job.headers = JSON.stringify(exposedHeaders);
            const decoder = new TextDecoder("utf-8", {fatal: true});
            const reader = response.body.getReader();
            let size = 0;
            while (job.state === "pending") {
                const chunk = await reader.read();
                if (job.state !== "pending") return;
                if (chunk.done) {
                    job.body += decoder.decode();
                    job.state = "done";
                    return;
                }
                size += chunk.value.byteLength;
                if (size > 16384) return fail("HTTP body exceeds the memory limit");
                job.body += decoder.decode(chunk.value, {stream: true});
            }
        } catch (_error) {
            fail("Canvas HTTP request failed; check the URL, CORS and browser certificate trust");
        } finally {
            clearTimeout(timer);
        }
    })();
    return job;
})
"""


class HttpClient:
    def __init__(self, credentials, timeout_ms):
        import js

        validate_secrets(credentials)
        if credentials.get("ca_file"):
            raise ValueError(
                "The canvas uses browser certificate trust, not ca_file")
        scheme, _host, _port, prefix, authority = parse_url(credentials["base_url"])
        self.base_url = scheme + "://" + authority + prefix
        self.headers = json.dumps({
            "Authorization": "Bearer " + credentials["token"],
            "Accept": "application/json",
        })
        self.timeout_ms = timeout_ms
        self.request = js.eval(FETCH)
        self.job = None
        self.browser_clock = False

    def start(self, path, now):
        if self.job is not None:
            raise RuntimeError("An HTTP request is already in progress")
        self.started = now
        self.job = self.request(self.base_url + path, self.headers, self.timeout_ms)

    def step(self, now):
        if self.job is None:
            return None
        if elapsed(now, self.started) >= self.timeout_ms:
            self.close()
            raise OSError("Home Assistant request timed out")
        state = str(self.job.state)
        if state == "pending":
            return None
        try:
            if state == "error":
                raise OSError(str(self.job.error))
            if state != "done":
                raise OSError("Home Assistant request was cancelled")
            code = int(self.job.status)
            if code != 200:
                hint = {401: "check token", 403: "sensor access denied",
                        404: "check entity ID", 429: "rate limited",
                        503: "Home Assistant unavailable"}.get(code, "request failed")
                raise ValueError("HTTP %d: %s" % (code, hint))
            if str(self.job.clock) == "browser" and not self.browser_clock:
                self.browser_clock = True
                print("Solar Buddy: CORS hides HTTP Date; "
                      "checking freshness with the browser clock")
            return json.loads(str(self.job.body)), json.loads(str(self.job.headers))
        finally:
            self.close()

    def close(self):
        job, self.job = self.job, None
        if job is not None:
            job.cancel()

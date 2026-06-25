from __future__ import annotations

import base64
import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import time as _time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def load_credentials(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def sign_apijwt(credentials: dict[str, Any], extra_claims: dict[str, Any] | None = None, lifetime_seconds: int = 300) -> str:
    now = int(time.time())
    header = {
        "alg": "RS256",
        "typ": "JWT",
        "kid": credentials.get("key_id", ""),
    }
    payload = {
        "iss": credentials.get("channel_identifier", ""),
        "sub": credentials.get("project_code", ""),
        "iat": now,
        "exp": now + lifetime_seconds,
        "type": credentials.get("type", "apijwt"),
    }
    if extra_claims:
        payload.update(extra_claims)
    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    ).encode("ascii")
    private_key = serialization.load_pem_private_key(credentials["private_key"].encode("utf-8"), password=None)
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return signing_input.decode("ascii") + "." + _b64url(signature)


def sign_noon_login_jwt(credentials: dict[str, Any]) -> str:
    header = {
        "alg": "RS256",
        "typ": "JWT",
    }
    payload = {
        "sub": credentials["key_id"],
        "iat": int(time.time()),
        "jti": str(uuid.uuid4()),
    }
    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    ).encode("ascii")
    private_key = serialization.load_pem_private_key(credentials["private_key"].encode("utf-8"), password=None)
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return signing_input.decode("ascii") + "." + _b64url(signature)


class NoonSession:
    def __init__(self, base_url: str, user_agent: str = "NoonAutoListingTool/0.1"):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def login(self, credentials: dict[str, Any]) -> dict[str, Any]:
        return self.post(
            "/identity/public/v1/api/login",
            {
                "token": sign_noon_login_jwt(credentials),
                "default_project_code": credentials["project_code"],
            },
            public=True,
        )

    def get(self, path: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        request_headers = {"User-Agent": self.user_agent}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            self.base_url + path,
            headers=request_headers,
            method="GET",
        )
        return self._open_json(request)

    def post(self, path: str, body: dict[str, Any], public: bool = False, headers: dict[str, str] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        request_headers = {"User-Agent": self.user_agent, "Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=request_headers,
            method="POST",
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request) -> dict[str, Any]:
        last_exc = None
        for attempt in range(5):
            try:
                with self.opener.open(request, timeout=30) as response:
                    text = response.read().decode("utf-8", errors="replace")
                    if not text:
                        return {"_status": response.status}
                    data = json.loads(text)
                    if isinstance(data, dict):
                        data.setdefault("_status", response.status)
                    return data
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 429 and attempt < 4:
                    retry_after = exc.headers.get("Retry-After")
                    try:
                        sleep_seconds = int(retry_after) if retry_after else 20 * (attempt + 1)
                    except ValueError:
                        sleep_seconds = 20 * (attempt + 1)
                    _time.sleep(sleep_seconds)
                    continue
                raise
            except urllib.error.URLError as exc:
                last_exc = exc
                if attempt < 4:
                    _time.sleep(10 * (attempt + 1))
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("Request failed without response")


class NoonApiProbe:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg

    def probe(self, credentials_path: Path | None = None) -> dict[str, Any]:
        noon_cfg = self.cfg.get("noon", {})
        cred_path = credentials_path or Path(noon_cfg.get("credentials_path", "../api.json"))
        if not cred_path.is_absolute():
            cred_path = (Path(__file__).resolve().parents[2] / cred_path).resolve()
        result: dict[str, Any] = {
            "credentials_path": str(cred_path),
            "credentials_loaded": False,
            "jwt_signing_ok": False,
            "api_base_url_configured": bool(noon_cfg.get("api_base_url")),
            "configured_probe_count": len(noon_cfg.get("probe_endpoints", [])),
            "permissions": [],
            "warnings": [],
        }
        try:
            credentials = load_credentials(cred_path)
            result["credentials_loaded"] = True
            result["credential_fields"] = sorted(k for k in credentials.keys() if k != "private_key")
            token = sign_noon_login_jwt(credentials)
            result["jwt_signing_ok"] = token.count(".") == 2
        except Exception as exc:
            result["warnings"].append(f"Credential/JWT probe failed: {type(exc).__name__}: {exc}")
            return result

        base_url = str(noon_cfg.get("api_base_url") or "https://noon-api-gateway.noon.partners").rstrip("/")
        endpoints = list(noon_cfg.get("probe_endpoints") or ["/identity/v1/whoami", "/content/v1/categories/list"])
        if not base_url:
            result["warnings"].append("No Noon API base URL configured; permission scope cannot be confirmed.")
            return result

        session = NoonSession(base_url)
        try:
            login_result = session.login(credentials)
            result["login_ok"] = True
            result["login_preview"] = _preview(login_result)
        except urllib.error.HTTPError as exc:
            result["login_ok"] = False
            result["warnings"].append(f"Login failed with HTTP {exc.code}: {exc.read(500).decode('utf-8', errors='replace')}")
            return result
        except Exception as exc:
            result["login_ok"] = False
            result["warnings"].append(f"Login failed: {type(exc).__name__}: {exc}")
            return result

        for endpoint in endpoints:
            result["permissions"].append(self._probe_endpoint(session, endpoint))
        return result

    def _probe_endpoint(self, session: NoonSession, endpoint: str) -> dict[str, Any]:
        method = "GET"
        body: dict[str, Any] = {}
        if endpoint.startswith("/content/"):
            method = "POST"
        try:
            data = session.post(endpoint, body) if method == "POST" else session.get(endpoint)
            return {"endpoint": endpoint, "method": method, "status": data.get("_status"), "ok": True, "body_preview": _preview(data)}
        except urllib.error.HTTPError as exc:
            body = exc.read(1000).decode("utf-8", errors="replace")
            return {"endpoint": endpoint, "method": method, "status": exc.code, "ok": False, "body_preview": body[:500]}
        except Exception as exc:
            return {"endpoint": endpoint, "method": method, "status": None, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


class NoonContentClient:
    def __init__(self, cfg: dict[str, Any], credentials_path: Path | None = None):
        noon_cfg = cfg.get("noon", {})
        self.base_url = str(noon_cfg.get("api_base_url") or "https://noon-api-gateway.noon.partners").rstrip("/")
        cred_path = credentials_path or Path(noon_cfg.get("credentials_path", "../api.json"))
        if not cred_path.is_absolute():
            cred_path = (Path(__file__).resolve().parents[2] / cred_path).resolve()
        self.credentials = load_credentials(cred_path)
        self.session = NoonSession(self.base_url)
        self.session.login(self.credentials)

    def list_categories(self) -> list[str]:
        data = self.session.post("/content/v1/categories/list", {})
        return list(data.get("categories") or [])

    def list_category_attributes(self, category_code: str) -> dict[str, Any]:
        data = self.session.post("/content/v1/categories/attributes/list", {"category_code": category_code})
        data.pop("_status", None)
        return data

    def upsert_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.session.post(
            "/content/v1/product/upsert",
            payload,
            headers={"X-Project": self.credentials["project_code"]},
        )

    def get_content(self, sku_parent: str) -> dict[str, Any]:
        return self.session.post("/content/v1/product/content/get", {"sku_parent": sku_parent})


def _preview(data: Any, max_len: int = 800) -> str:
    text = json.dumps(data, ensure_ascii=False)
    return text[:max_len]

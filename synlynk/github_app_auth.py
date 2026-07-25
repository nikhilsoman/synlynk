"""GitHub App auth helpers used by the identity role provisioning flow."""

import base64
import json
import subprocess
import time


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _sign_jwt(private_key_path: str, app_id=None, lifetime_seconds: int = 540) -> str:
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iat": now - 60,
        "exp": now + lifetime_seconds,
    }
    if app_id is not None:
        payload["iss"] = str(app_id)

    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")),
            _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")),
        ]
    ).encode("ascii")

    try:
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", private_key_path, "-binary"],
            input=signing_input,
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("unable to sign GitHub App JWT") from exc

    signature = _b64url(result.stdout)
    return f"{signing_input.decode('ascii')}.{signature}"

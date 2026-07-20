#!/usr/bin/env python3
"""Idempotent FastClaw provisioning and verification for SciPoster."""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.cookiejar
import json
import mimetypes
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEPLOY_VERSION = "1.0.0"


class DeployError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[sciposter] {message}", flush=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def sha256_tree(path: Path) -> tuple[str, int]:
    """Hash a directory as sorted relative paths plus per-file SHA-256."""
    digest = hashlib.sha256()
    count = 0
    candidates = (
        p for p in path.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix.lower() not in {".pyc", ".pyo"}
    )
    for item in sorted(candidates, key=lambda p: p.relative_to(path).as_posix().lower()):
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(item).encode("ascii"))
        digest.update(b"\n")
        count += 1
    return digest.hexdigest().upper(), count


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise DeployError(f"required file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DeployError(f"invalid JSON in {path}: {exc}") from exc


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def require_string(obj: dict[str, Any], dotted: str) -> str:
    current: Any = obj
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise DeployError(f"configuration field is required: {dotted}")
        current = current[part]
    if not isinstance(current, str) or not current.strip():
        raise DeployError(f"configuration field must be a non-empty string: {dotted}")
    if "REPLACE_ME" in current:
        raise DeployError(f"replace the placeholder in configuration field: {dotted}")
    return current.strip()


def validate_configuration(config: dict[str, Any], agents_cfg: dict[str, Any]) -> None:
    if config.get("schemaVersion") != 1:
        raise DeployError("deploy config schemaVersion must be 1")
    for field in (
        "administrator.username",
        "administrator.email",
        "administrator.password",
        "provider.name",
        "provider.apiBase",
        "provider.apiKey",
        "provider.apiType",
        "provider.authType",
        "provider.model.id",
    ):
        require_string(config, field)
    fastclaw = config.get("fastclaw", {})
    if fastclaw.get("host") != "127.0.0.1":
        raise DeployError("fastclaw.host must remain 127.0.0.1 for this no-sandbox package")
    port = fastclaw.get("port")
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise DeployError("fastclaw.port must be a valid integer port")
    agents = agents_cfg.get("agents")
    if agents_cfg.get("schemaVersion") != 1 or not isinstance(agents, list) or not agents:
        raise DeployError("config/agents.json must contain a non-empty schemaVersion 1 agents list")
    keys = [a.get("key") for a in agents]
    names = [a.get("name") for a in agents]
    if len(set(keys)) != len(keys) or len(set(names)) != len(names):
        raise DeployError("agent keys and names must be unique")
    for agent in agents:
        for field in ("key", "name", "model", "prompt"):
            if not isinstance(agent.get(field), str) or not agent[field].strip():
                raise DeployError(f"agent {agent!r} has invalid {field}")
        if not isinstance(agent.get("skills"), list) or not agent["skills"]:
            raise DeployError(f"agent {agent['key']} must declare at least one skill")


def validate_manifest(root: Path) -> None:
    manifest_path = root / "manifest.json"
    manifest = load_json(manifest_path)
    if manifest.get("schemaVersion") != 1:
        raise DeployError("manifest schemaVersion must be 1")
    failures: list[str] = []
    for entry in manifest.get("files", []):
        rel = entry.get("path", "")
        expected = str(entry.get("sha256", "")).upper()
        path = root / Path(rel)
        if not path.is_file():
            failures.append(f"missing: {rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            failures.append(f"hash mismatch: {rel} (expected {expected}, got {actual})")
    for entry in manifest.get("trees", []):
        rel = entry.get("path", "")
        expected = str(entry.get("sha256", "")).upper()
        expected_count = int(entry.get("fileCount", -1))
        path = root / Path(rel)
        if not path.is_dir():
            failures.append(f"missing directory: {rel}")
            continue
        actual, count = sha256_tree(path)
        if actual != expected or count != expected_count:
            failures.append(
                f"tree mismatch: {rel} (expected {expected}/{expected_count} files, got {actual}/{count} files)"
            )
    if failures:
        raise DeployError("manifest validation failed:\n  " + "\n  ".join(failures))


def validate_package(root: Path, config_path: Path, agents_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = load_json(config_path)
    agents_cfg = load_json(agents_path)
    validate_configuration(config, agents_cfg)
    validate_manifest(root)
    for agent in agents_cfg["agents"]:
        prompt_path = root / agent["prompt"]
        if not prompt_path.is_file():
            raise DeployError(f"prompt is missing for {agent['key']}: {prompt_path}")
        for skill in agent["skills"]:
            zip_path = root / "skills" / f"{skill}.zip"
            if not zip_path.is_file():
                raise DeployError(f"skill archive is missing: {zip_path}")
    return config, agents_cfg


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 60, bearer: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.bearer = bearer
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        headers: dict[str, str] | None = None,
        raw: bytes | None = None,
    ) -> Any:
        url = self.base_url + path
        request_headers = {"Accept": "application/json"}
        if self.bearer:
            request_headers["Authorization"] = f"Bearer {self.bearer}"
        if headers:
            request_headers.update(headers)
        data = raw
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                body = response.read()
                if not body:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "json" in content_type or body[:1] in (b"{", b"["):
                    return json.loads(body.decode("utf-8"))
                return body
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body)
            except json.JSONDecodeError:
                detail = body[:1000]
            raise DeployError(f"FastClaw API {method} {path} returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise DeployError(f"cannot reach FastClaw at {url}: {exc.reason}") from exc

    def upload_skill(self, path: str, archive: Path, skill_name: str) -> Any:
        boundary = "----sciposter-" + secrets.token_hex(16)
        filename = archive.name.replace('"', "")
        prefix = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="name"\r\n\r\n{skill_name}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8")
        suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
        return self.request(
            "POST",
            path,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            raw=prefix + archive.read_bytes() + suffix,
        )


def base_url(config: dict[str, Any]) -> str:
    fc = config["fastclaw"]
    return f"http://{fc['host']}:{fc['port']}"


def login(config: dict[str, Any], timeout: int = 60) -> ApiClient:
    client = ApiClient(base_url(config), timeout=timeout)
    response = client.request(
        "POST",
        "/api/login",
        {"login": config["administrator"]["username"], "password": config["administrator"]["password"]},
    )
    if not isinstance(response, dict) or not response.get("ok"):
        raise DeployError("administrator login failed")
    return client


def provider_payload(config: dict[str, Any]) -> dict[str, Any]:
    provider = config["provider"]
    model = provider["model"]
    return {
        "scope": "system",
        "scopeId": "",
        "name": provider["name"],
        "apiBase": provider["apiBase"],
        "apiKey": provider["apiKey"],
        "apiType": provider["apiType"],
        "authType": provider["authType"],
        "models": [model],
    }


def reconcile_provider(client: ApiClient, config: dict[str, Any]) -> str:
    payload = provider_payload(config)
    response = client.request("GET", "/api/providers?scope=system")
    providers = response.get("providers", []) if isinstance(response, dict) else []
    matches = [p for p in providers if p.get("name") == payload["name"]]
    if len(matches) > 1:
        raise DeployError(f"duplicate providers named {payload['name']!r}; resolve manually")
    if matches:
        provider_id = matches[0]["id"]
        client.request("PUT", f"/api/providers/{urllib.parse.quote(provider_id)}", payload)
        log(f"updated provider {payload['name']}")
    else:
        client.request("POST", "/api/providers", payload)
        response = client.request("GET", "/api/providers?scope=system")
        matches = [p for p in response.get("providers", []) if p.get("name") == payload["name"]]
        if len(matches) != 1:
            raise DeployError(f"provider {payload['name']!r} was not uniquely created")
        provider_id = matches[0]["id"]
        log(f"created provider {payload['name']}")
    test = client.request(
        "POST",
        f"/api/providers/{urllib.parse.quote(provider_id)}/test",
        {"model": config["provider"]["model"]["id"]},
    )
    if not isinstance(test, dict) or not test.get("ok"):
        raise DeployError(f"provider connection test failed: {test}")
    log("provider connection test passed")
    return provider_id


def resolved_model(agent: dict[str, Any], config: dict[str, Any]) -> str:
    if agent["model"] == "provider/model":
        return f"{config['provider']['name']}/{config['provider']['model']['id']}"
    return agent["model"]


def reconcile_agents(client: ApiClient, root: Path, config: dict[str, Any], agents_cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    response = client.request("GET", "/api/agents")
    existing = response.get("agents", []) if isinstance(response, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for desired in agents_cfg["agents"]:
        matches = [a for a in existing if a.get("name") == desired["name"]]
        if len(matches) > 1:
            raise DeployError(f"duplicate agents named {desired['name']!r}; resolve manually")
        payload = {
            "name": desired["name"],
            "description": desired.get("description", ""),
            "model": resolved_model(desired, config),
        }
        if matches:
            agent_id = matches[0]["id"]
            client.request("PUT", f"/api/agents/{urllib.parse.quote(agent_id)}", payload)
            log(f"updated agent {desired['name']} ({agent_id})")
        else:
            created = client.request("POST", "/api/agents", payload)
            agent_id = created.get("agent", {}).get("id") if isinstance(created, dict) else None
            if not agent_id:
                raise DeployError(f"agent {desired['name']!r} creation returned no id")
            log(f"created agent {desired['name']} ({agent_id})")
        prompt = (root / desired["prompt"]).read_text(encoding="utf-8-sig")
        client.request(
            "PUT",
            f"/api/agents/{urllib.parse.quote(agent_id)}/system-files/AGENTS.md",
            {"content": prompt},
        )
        result[desired["key"]] = {
            "id": agent_id,
            "name": desired["name"],
            "promptSha256": sha256_text(prompt),
        }
    return result


def normalize_skill_list(response: Any) -> set[str]:
    entries = response if isinstance(response, list) else response.get("skills", []) if isinstance(response, dict) else []
    return {e.get("name") for e in entries if isinstance(e, dict) and isinstance(e.get("name"), str)}


def reconcile_skills(
    client: ApiClient,
    root: Path,
    agents_cfg: dict[str, Any],
    agent_state: dict[str, dict[str, Any]],
    prior_state: dict[str, Any],
) -> None:
    managed = {s for a in agents_cfg["agents"] for s in a["skills"]}
    prior_agents = prior_state.get("agents", {}) if isinstance(prior_state, dict) else {}
    for desired in agents_cfg["agents"]:
        state_entry = agent_state[desired["key"]]
        agent_id = state_entry["id"]
        installed = normalize_skill_list(client.request("GET", f"/api/agents/{urllib.parse.quote(agent_id)}/skills"))
        target = set(desired["skills"])
        prior_skills = prior_agents.get(desired["key"], {}).get("skills", {})
        current_hashes = {name: sha256_file(root / "skills" / f"{name}.zip") for name in target}

        for name in sorted((installed & managed) - target):
            client.request("DELETE", f"/api/agents/{urllib.parse.quote(agent_id)}/skills/{urllib.parse.quote(name)}")
            installed.discard(name)
            log(f"removed obsolete managed skill {name} from {desired['name']}")

        for name in sorted(target):
            unchanged = name in installed and prior_skills.get(name) == current_hashes[name]
            if unchanged:
                continue
            if name in installed:
                client.request("DELETE", f"/api/agents/{urllib.parse.quote(agent_id)}/skills/{urllib.parse.quote(name)}")
            archive = root / "skills" / f"{name}.zip"
            client.upload_skill(
                f"/api/skills/upload?agent={urllib.parse.quote(agent_id)}",
                archive,
                name,
            )
            log(f"installed skill {name} on {desired['name']}")
        state_entry["skills"] = current_hashes


def validate_client_key(config: dict[str, Any], expected_ids: set[str]) -> bool:
    token = config.get("fastclawClientApiKey", "")
    if not isinstance(token, str) or not token.strip():
        return False
    try:
        response = ApiClient(base_url(config), bearer=token.strip()).request("GET", "/v1/agents")
    except DeployError:
        return False
    ids = {a.get("id") for a in response.get("agents", [])} if isinstance(response, dict) else set()
    return ids == expected_ids


def reconcile_api_key(
    client: ApiClient,
    config: dict[str, Any],
    config_path: Path,
    agent_ids: list[str],
) -> str:
    name = config["fastclaw"].get("apiKeyName", "sciposter-middleware")
    response = client.request("GET", "/api/apikeys")
    keys = response.get("apikeys", []) if isinstance(response, dict) else []
    matches = [key for key in keys if key.get("name") == name]
    if len(matches) > 1:
        raise DeployError(f"duplicate API keys named {name!r}; resolve manually")
    expected = set(agent_ids)
    token_is_valid = validate_client_key(config, expected)
    token = config.get("fastclawClientApiKey", "") if token_is_valid else ""
    if matches:
        key_id = matches[0]["id"]
        client.request("PUT", f"/api/apikeys/{urllib.parse.quote(key_id)}/agents", {"agentIds": agent_ids})
        if not token_is_valid:
            rotated = client.request("POST", f"/api/apikeys/{urllib.parse.quote(key_id)}/rotate", {})
            token = rotated.get("token", "") if isinstance(rotated, dict) else ""
            log(f"rotated API key {name}")
        else:
            log(f"validated API key {name}")
    else:
        created = client.request("POST", "/api/apikeys", {"name": name, "type": "agent", "agentIds": agent_ids})
        key_id = created.get("apikey", {}).get("id") if isinstance(created, dict) else None
        token = created.get("token", "") if isinstance(created, dict) else ""
        if not key_id:
            raise DeployError("API key creation returned no id")
        log(f"created API key {name}")
    if not token:
        raise DeployError("FastClaw returned no plaintext API key during create/rotate")
    if config.get("fastclawClientApiKey") != token:
        config["fastclawClientApiKey"] = token
        atomic_json(config_path, config)
    if not validate_client_key(config, expected):
        raise DeployError("scoped API key validation failed after create/rotate")
    return key_id


def load_prior_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return load_json(path)
    except DeployError:
        return {}


def reconcile(root: Path, config_path: Path, agents_path: Path, state_path: Path) -> None:
    config, agents_cfg = validate_package(root, config_path, agents_path)
    timeout = int(config.get("verification", {}).get("requestTimeoutSeconds", 180))
    client = login(config, timeout=timeout)
    provider_id = reconcile_provider(client, config)
    prior_state = load_prior_state(state_path)
    agents = reconcile_agents(client, root, config, agents_cfg)
    reconcile_skills(client, root, agents_cfg, agents, prior_state)
    ordered_ids = [agents[a["key"]]["id"] for a in agents_cfg["agents"]]
    api_key_id = reconcile_api_key(client, config, config_path, ordered_ids)
    state = {
        "schemaVersion": 1,
        "deployVersion": DEPLOY_VERSION,
        "reconciledAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": {"id": provider_id, "name": config["provider"]["name"]},
        "apiKey": {"id": api_key_id, "name": config["fastclaw"].get("apiKeyName", "sciposter-middleware")},
        "managedSkills": sorted({s for a in agents_cfg["agents"] for s in a["skills"]}),
        "agents": agents,
    }
    atomic_json(state_path, state)
    log(f"wrote non-secret deployment state to {state_path}")


def get_prompt_content(client: ApiClient, agent_id: str) -> str:
    response = client.request("GET", f"/api/agents/{urllib.parse.quote(agent_id)}/system-files/AGENTS.md")
    if isinstance(response, dict):
        return str(response.get("content", ""))
    return ""


def call_agent(config: dict[str, Any], agent_id: str, prompt: str, attachment: Path | None = None) -> dict[str, Any]:
    token = config["fastclawClientApiKey"]
    body: dict[str, Any] = {
        "model": "",
        "agent_id": agent_id,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }
    if attachment is not None:
        mime = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(attachment.read_bytes()).decode("ascii")
        body["attachments"] = [{"url": f"data:{mime};base64,{encoded}", "name": attachment.name}]
    timeout = int(config.get("verification", {}).get("requestTimeoutSeconds", 180))
    response = ApiClient(base_url(config), timeout=timeout, bearer=token).request("POST", "/v1/chat/completions", body)
    if not isinstance(response, dict) or not response.get("choices"):
        raise DeployError(f"agent {agent_id} returned an invalid chat response: {response}")
    return response


def verify(root: Path, config_path: Path, agents_path: Path, state_path: Path, run_smoke: bool) -> None:
    config, agents_cfg = validate_package(root, config_path, agents_path)
    state = load_json(state_path)
    client = login(config)
    listed = client.request("GET", "/api/agents")
    all_agents = listed.get("agents", []) if isinstance(listed, dict) else []
    by_name: dict[str, list[dict[str, Any]]] = {}
    for agent in all_agents:
        by_name.setdefault(agent.get("name", ""), []).append(agent)
    managed = set(state.get("managedSkills", []))
    expected_ids: set[str] = set()
    for desired in agents_cfg["agents"]:
        matches = by_name.get(desired["name"], [])
        if len(matches) != 1:
            raise DeployError(f"expected exactly one agent named {desired['name']!r}, found {len(matches)}")
        agent_id = matches[0]["id"]
        expected_ids.add(agent_id)
        prompt = (root / desired["prompt"]).read_text(encoding="utf-8-sig")
        if get_prompt_content(client, agent_id) != prompt:
            raise DeployError(f"AGENTS.md mismatch for {desired['name']}")
        installed = normalize_skill_list(client.request("GET", f"/api/agents/{urllib.parse.quote(agent_id)}/skills"))
        actual_managed = installed & managed
        if actual_managed != set(desired["skills"]):
            raise DeployError(
                f"managed skill mismatch for {desired['name']}: expected {sorted(desired['skills'])}, got {sorted(actual_managed)}"
            )
        log(f"verified agent, prompt, and skills: {desired['name']}")
    if not validate_client_key(config, expected_ids):
        raise DeployError("middleware API key is missing, invalid, or not scoped to the managed agents")
    log("verified middleware API key scope")

    if run_smoke and config.get("verification", {}).get("modelSmoke", True):
        state_agents = state.get("agents", {})
        for desired in agents_cfg["agents"]:
            agent_id = state_agents[desired["key"]]["id"]
            if desired["key"] == "poster-agent":
                continue
            call_agent(config, agent_id, "Reply with exactly: SCIPOSTER_SMOKE_OK")
            log(f"text smoke passed: {desired['name']}")
        poster_input = str(config.get("verification", {}).get("posterSmokeInput", "")).strip()
        if poster_input:
            path = Path(poster_input)
            if not path.is_absolute():
                path = root / path
            if not path.is_file():
                raise DeployError(f"poster smoke input does not exist: {path}")
            call_agent(
                config,
                state_agents["poster-agent"]["id"],
                "Generate the complete academic poster now and verify all six required outputs.",
                path,
            )
            log("poster generation smoke request completed")
        else:
            log("poster smoke skipped because verification.posterSmokeInput is empty")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "reconcile", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--agents", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        if args.command == "validate":
            validate_package(root, args.config.resolve(), args.agents.resolve())
            log("configuration and package manifest are valid")
        elif args.command == "reconcile":
            reconcile(root, args.config.resolve(), args.agents.resolve(), args.state.resolve())
        else:
            verify(root, args.config.resolve(), args.agents.resolve(), args.state.resolve(), args.smoke)
        return 0
    except DeployError as exc:
        print(f"[sciposter] ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

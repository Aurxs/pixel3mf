#!/usr/bin/env python3
"""WorkBuddy orchestration for image generation and Pixel3MF conversion."""

from __future__ import annotations

import argparse
import ast
import base64
from datetime import datetime
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.request import urlopen

try:
    import requests
except ImportError:  # doctor must remain runnable before installation.
    requests = None  # type: ignore[assignment]

try:
    from PIL import Image, ImageOps
except ImportError:  # doctor must remain runnable before installation.
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]

try:
    from refine_pixel import detect_source_grid
    from run_pipeline import run_pipeline
except ImportError:  # doctor reports the missing runtime dependency.
    detect_source_grid = None  # type: ignore[assignment]
    run_pipeline = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_SKILL_DIR = PROJECT_ROOT / "skills" / "pixel-art-to-3mf-skill"
WORKBUDDY_SKILL_DIR = PROJECT_ROOT / ".codebuddy" / "skills" / "pixel-art-to-3mf"
GENERATION_PROMPT_PATH = PROJECT_ROOT / "workbuddy" / "generation-prompt.md"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / ".workbuddy.local.json"
STATE_FILENAME = "workbuddy_state.json"
STATE_VERSION = 1
MAX_GENERATION_ATTEMPTS = 3
TOKENHUB_KEYCHAIN_SERVICE = "pixel3mf.tokenhub"
COS_KEYCHAIN_SERVICE = "pixel3mf.cos"

DEFAULT_CONFIG: dict[str, Any] = {
    "tokenhub": {
        "model": "hy-image-v3.0",
        "submit_url": "https://tokenhub.tencentmaas.com/v1/api/image/submit",
        "query_url": "https://tokenhub.tencentmaas.com/v1/api/image/query",
        "size": "1024:1024",
        "timeout_seconds": 300,
        "poll_interval_seconds": 2,
    },
    "cos": {
        "region": "ap-shanghai",
        "bucket": "",
        "object_prefix": "workbuddy-reference",
        "signed_url_ttl_seconds": 900,
    },
    "lumina": {"api_url": "http://127.0.0.1:8000"},
    "generation": {"max_attempts": MAX_GENERATION_ATTEMPTS},
}


class TokenHubError(RuntimeError):
    """Base error for TokenHub operations."""


class TokenHubHTTPError(TokenHubError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.safe_message = message
        super().__init__(f"TokenHub HTTP {status_code}: {message}")


class TokenHubTerminalError(TokenHubError):
    """A submitted task reached a terminal non-success state."""


def _require_runtime_dependencies() -> None:
    missing = []
    if requests is None:
        missing.append("requests")
    if Image is None or ImageOps is None:
        missing.append("Pillow")
    if detect_source_grid is None or run_pipeline is None:
        missing.append("Pixel3MF runtime modules")
    if missing:
        raise RuntimeError(
            "missing runtime dependencies: " + ", ".join(missing)
            + "; run doctor with the project virtual environment"
        )


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _slug(value: str) -> str:
    slug = re.sub(r"[^\w-]+", "-", value.strip().lower(), flags=re.UNICODE).strip("-_")
    return slug or "run"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _find_config_secret(value: object, path: str = "config") -> str | None:
    sensitive = {
        "access_key",
        "api_key",
        "api_token",
        "authorization",
        "bearer",
        "credential",
        "password",
        "secret_id",
        "secret_key",
        "token",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(
                r"(?<=[a-z0-9])(?=[A-Z])", "_", str(key).strip()
            ).lower().replace("-", "_")
            if normalized in sensitive or normalized.endswith("_password"):
                return f"{path}.{key}"
            found = _find_config_secret(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_config_secret(child, f"{path}[{index}]")
            if found:
                return found
    return None


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path).expanduser().resolve() if path else DEFAULT_CONFIG_PATH
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if config_path.is_file():
        override = _read_json(config_path)
        secret_path = _find_config_secret(override)
        if secret_path:
            raise ValueError(
                f"local WorkBuddy config must not contain credentials: {secret_path}"
            )
        config = _deep_merge(config, override)
    if os.getenv("PIXEL3MF_COS_BUCKET"):
        config["cos"]["bucket"] = os.environ["PIXEL3MF_COS_BUCKET"]
    if os.getenv("PIXEL3MF_COS_REGION"):
        config["cos"]["region"] = os.environ["PIXEL3MF_COS_REGION"]
    attempts = int(config.get("generation", {}).get("max_attempts", 3))
    if attempts != MAX_GENERATION_ATTEMPTS:
        raise ValueError(
            f"generation.max_attempts must remain {MAX_GENERATION_ATTEMPTS}"
        )
    return config


def _keychain_secret(service: str, account: str) -> str | None:
    security = shutil.which("security")
    if security is None:
        return None
    result = subprocess.run(
        [security, "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _credential(service: str, account: str, environment_name: str) -> str | None:
    return _keychain_secret(service, account) or os.getenv(environment_name)


def _tokenhub_api_key() -> str | None:
    return _credential(
        TOKENHUB_KEYCHAIN_SERVICE,
        "api-key",
        "PIXEL3MF_TOKENHUB_API_KEY",
    )


def _cos_credentials() -> tuple[str | None, str | None]:
    secret_id = _credential(
        COS_KEYCHAIN_SERVICE,
        "secret-id",
        "PIXEL3MF_COS_SECRET_ID",
    )
    secret_key = _credential(
        COS_KEYCHAIN_SERVICE,
        "secret-key",
        "PIXEL3MF_COS_SECRET_KEY",
    )
    return secret_id, secret_key


def configure_keychain(kind: str) -> None:
    entries = {
        "tokenhub": (TOKENHUB_KEYCHAIN_SERVICE, "api-key"),
        "cos-secret-id": (COS_KEYCHAIN_SERVICE, "secret-id"),
        "cos-secret-key": (COS_KEYCHAIN_SERVICE, "secret-key"),
    }
    if kind not in entries:
        raise ValueError(f"unsupported Keychain credential kind: {kind}")
    security = shutil.which("security")
    if security is None:
        raise RuntimeError("macOS security command is unavailable")
    service, account = entries[kind]
    print(f"Enter the {kind} value at the macOS Keychain prompt.", file=sys.stderr)
    result = subprocess.run(
        [
            security,
            "add-generic-password",
            "-U",
            "-s",
            service,
            "-a",
            account,
            "-w",
        ],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"failed to store {kind} in macOS Keychain")


def _new_run_dir(output_root: Path, character_name: str) -> Path:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    stem = f"{timestamp}_{_slug(character_name)}"
    candidate = output_root / stem
    suffix = 2
    while candidate.exists():
        candidate = output_root / f"{stem}_{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate.resolve()


def _resolve_text(value: str | None, file_path: str | None, label: str) -> str:
    if bool(value) == bool(file_path):
        raise ValueError(f"provide exactly one of --{label} or --{label}-file")
    if file_path:
        return Path(file_path).expanduser().resolve().read_text(encoding="utf-8").strip()
    assert value is not None
    return value.strip()


def _state_path(run_dir: str | Path) -> Path:
    return Path(run_dir).expanduser().resolve() / STATE_FILENAME


def load_state(run_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    resolved = Path(run_dir).expanduser().resolve()
    state_path = resolved / STATE_FILENAME
    if not state_path.is_file():
        raise FileNotFoundError(f"WorkBuddy state not found: {state_path}")
    state = _read_json(state_path)
    if state.get("version") != STATE_VERSION:
        raise ValueError(f"unsupported WorkBuddy state version: {state.get('version')}")
    if state.get("run_id") != resolved.name:
        raise ValueError("WorkBuddy state run_id does not match its run directory")
    if state.get("max_attempts") != MAX_GENERATION_ATTEMPTS:
        raise ValueError(
            f"WorkBuddy state max_attempts must remain {MAX_GENERATION_ATTEMPTS}"
        )
    return resolved, state


def init_run(
    *,
    character_name: str,
    character_request: str,
    original_request: str,
    route: str,
    output_root: str | Path = "output",
    research_status: str = "not_applicable",
    research_path: str | Path | None = None,
    official_sources: list[str] | None = None,
    user_references: list[str] | None = None,
    source_image: str | Path | None = None,
    edit_defect: str | None = None,
    use_bundled_style: bool = False,
    include_action_reference: bool = False,
) -> Path:
    if route not in {"generate", "edit", "direct"}:
        raise ValueError("route must be generate, edit, or direct")
    if research_status not in {"completed", "not_applicable"}:
        raise ValueError("research status must be completed or not_applicable")
    sources = list(official_sources or [])
    resolved_research = (
        Path(research_path).expanduser().resolve() if research_path else None
    )
    if research_status == "completed":
        if (
            resolved_research is None
            or not resolved_research.is_file()
            or not 1 <= len(sources) <= 4
        ):
            raise ValueError(
                "completed research requires a research file and 1-4 official URLs"
            )
    elif resolved_research is not None or sources:
        raise ValueError("not_applicable research cannot include a research file or URLs")
    resolved_source = Path(source_image).expanduser().resolve() if source_image else None
    if route in {"edit", "direct"} and (
        resolved_source is None or not resolved_source.is_file()
    ):
        raise ValueError(f"route {route} requires --source-image")
    if route == "edit" and not edit_defect:
        raise ValueError("route edit requires --edit-defect")
    references = [str(Path(value).expanduser().resolve()) for value in user_references or []]
    for reference in references:
        if not Path(reference).is_file():
            raise FileNotFoundError(f"reference image not found: {reference}")

    root = Path(output_root).expanduser()
    if not root.is_absolute():
        root = (PROJECT_ROOT / root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_dir = _new_run_dir(root, character_name)
    research_output = None
    if resolved_research is not None:
        research_output = run_dir / "00_official_character_research.md"
        shutil.copy2(resolved_research, research_output)
    direct_source = None
    source_sha256 = None
    if resolved_source is not None:
        suffix = resolved_source.suffix.lower() or ".bin"
        direct_source = run_dir / f"00_user_source_original{suffix}"
        shutil.copy2(resolved_source, direct_source)
        source_sha256 = hashlib.sha256(direct_source.read_bytes()).hexdigest()

    state: dict[str, Any] = {
        "version": STATE_VERSION,
        "run_id": run_dir.name,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "status": "initialized",
        "route": route,
        "character_name": character_name,
        "character_request": character_request,
        "generation_prompt_template": _prompt_block(route) if route != "direct" else None,
        "original_request": original_request,
        "edit_defect": edit_defect,
        "research": {
            "status": research_status,
            "path": str(research_output) if research_output else None,
            "sources": sources,
        },
        "user_references": references,
        "source_image": str(direct_source) if direct_source else None,
        "source_sha256": source_sha256,
        "use_bundled_style": bool(use_bundled_style),
        "include_action_reference": bool(include_action_reference),
        "max_attempts": MAX_GENERATION_ATTEMPTS,
        "attempts": [],
        "selected_attempt": None,
        "cleanup_required": False,
        "pipeline_attempts": [],
        "pipeline_run_dir": None,
    }
    _write_json(run_dir / STATE_FILENAME, state)
    return run_dir


def _prompt_block(route: str) -> str:
    source = GENERATION_PROMPT_PATH.read_text(
        encoding="utf-8"
    )
    heading = (
        "## New-generation payload"
        if route == "generate"
        else "## Explicit user-source edit payload"
    )
    section = source.split(heading, 1)
    if len(section) != 2:
        raise RuntimeError(f"prompt section not found: {heading}")
    match = re.search(r"```text\n(.*?)\n```", section[1], flags=re.DOTALL)
    if not match:
        raise RuntimeError(f"fenced prompt not found below {heading}")
    return match.group(1)


def _research_prompt_value(state: dict[str, Any]) -> str:
    research = state["research"]
    if research["status"] != "completed":
        return "not_applicable — original or non-character subject"
    research_path = Path(research["path"])
    if not research_path.is_file():
        raise FileNotFoundError(
            f"official-character research file is unavailable: {research_path}"
        )
    research_value = research_path.read_text(encoding="utf-8").strip()
    if not research_value:
        raise ValueError("official-character research file is empty")
    # Keep citations and audit notes out of the image payload when a concise,
    # explicitly approved identity block is provided. Preserve legacy briefs.
    identity = re.search(r"```identity\n(.*?)\n```", research_value, flags=re.DOTALL)
    if identity:
        research_value = identity.group(1).strip()
        if not research_value:
            raise ValueError("image identity brief is empty")
    if len(research_value) > 6000:
        raise ValueError(
            "official-character research brief exceeds the 6000-character limit"
        )
    return research_value


def render_prompt(state: dict[str, Any]) -> str:
    route = state["route"]
    if route == "direct":
        raise ValueError("direct conversion does not have a generation prompt")
    prompt = state.get("generation_prompt_template") or _prompt_block(route)
    if route == "generate":
        prompt = prompt.replace("<character>", state["character_request"])
    else:
        prompt = prompt.replace("<user-requested defect>", state["edit_defect"])
    prompt = prompt.replace(
        "<official-character-research-file>", _research_prompt_value(state)
    )
    remaining = re.findall(r"<[^>]+>", prompt)
    if remaining:
        raise RuntimeError(f"unresolved prompt placeholders: {remaining}")
    return prompt


def native_reference_files(state: dict[str, Any]) -> list[Path]:
    """Return the actual original inputs for native generation, without compositing."""
    paths: list[Path] = []
    if state.get("use_bundled_style"):
        paths.extend(CORE_SKILL_DIR / "assets" / name for name in (
            "reference-24x24-block-style.png",
            "reference-coarse-density-a.png",
            "reference-coarse-density-b.png",
        ))
    if state.get("include_action_reference"):
        paths.append(CORE_SKILL_DIR / "assets" / "reference-action-interaction.png")
    if state.get("route") == "edit" and state.get("source_image"):
        paths.insert(0, Path(state["source_image"]))
    paths.extend(Path(value) for value in state.get("user_references", []))
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"registered native reference is unavailable: {path}")
    return paths


def _compose_reference_sheet(paths: list[Path], output_path: Path) -> Path:
    if not paths:
        raise ValueError("reference sheet requires at least one image")
    images: list[Image.Image] = []
    try:
        for path in paths:
            with Image.open(path) as image:
                images.append(image.convert("RGB"))
        columns = min(2, len(images))
        rows = math.ceil(len(images) / columns)
        cell = 480
        gap = 16
        canvas = Image.new(
            "RGB",
            (columns * cell + (columns + 1) * gap, rows * cell + (rows + 1) * gap),
            "white",
        )
        for index, image in enumerate(images):
            fitted = ImageOps.contain(image, (cell, cell), Image.Resampling.LANCZOS)
            column = index % columns
            row = index // columns
            x = gap + column * (cell + gap) + (cell - fitted.width) // 2
            y = gap + row * (cell + gap) + (cell - fitted.height) // 2
            canvas.paste(fitted, (x, y))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output_path, format="PNG", optimize=True)
        return output_path
    finally:
        for image in images:
            image.close()


def prepare_references(run_dir: Path, state: dict[str, Any]) -> list[Path]:
    reference_dir = run_dir / "references"
    reference_dir.mkdir(exist_ok=True)
    prepared: list[Path] = []
    if state.get("use_bundled_style"):
        style_paths = [
            CORE_SKILL_DIR / "assets" / "reference-24x24-block-style.png",
            CORE_SKILL_DIR / "assets" / "reference-coarse-density-a.png",
            CORE_SKILL_DIR / "assets" / "reference-coarse-density-b.png",
        ]
        prepared.append(
            _compose_reference_sheet(style_paths, reference_dir / "style-sheet.png")
        )
    if state.get("include_action_reference"):
        action = CORE_SKILL_DIR / "assets" / "reference-action-interaction.png"
        action_output = reference_dir / "action-reference.png"
        shutil.copy2(action, action_output)
        prepared.append(action_output)
    user_paths = [Path(value) for value in state.get("user_references", [])]
    if state.get("route") == "edit" and state.get("source_image"):
        user_paths.insert(0, Path(state["source_image"]))
    if user_paths:
        prepared.append(
            _compose_reference_sheet(user_paths, reference_dir / "user-sheet.png")
        )
    if len(prepared) > 3:
        raise RuntimeError("TokenHub reference preparation exceeded three images")
    return prepared


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    if len(encoded) > 10 * 1024 * 1024:
        raise ValueError(f"base64 reference exceeds 10 MiB: {path}")
    return f"data:{mime};base64,{encoded}"


def _sanitize_state_text(value: str) -> str:
    value = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+|bearer\s+)[^\s\"']+",
        lambda match: match.group(1) + "[REDACTED]",
        value,
    )
    return re.sub(
        r"(https?://[^\s?\"']+)\?[^\s\"']+",
        r"\1?[REDACTED_QUERY]",
        value,
    )


def _safe_error(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": _sanitize_state_text(str(exc))[:1200],
    }


def _safe_response_message(response: requests.Response) -> str:
    try:
        body = response.json()
        message = json.dumps(body, ensure_ascii=False)
    except ValueError:
        message = response.text
    return _sanitize_state_text(message)[:1200]


def _is_reference_url_error(error: TokenHubHTTPError) -> bool:
    if error.status_code not in {400, 415, 422}:
        return False
    text = error.safe_message.lower()
    image_term = any(term in text for term in ("image", "images", "图片"))
    address_term = any(
        term in text
        for term in ("url", "uri", "address", "format", "地址", "格式")
    )
    return image_term and address_term


class TokenHubClient:
    def __init__(
        self,
        api_key: str,
        config: dict[str, Any],
        *,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.config = config
        self.session = session or requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, url: str, payload: dict[str, Any], timeout: float = 60) -> dict[str, Any]:
        try:
            response = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise TokenHubError(f"TokenHub request failed: {type(exc).__name__}") from exc
        if not response.ok:
            raise TokenHubHTTPError(response.status_code, _safe_response_message(response))
        try:
            value = response.json()
        except ValueError as exc:
            raise TokenHubError("TokenHub returned non-JSON data") from exc
        if not isinstance(value, dict):
            raise TokenHubError("TokenHub response must be a JSON object")
        return value

    def poll(self, task_id: str) -> dict[str, Any]:
        tokenhub = self.config["tokenhub"]
        deadline = time.monotonic() + float(tokenhub["timeout_seconds"])
        poll_errors = 0
        while time.monotonic() < deadline:
            time.sleep(float(tokenhub["poll_interval_seconds"]))
            try:
                result = self._post(
                    tokenhub["query_url"],
                    {"model": tokenhub["model"], "id": task_id},
                )
                poll_errors = 0
            except (TokenHubError, TokenHubHTTPError):
                poll_errors += 1
                if poll_errors >= 3:
                    raise
                continue
            status = str(result.get("status", "")).lower()
            if status in {"completed", "succeeded", "success"}:
                data = result.get("data")
                if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                    raise TokenHubError("completed TokenHub task did not include image data")
                image_url = data[0].get("url")
                if not isinstance(image_url, str) or not image_url:
                    raise TokenHubError("completed TokenHub task did not include an image URL")
                return {
                    "task_id": task_id,
                    "request_id": result.get("request_id"),
                    "image_url": image_url,
                    "revised_prompt": data[0].get("revised_prompt"),
                    "status": status,
                }
            if status in {"failed", "error", "cancelled", "canceled"}:
                raise TokenHubTerminalError(
                    f"TokenHub task {task_id} ended with status {status}"
                )
        raise TimeoutError(f"TokenHub task {task_id} did not finish before timeout")

    def generate(
        self,
        prompt: str,
        image_urls: list[str],
        *,
        on_submitted: Any | None = None,
    ) -> dict[str, Any]:
        tokenhub = self.config["tokenhub"]
        payload: dict[str, Any] = {
            "model": tokenhub["model"],
            "prompt": prompt,
            "size": tokenhub["size"],
            "revise": 0,
            "logo_add": 0,
        }
        if image_urls:
            payload["images"] = image_urls
        submitted = self._post(tokenhub["submit_url"], payload)
        submitted_data = submitted.get("data")
        if isinstance(submitted_data, list) and submitted_data and isinstance(
            submitted_data[0], dict
        ):
            direct_url = submitted_data[0].get("url")
            if isinstance(direct_url, str) and direct_url:
                return {
                    "task_id": submitted.get("id") or submitted.get("request_id") or "synchronous",
                    "request_id": submitted.get("request_id"),
                    "image_url": direct_url,
                    "revised_prompt": submitted_data[0].get("revised_prompt"),
                    "status": str(submitted.get("status") or "completed").lower(),
                }
        task_id = submitted.get("id") or submitted.get("job_id")
        if not isinstance(task_id, str) or not task_id:
            raise TokenHubError("TokenHub submit response did not include a task id")
        if on_submitted is not None:
            on_submitted(task_id, submitted.get("request_id"))
        return self.poll(task_id)

    def download(self, url: str, output_path: Path) -> None:
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TokenHubError("failed to download the generated image") from exc
        try:
            with Image.open(io.BytesIO(response.content)) as image:
                image.convert("RGBA").save(output_path, format="PNG")
        except Exception as exc:
            raise TokenHubError("TokenHub result was not a readable image") from exc


class CosReferenceTransport:
    def __init__(self, config: dict[str, Any], secret_id: str, secret_key: str) -> None:
        try:
            from qcloud_cos import CosConfig, CosS3Client
        except ImportError as exc:
            raise RuntimeError(
                "COS fallback requires cos-python-sdk-v5; install project requirements"
            ) from exc
        cos = config["cos"]
        self.bucket = str(cos["bucket"])
        self.prefix = str(cos["object_prefix"]).strip("/")
        self.ttl = int(cos["signed_url_ttl_seconds"])
        self.uploaded_keys: list[str] = []
        if not self.bucket:
            raise RuntimeError("COS bucket is not configured")
        sdk_config = CosConfig(
            Region=str(cos["region"]),
            SecretId=secret_id,
            SecretKey=secret_key,
            Scheme="https",
        )
        self.client = CosS3Client(sdk_config)

    def upload(self, run_id: str, paths: list[Path]) -> tuple[list[str], list[str]]:
        urls: list[str] = []
        keys: list[str] = []
        for path in paths:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            key = f"{self.prefix}/{run_id}/{digest}-{path.name}"
            with path.open("rb") as handle:
                self.client.put_object(Bucket=self.bucket, Key=key, Body=handle)
            self.uploaded_keys.append(key)
            url = self.client.get_presigned_url(
                Method="GET",
                Bucket=self.bucket,
                Key=key,
                Expired=self.ttl,
            )
            keys.append(key)
            urls.append(url)
        return urls, keys

    def cleanup(self, keys: list[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for key in keys:
            try:
                self.client.delete_object(Bucket=self.bucket, Key=key)
                results.append({"key": key, "deleted": True})
            except Exception as exc:
                results.append(
                    {"key": key, "deleted": False, "error": type(exc).__name__}
                )
        return results


def _objective_preflight(path: Path) -> dict[str, Any]:
    reasons: list[str] = []
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha_extrema = rgba.getchannel("A").getextrema()
        if alpha_extrema != (255, 255):
            reasons.append("generated source is not fully opaque")
        rgb = rgba.convert("RGB")
        width, height = rgb.size
        border_crops = (
            rgb.crop((0, 0, width, 1)),
            rgb.crop((0, height - 1, width, height)),
            rgb.crop((0, 0, 1, height)),
            rgb.crop((width - 1, 0, width, height)),
        )
        if any(crop.getextrema() != ((255, 255),) * 3 for crop in border_crops):
            reasons.append("generated source border is not uniformly pure white")
    grid: dict[str, Any] | None = None
    try:
        detected = detect_source_grid(path)
        grid = {"width": int(detected["width"]), "height": int(detected["height"])}
        if not (60 <= grid["width"] <= 85 and 60 <= grid["height"] <= 85):
            reasons.append(
                f"detected source grid {grid['width']}x{grid['height']} is outside 60-85"
            )
    except Exception as exc:
        reasons.append(f"Perfect Pixel preflight failed: {type(exc).__name__}: {exc}")
    return {
        "passed": not reasons,
        "fully_opaque": alpha_extrema == (255, 255),
        "pure_white_border": not any(
            reason.startswith("generated source border") for reason in reasons
        ),
        "detected_grid": grid,
        "reasons": reasons,
    }


def generate_source(
    run_dir: str | Path,
    *,
    config_path: str | Path | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    resolved, state = load_state(run_dir)
    if state["route"] == "direct":
        raise ValueError("direct conversion cannot call image generation")
    if state.get("cleanup_required"):
        raise RuntimeError("COS reference cleanup is required before continuing")
    attempts = state["attempts"]
    if len(attempts) >= MAX_GENERATION_ATTEMPTS:
        raise RuntimeError("maximum of three generation attempts has been reached")
    if state.get("status") not in {"initialized", "ready_for_retry"}:
        raise RuntimeError(
            f"cannot generate while WorkBuddy run status is {state.get('status')}"
        )
    if state.get("selected_attempt") is not None:
        raise RuntimeError("a source attempt is already accepted")
    api_key = _tokenhub_api_key()
    if not api_key:
        raise RuntimeError(
            "TokenHub API key not found in macOS Keychain or PIXEL3MF_TOKENHUB_API_KEY"
        )
    config = load_config(config_path)
    prompt = render_prompt(state)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    references = prepare_references(resolved, state)
    number = len(attempts) + 1
    candidate = resolved / f"01_source_attempt_{number:02d}.png"
    if candidate.exists():
        raise FileExistsError(f"generation candidate already exists: {candidate}")
    attempt: dict[str, Any] = {
        "number": number,
        "created_at": _now_iso(),
        "finished_at": None,
        "file": str(candidate),
        "provider": "tokenhub",
        "model": config["tokenhub"]["model"],
        "logo_add": 0,
        "prompt_sha256": prompt_hash,
        "reference_files": [str(path) for path in references],
        "reference_transport": "data-uri",
        "task_id": None,
        "request_id": None,
        "submission_mode": None,
        "objective_validation": None,
        "visual_decision": None,
        "visual_reason": None,
        "cos_objects": [],
        "cos_cleanup": [],
        "status": "submitting",
        "error": None,
    }
    attempts.append(attempt)
    state["status"] = "generating"
    state["updated_at"] = _now_iso()
    _write_json(resolved / STATE_FILENAME, state)

    client = TokenHubClient(api_key, config, session=session)
    cos_transport: CosReferenceTransport | None = None
    started = time.monotonic()
    cleanup_safe = False
    asynchronous_submission = False
    remote_completed = False

    def persist_submission(task_id: str, request_id: str | None) -> None:
        nonlocal asynchronous_submission
        asynchronous_submission = True
        attempt["task_id"] = task_id
        attempt["request_id"] = request_id
        attempt["submission_mode"] = "asynchronous"
        attempt["status"] = "generation_in_progress"
        state["status"] = "generation_in_progress"
        state["updated_at"] = _now_iso()
        _write_json(resolved / STATE_FILENAME, state)

    try:
        data_urls = [_data_uri(path) for path in references]
        try:
            result = client.generate(
                prompt,
                data_urls,
                on_submitted=persist_submission,
            )
        except TokenHubHTTPError as exc:
            if (
                attempt.get("task_id")
                or not references
                or not _is_reference_url_error(exc)
            ):
                raise
            secret_id, secret_key = _cos_credentials()
            if not secret_id or not secret_key:
                raise RuntimeError(
                    "TokenHub rejected data URIs and COS credentials are unavailable"
                ) from exc
            cos_transport = CosReferenceTransport(config, secret_id, secret_key)
            try:
                urls, _ = cos_transport.upload(state["run_id"], references)
            finally:
                attempt["cos_objects"] = list(cos_transport.uploaded_keys)
            attempt["reference_transport"] = "cos-signed-url"
            result = client.generate(
                prompt,
                urls,
                on_submitted=persist_submission,
            )
        remote_completed = True
        attempt["task_id"] = result["task_id"]
        attempt["request_id"] = result.get("request_id") or attempt.get("request_id")
        attempt["submission_mode"] = (
            "asynchronous" if asynchronous_submission else "synchronous"
        )
        attempt["status"] = "downloading"
        state["status"] = "downloading"
        state["updated_at"] = _now_iso()
        _write_json(resolved / STATE_FILENAME, state)
        client.download(result["image_url"], candidate)
        validation = _objective_preflight(candidate)
        attempt["objective_validation"] = validation
        if validation["passed"]:
            attempt["status"] = "awaiting_visual_decision"
            state["status"] = "awaiting_visual_decision"
        else:
            attempt["status"] = "objective_rejected"
            attempt["visual_decision"] = "not_required"
            attempt["visual_reason"] = "; ".join(validation["reasons"])
            state["status"] = (
                "attempts_exhausted"
                if number >= MAX_GENERATION_ATTEMPTS
                else "ready_for_retry"
            )
        cleanup_safe = True
    except TokenHubTerminalError as exc:
        attempt["status"] = "failed"
        attempt["error"] = _safe_error(exc)
        state["status"] = (
            "attempts_exhausted"
            if number >= MAX_GENERATION_ATTEMPTS
            else "ready_for_retry"
        )
        cleanup_safe = True
        raise
    except Exception as exc:
        submitted = bool(attempt.get("task_id"))
        if submitted and asynchronous_submission and remote_completed:
            attempt["status"] = "download_pending"
            state["status"] = "download_pending"
        elif submitted and not remote_completed:
            attempt["status"] = "generation_unknown"
            state["status"] = "generation_unknown"
        else:
            attempt["status"] = "failed"
            state["status"] = (
                "attempts_exhausted"
                if number >= MAX_GENERATION_ATTEMPTS
                else "ready_for_retry"
            )
        attempt["error"] = _safe_error(exc)
        cleanup_safe = remote_completed or not submitted
        raise
    finally:
        if cos_transport is not None:
            attempt["cos_objects"] = list(cos_transport.uploaded_keys)
        if cleanup_safe and cos_transport is not None and cos_transport.uploaded_keys:
            attempt["cos_cleanup"] = cos_transport.cleanup(
                cos_transport.uploaded_keys
            )
            if any(not item["deleted"] for item in attempt["cos_cleanup"]):
                state["cleanup_required"] = True
        attempt["duration_seconds"] = round(time.monotonic() - started, 3)
        attempt["finished_at"] = _now_iso()
        state["updated_at"] = _now_iso()
        _write_json(resolved / STATE_FILENAME, state)
    return attempt


def normalize_generated_background(path: Path) -> dict[str, Any]:
    """Whiten only opaque, near-white pixels connected to a near-white border."""
    import numpy as np
    from scipy.ndimage import binary_propagation

    with Image.open(path) as image:
        pixels = np.array(image.convert("RGBA"))
    rgb = pixels[:, :, :3]
    metadata: dict[str, Any] = {
        "method": "border_connected_near_white",
        "minimum_channel": 240,
        "maximum_channel_spread": 8,
        "connectivity": 4,
        "changed_pixels": 0,
        "status": "unchanged",
    }
    if not np.all(pixels[:, :, 3] == 255):
        metadata["status"] = "skipped_nonopaque"
        return metadata
    near_white = np.all(rgb >= 240, axis=2) & (np.ptp(rgb, axis=2) <= 8)
    border = np.zeros(near_white.shape, dtype=bool)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    if not np.all(near_white[border]):
        metadata["status"] = "skipped_nonwhite_border"
        return metadata
    background = binary_propagation(border, mask=near_white)
    changed = background & np.any(rgb != 255, axis=2)
    metadata["changed_pixels"] = int(changed.sum())
    if metadata["changed_pixels"]:
        rgb[changed] = 255
        Image.fromarray(pixels).save(path)
        metadata["status"] = "normalized"
    return metadata


def import_workbuddy_candidate(
    run_dir: str | Path,
    *,
    source_image: str | Path,
    model: str = "workbuddy-default",
) -> dict[str, Any]:
    """Register one image made by WorkBuddy's native generator as an attempt."""
    resolved, state = load_state(run_dir)
    if state["route"] == "direct":
        raise ValueError("direct conversion cannot import a generated candidate")
    if state.get("cleanup_required"):
        raise RuntimeError("COS reference cleanup is required before continuing")
    attempts = state["attempts"]
    if len(attempts) >= MAX_GENERATION_ATTEMPTS:
        raise RuntimeError("maximum of three generation attempts has been reached")
    if state.get("status") not in {"initialized", "ready_for_retry"}:
        raise RuntimeError(
            f"cannot import a candidate while WorkBuddy run status is {state.get('status')}"
        )
    if state.get("selected_attempt") is not None:
        raise RuntimeError("a source attempt is already accepted")

    source = Path(source_image).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"WorkBuddy candidate image not found: {source}")
    number = len(attempts) + 1
    candidate = resolved / f"01_source_attempt_{number:02d}.png"
    if candidate.exists():
        raise FileExistsError(f"generation candidate already exists: {candidate}")
    original = resolved / f"01_source_attempt_{number:02d}_original{source.suffix.lower() or '.bin'}"
    if original.exists():
        raise FileExistsError(f"original generation candidate already exists: {original}")
    shutil.copy2(source, original)
    with Image.open(original) as image:
        image.convert("RGBA").save(candidate)
    normalization = normalize_generated_background(candidate)
    normalization["original_file"] = str(original)
    normalization["original_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
    normalization["normalized_sha256"] = hashlib.sha256(candidate.read_bytes()).hexdigest()

    validation = _objective_preflight(candidate)
    attempt: dict[str, Any] = {
        "number": number,
        "created_at": _now_iso(),
        "finished_at": _now_iso(),
        "file": str(candidate),
        "provider": "workbuddy",
        "model": model.strip() or "workbuddy-default",
        "logo_add": None,
        "prompt_sha256": hashlib.sha256(
            render_prompt(state).encode("utf-8")
        ).hexdigest(),
        "reference_files": [str(path) for path in native_reference_files(state)],
        "reference_transport": "workbuddy-native",
        "task_id": None,
        "request_id": None,
        "submission_mode": "host-native",
        "background_normalization": normalization,
        "objective_validation": validation,
        "visual_decision": None if validation["passed"] else "not_required",
        "visual_reason": None if validation["passed"] else "; ".join(validation["reasons"]),
        "cos_objects": [],
        "cos_cleanup": [],
        "duration_seconds": None,
        "status": (
            "awaiting_visual_decision" if validation["passed"] else "objective_rejected"
        ),
        "error": None,
    }
    attempts.append(attempt)
    state["status"] = (
        "awaiting_visual_decision"
        if validation["passed"]
        else (
            "attempts_exhausted"
            if number >= MAX_GENERATION_ATTEMPTS
            else "ready_for_retry"
        )
    )
    state["updated_at"] = _now_iso()
    _write_json(resolved / STATE_FILENAME, state)
    return attempt


def resume_generation(
    run_dir: str | Path,
    *,
    config_path: str | Path | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    resolved, state = load_state(run_dir)
    if state.get("status") not in {"generation_unknown", "download_pending"}:
        raise RuntimeError(
            "resume-generation requires generation_unknown or download_pending status"
        )
    matches = [
        attempt
        for attempt in state["attempts"]
        if attempt.get("status") in {"generation_unknown", "download_pending"}
        and attempt.get("task_id")
    ]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one unresolved TokenHub task")
    attempt = matches[0]
    api_key = _tokenhub_api_key()
    if not api_key:
        raise RuntimeError("TokenHub API key is required to resume generation")
    config = load_config(config_path)
    client = TokenHubClient(api_key, config, session=session)
    cos_objects = list(attempt.get("cos_objects") or [])
    cos_transport: CosReferenceTransport | None = None
    cleanup_safe = False
    state["status"] = "generation_in_progress"
    attempt["status"] = "generation_in_progress"
    state["updated_at"] = _now_iso()
    _write_json(resolved / STATE_FILENAME, state)
    try:
        result = client.poll(str(attempt["task_id"]))
        attempt["request_id"] = result.get("request_id") or attempt.get("request_id")
        candidate = Path(attempt["file"])
        attempt["status"] = "downloading"
        state["status"] = "downloading"
        state["updated_at"] = _now_iso()
        _write_json(resolved / STATE_FILENAME, state)
        client.download(result["image_url"], candidate)
        validation = _objective_preflight(candidate)
        attempt["objective_validation"] = validation
        attempt["error"] = None
        if validation["passed"]:
            attempt["status"] = "awaiting_visual_decision"
            state["status"] = "awaiting_visual_decision"
        else:
            attempt["status"] = "objective_rejected"
            attempt["visual_decision"] = "not_required"
            attempt["visual_reason"] = "; ".join(validation["reasons"])
            state["status"] = (
                "attempts_exhausted"
                if len(state["attempts"]) >= MAX_GENERATION_ATTEMPTS
                else "ready_for_retry"
            )
        cleanup_safe = True
    except TokenHubTerminalError as exc:
        attempt["status"] = "failed"
        attempt["error"] = _safe_error(exc)
        state["status"] = (
            "attempts_exhausted"
            if len(state["attempts"]) >= MAX_GENERATION_ATTEMPTS
            else "ready_for_retry"
        )
        cleanup_safe = True
        raise
    except Exception as exc:
        attempt["status"] = (
            "download_pending" if state.get("status") == "downloading"
            else "generation_unknown"
        )
        attempt["error"] = _safe_error(exc)
        state["status"] = attempt["status"]
        cleanup_safe = attempt["status"] == "download_pending"
        raise
    finally:
        if cleanup_safe and cos_objects:
            secret_id, secret_key = _cos_credentials()
            if secret_id and secret_key:
                cos_transport = CosReferenceTransport(config, secret_id, secret_key)
                attempt["cos_cleanup"] = cos_transport.cleanup(cos_objects)
                state["cleanup_required"] = any(
                    not item["deleted"] for item in attempt["cos_cleanup"]
                )
            else:
                state["cleanup_required"] = True
                attempt["cos_cleanup"] = [
                    {"key": key, "deleted": False, "error": "MissingCredentials"}
                    for key in cos_objects
                ]
        attempt["finished_at"] = _now_iso()
        state["updated_at"] = _now_iso()
        _write_json(resolved / STATE_FILENAME, state)
    return attempt


def cleanup_references(
    run_dir: str | Path,
    *,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    resolved, state = load_state(run_dir)
    if state.get("status") in {"generation_in_progress", "generation_unknown"}:
        raise RuntimeError("cannot clean references while a TokenHub task may be running")
    pending: list[tuple[dict[str, Any], list[str]]] = []
    for attempt in state["attempts"]:
        objects = list(attempt.get("cos_objects") or [])
        deleted = {
            item["key"]
            for item in attempt.get("cos_cleanup") or []
            if item.get("deleted")
        }
        remaining = [key for key in objects if key not in deleted]
        if remaining:
            pending.append((attempt, remaining))
    if not pending:
        state["cleanup_required"] = False
        state["updated_at"] = _now_iso()
        _write_json(resolved / STATE_FILENAME, state)
        return []
    secret_id, secret_key = _cos_credentials()
    if not secret_id or not secret_key:
        raise RuntimeError("COS credentials are required for reference cleanup")
    transport = CosReferenceTransport(load_config(config_path), secret_id, secret_key)
    all_results: list[dict[str, Any]] = []
    for attempt, keys in pending:
        results = transport.cleanup(keys)
        existing = list(attempt.get("cos_cleanup") or [])
        by_key = {item["key"]: item for item in existing}
        for result in results:
            by_key[result["key"]] = result
        attempt["cos_cleanup"] = list(by_key.values())
        all_results.extend(results)
    state["cleanup_required"] = any(not item["deleted"] for item in all_results)
    state["updated_at"] = _now_iso()
    _write_json(resolved / STATE_FILENAME, state)
    return all_results


def decide_source(
    run_dir: str | Path,
    *,
    attempt_number: int,
    decision: str,
    reason: str,
) -> dict[str, Any]:
    resolved, state = load_state(run_dir)
    if decision not in {"accepted", "rejected"}:
        raise ValueError("decision must be accepted or rejected")
    matches = [attempt for attempt in state["attempts"] if attempt["number"] == attempt_number]
    if len(matches) != 1:
        raise ValueError(f"generation attempt not found: {attempt_number}")
    attempt = matches[0]
    if attempt.get("status") != "awaiting_visual_decision":
        raise RuntimeError("attempt is not awaiting a visual decision")
    if attempt.get("visual_decision") not in {None, "not_required"}:
        raise RuntimeError("generation attempt already has a visual decision")
    if decision == "accepted":
        if not attempt.get("objective_validation", {}).get("passed"):
            raise RuntimeError("cannot accept an attempt that failed objective validation")
        selected = state.get("selected_attempt")
        if selected is not None and selected != attempt_number:
            raise RuntimeError("another generation attempt is already accepted")
        source_path = Path(attempt["file"])
        if not source_path.is_file():
            raise FileNotFoundError(f"candidate image not found: {source_path}")
        shutil.copy2(source_path, resolved / "01_source.png")
        state["selected_attempt"] = attempt_number
        state["status"] = "source_accepted"
    else:
        if not reason.strip():
            raise ValueError("a rejection reason is required")
        state["status"] = (
            "attempts_exhausted"
            if len(state["attempts"]) >= state["max_attempts"]
            else "ready_for_retry"
        )
    attempt["visual_decision"] = decision
    attempt["visual_reason"] = reason.strip() or "accepted by WorkBuddy visual review"
    attempt["status"] = "accepted" if decision == "accepted" else "visual_rejected"
    state["updated_at"] = _now_iso()
    _write_json(resolved / STATE_FILENAME, state)
    return attempt


def _alpha_profile(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        alpha = image.convert("RGBA").getchannel("A")
        values = [index for index, count in enumerate(alpha.histogram()) if count]
    return {
        "values": values,
        "binary": set(values).issubset({0, 255}),
        "fully_opaque": values == [255],
    }


def _generation_manifest(state: dict[str, Any]) -> dict[str, Any] | None:
    if state["route"] == "direct":
        return None
    selected_number = state.get("selected_attempt")
    selected = next(
        (
            attempt
            for attempt in state["attempts"]
            if attempt.get("number") == selected_number
        ),
        None,
    )
    return {
        "version": 1,
        "provider": (selected or {}).get("provider", "unknown"),
        "model": (selected or {}).get("model", "unknown"),
        "logo_add": (selected or {}).get("logo_add"),
        "attempts": state["attempts"],
        "selected_attempt": selected_number,
    }


def _archive_failed_pipeline(resolved: Path, state: dict[str, Any]) -> Path | None:
    manifest_path = resolved / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = _read_json(manifest_path)
    if manifest.get("status") == "success":
        raise FileExistsError("this WorkBuddy run already completed successfully")
    failures_root = resolved / "pipeline_failures"
    failures_root.mkdir(exist_ok=True)
    index = len(list(failures_root.glob("attempt_*"))) + 1
    archive = failures_root / f"attempt_{index:02d}"
    archive.mkdir()
    owned_names = {"manifest.json", "lumina_api.log"}
    for entry in list(resolved.iterdir()):
        if entry.name in owned_names or re.match(r"^(02|03|04|05|06|07|08)_", entry.name):
            shutil.move(str(entry), archive / entry.name)
    if state.get("pipeline_attempts"):
        last = state["pipeline_attempts"][-1]
        if last.get("status") in {"running", "failed"}:
            if last.get("status") == "running":
                last["status"] = "interrupted"
                last["finished_at"] = _now_iso()
            last["manifest"] = str(archive / "manifest.json")
    return archive


def convert_run(
    run_dir: str | Path,
    *,
    config_path: str | Path | None = None,
    alpha_policy: str = "auto",
    mask_override: str | Path | None = None,
    background_method: str = "auto",
    background_model: str = "auto",
    square_output: bool = False,
) -> Path:
    resolved, state = load_state(run_dir)
    if state.get("cleanup_required"):
        raise RuntimeError("COS reference cleanup is required before conversion")
    archived = _archive_failed_pipeline(resolved, state)
    if archived is not None:
        state["updated_at"] = _now_iso()
        _write_json(resolved / STATE_FILENAME, state)
    route = state["route"]
    if route == "direct":
        selected_source = Path(state["source_image"]) if state.get("source_image") else None
        if selected_source is None or not selected_source.is_file():
            raise FileNotFoundError("direct conversion source image is unavailable")
        actual_hash = hashlib.sha256(selected_source.read_bytes()).hexdigest()
        if actual_hash != state.get("source_sha256"):
            raise RuntimeError("registered direct source changed after init-run")
        canonical_source = resolved / "01_source.png"
        with Image.open(selected_source) as image:
            image.convert("RGBA").save(canonical_source)
    else:
        if state.get("selected_attempt") is None:
            raise RuntimeError("generation route requires an accepted source attempt")
        canonical_source = resolved / "01_source.png"
        if not canonical_source.is_file():
            raise FileNotFoundError("accepted source image is unavailable")
    alpha = _alpha_profile(canonical_source)
    if not alpha["binary"] and mask_override is None:
        raise ValueError("non-binary alpha requires --mask-override")
    config = load_config(config_path)
    research = state["research"]
    state["status"] = "converting"
    pipeline_attempt = {
        "number": len(state["pipeline_attempts"]) + 1,
        "started_at": _now_iso(),
        "finished_at": None,
        "status": "running",
        "manifest": str(resolved / "manifest.json"),
    }
    state["pipeline_attempts"].append(pipeline_attempt)
    state["updated_at"] = _now_iso()
    _write_json(resolved / STATE_FILENAME, state)
    try:
        result = run_pipeline(
            canonical_source,
            character_name=state["character_name"],
            output_root=resolved.parent,
            background_method=background_method,
            api_url=config["lumina"]["api_url"],
            official_character_research_path=research["path"],
            official_character_sources=research["sources"],
            official_character_research_status=research["status"],
            square_output=square_output,
            background_model=background_model,
            segmentation_device="cpu",
            segmentation_memory_limit_gb=8.0,
            working_padding_cells=2,
            mask_override=mask_override,
            allow_ambiguous_mask=False,
            alpha_policy=alpha_policy,
            run_dir=resolved,
            generation_metadata=_generation_manifest(state),
            source_provenance=(
                {
                    "original_path": str(selected_source),
                    "sha256": str(state["source_sha256"]),
                }
                if route == "direct"
                else None
            ),
        )
    except Exception:
        state["status"] = "conversion_failed"
        pipeline_attempt["status"] = "failed"
        pipeline_attempt["finished_at"] = _now_iso()
        state["updated_at"] = _now_iso()
        _write_json(resolved / STATE_FILENAME, state)
        raise
    state["status"] = "converted"
    pipeline_attempt["status"] = "success"
    pipeline_attempt["finished_at"] = _now_iso()
    state["pipeline_run_dir"] = str(result)
    state["updated_at"] = _now_iso()
    _write_json(resolved / STATE_FILENAME, state)
    return result


def _doctor_read_lumina_nozzle_width(lumina_dir: Path) -> Decimal:
    config_path = lumina_dir / "config.py"
    if not config_path.is_file():
        raise FileNotFoundError(f"Lumina config not found: {config_path}")
    tree = ast.parse(
        config_path.read_text(encoding="utf-8"), filename=str(config_path)
    )
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "PrinterConfig":
            continue
        for statement in node.body:
            target = None
            value = None
            if isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ):
                target = statement.target.id
                value = statement.value
            elif isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                if isinstance(statement.targets[0], ast.Name):
                    target = statement.targets[0].id
                    value = statement.value
            if target == "NOZZLE_WIDTH" and value is not None:
                return Decimal(str(ast.literal_eval(value)))
    raise RuntimeError(f"PrinterConfig.NOZZLE_WIDTH not found in {config_path}")


def _doctor_api_ready(base_url: str) -> bool:
    try:
        with urlopen(base_url.rstrip("/") + "/api/health", timeout=2) as response:
            return 200 <= int(response.status) < 300
    except Exception:
        return False


def doctor(config_path: str | Path | None = None) -> dict[str, Any]:
    config = load_config(config_path)
    checks: dict[str, dict[str, Any]] = {}

    def record(name: str, ok: bool, detail: str, severity: str = "error") -> None:
        checks[name] = {"ok": bool(ok), "detail": detail, "severity": severity}

    record("python", sys.version_info >= (3, 10), sys.version.split()[0])
    record("project_root", (PROJECT_ROOT / "tools" / "run_pipeline.py").is_file(), str(PROJECT_ROOT))
    required_modules = ("PIL", "requests", "psutil", "rembg", "perfect_pixel")
    missing_modules = [
        name for name in required_modules if importlib.util.find_spec(name) is None
    ]
    record(
        "python_dependencies",
        not missing_modules,
        "installed" if not missing_modules else f"missing: {', '.join(missing_modules)}",
    )
    lumina = PROJECT_ROOT / "Lumina-Layers"
    try:
        cell = _doctor_read_lumina_nozzle_width(lumina)
        record("lumina_cell", str(cell) == "0.42", f"{cell} mm")
    except Exception as exc:
        record("lumina_cell", False, f"{type(exc).__name__}: {exc}")
    api_url = str(config["lumina"]["api_url"])
    api_is_ready = _doctor_api_ready(api_url)
    record(
        "lumina_api",
        api_is_ready,
        f"ready at {api_url}" if api_is_ready else "not running; convert will start it locally",
        severity="warning",
    )
    profile = PROJECT_ROOT / "profiles" / "bambu_a1mini_0.4_0.08_extra_fine_pixel3mf.json"
    try:
        _read_json(profile)
        profile_ok = True
        profile_detail = str(profile)
    except Exception as exc:
        profile_ok = False
        profile_detail = f"{type(exc).__name__}: {exc}"
    record("a1mini_profile", profile_ok, profile_detail)
    tokenhub_key = _tokenhub_api_key()
    record(
        "tokenhub_credentials",
        tokenhub_key is not None,
        "configured" if tokenhub_key else "missing; direct conversion remains available",
        severity="warning",
    )
    record(
        "workbuddy_candidate_import",
        True,
        "available through render-prompt and import-candidate",
        severity="warning",
    )
    secret_id, secret_key = _cos_credentials()
    cos_complete = bool(secret_id and secret_key and config["cos"].get("bucket"))
    record(
        "cos_fallback",
        cos_complete,
        "configured" if cos_complete else "incomplete; only needed if TokenHub rejects data URIs",
        severity="warning",
    )
    try:
        import qcloud_cos  # noqa: F401

        cos_sdk = True
    except ImportError:
        cos_sdk = False
    record(
        "cos_sdk",
        cos_sdk,
        "installed" if cos_sdk else "cos-python-sdk-v5 is not installed",
        severity="warning",
    )
    weights = sorted((PROJECT_ROOT / ".cache" / "rembg").glob("*.onnx"))
    record(
        "isnet_weights",
        bool(weights),
        f"{len(weights)} cached model(s)" if weights else "first conversion may download models",
        severity="warning",
    )
    try:
        from build_workbuddy_skill import skill_tree_matches

        skill_synced = skill_tree_matches()
    except Exception as exc:
        skill_synced = False
        skill_detail = f"{type(exc).__name__}: {exc}"
    else:
        skill_detail = "synchronized" if skill_synced else "run tools/build_workbuddy_skill.py"
    record("workbuddy_skill", skill_synced, skill_detail)
    core_ready = all(
        check["ok"] for check in checks.values() if check["severity"] == "error"
    )
    tokenhub_generation_ready = core_ready and bool(tokenhub_key)
    generation_ready = core_ready
    return {
        "core_ready": core_ready,
        "generation_ready": generation_ready,
        "tokenhub_generation_ready": tokenhub_generation_ready,
        "workbuddy_candidate_import_ready": core_ready,
        "cos_fallback_ready": cos_complete and cos_sdk,
        "config_path": str(Path(config_path).resolve()) if config_path else str(DEFAULT_CONFIG_PATH),
        "checks": checks,
    }


def _print_doctor(report: dict[str, Any]) -> None:
    for name, check in report["checks"].items():
        symbol = "OK" if check["ok"] else ("WARN" if check["severity"] == "warning" else "FAIL")
        print(f"[{symbol}] {name}: {check['detail']}")
    print(f"core_ready={str(report['core_ready']).lower()}")
    print(f"generation_ready={str(report['generation_ready']).lower()}")
    print(
        "tokenhub_generation_ready="
        + str(report["tokenhub_generation_ready"]).lower()
    )
    print(
        "workbuddy_candidate_import_ready="
        + str(report["workbuddy_candidate_import_ready"]).lower()
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")

    keychain_parser = subparsers.add_parser("configure-keychain")
    keychain_parser.add_argument(
        "kind",
        choices=("tokenhub", "cos-secret-id", "cos-secret-key"),
    )

    init_parser = subparsers.add_parser("init-run")
    init_parser.add_argument("--character-name", required=True)
    character_request_group = init_parser.add_mutually_exclusive_group(required=True)
    character_request_group.add_argument("--character-request")
    character_request_group.add_argument("--character-request-file")
    request_group = init_parser.add_mutually_exclusive_group(required=True)
    request_group.add_argument("--request")
    request_group.add_argument("--request-file")
    init_parser.add_argument("--route", choices=("generate", "edit", "direct"), required=True)
    init_parser.add_argument("--output-root", default="output")
    init_parser.add_argument(
        "--research-status",
        choices=("completed", "not_applicable"),
        default="not_applicable",
    )
    init_parser.add_argument("--research-path")
    init_parser.add_argument("--official-source", action="append", default=[])
    init_parser.add_argument("--user-reference", action="append", default=[])
    init_parser.add_argument("--source-image")
    init_parser.add_argument("--edit-defect")
    styles = init_parser.add_mutually_exclusive_group()
    styles.add_argument("--with-bundled-style", dest="use_bundled_style", action="store_true")
    styles.add_argument("--no-bundled-style", dest="use_bundled_style", action="store_false")
    init_parser.set_defaults(use_bundled_style=False)
    init_parser.add_argument("--include-action-reference", action="store_true")

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--run-dir", required=True)

    prompt_parser = subparsers.add_parser("render-prompt")
    prompt_parser.add_argument("--run-dir", required=True)
    prompt_parser.add_argument("--json", action="store_true", help="Native prompt and exact registered reference paths")

    import_parser = subparsers.add_parser("import-candidate")
    import_parser.add_argument("--run-dir", required=True)
    import_parser.add_argument("--source-image", required=True)
    import_parser.add_argument("--model", default="workbuddy-default")

    resume_parser = subparsers.add_parser("resume-generation")
    resume_parser.add_argument("--run-dir", required=True)

    cleanup_parser = subparsers.add_parser("cleanup-references")
    cleanup_parser.add_argument("--run-dir", required=True)

    decide_parser = subparsers.add_parser("decide")
    decide_parser.add_argument("--run-dir", required=True)
    decide_parser.add_argument("--attempt", type=int, required=True)
    decide_parser.add_argument("--decision", choices=("accepted", "rejected"), required=True)
    decide_parser.add_argument("--reason", default="")

    convert_parser = subparsers.add_parser("convert")
    convert_parser.add_argument("--run-dir", required=True)
    convert_parser.add_argument("--alpha-policy", choices=("auto", "preserve", "repair"), default="auto")
    convert_parser.add_argument("--mask-override")
    convert_parser.add_argument("--background-method", choices=("auto", "rembg", "white"), default="auto")
    convert_parser.add_argument(
        "--background-model",
        choices=("auto", "isnet-anime", "isnet-general-use"),
        default="auto",
    )
    convert_parser.add_argument("--square-output", action="store_true")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "doctor":
        report = doctor(args.config)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_doctor(report)
        return
    if args.command == "configure-keychain":
        configure_keychain(args.kind)
        print(f"stored {args.kind} in macOS Keychain")
        return
    _require_runtime_dependencies()
    if args.command == "init-run":
        character_request = _resolve_text(
            args.character_request,
            args.character_request_file,
            "character-request",
        )
        original_request = _resolve_text(args.request, args.request_file, "request")
        run_dir = init_run(
            character_name=args.character_name,
            character_request=character_request,
            original_request=original_request,
            route=args.route,
            output_root=args.output_root,
            research_status=args.research_status,
            research_path=args.research_path,
            official_sources=args.official_source,
            user_references=args.user_reference,
            source_image=args.source_image,
            edit_defect=args.edit_defect,
            use_bundled_style=args.use_bundled_style,
            include_action_reference=args.include_action_reference,
        )
        print(run_dir)
        return
    if args.command == "generate":
        attempt = generate_source(args.run_dir, config_path=args.config)
        print(json.dumps(attempt, ensure_ascii=False, indent=2))
        return
    if args.command == "render-prompt":
        _, state = load_state(args.run_dir)
        if state["route"] == "direct":
            raise ValueError("direct conversion does not have an image-generation prompt")
        if args.json:
            incoming = Path(args.run_dir).expanduser().resolve() / "00_incoming"
            incoming.mkdir(exist_ok=True)
            print(json.dumps({"prompt": render_prompt(state), "reference_files": [str(path) for path in native_reference_files(state)], "output_dir": str(incoming)}, ensure_ascii=False, indent=2))
        else:
            print(render_prompt(state))
        return
    if args.command == "import-candidate":
        attempt = import_workbuddy_candidate(
            args.run_dir,
            source_image=args.source_image,
            model=args.model,
        )
        print(json.dumps(attempt, ensure_ascii=False, indent=2))
        return
    if args.command == "resume-generation":
        attempt = resume_generation(args.run_dir, config_path=args.config)
        print(json.dumps(attempt, ensure_ascii=False, indent=2))
        return
    if args.command == "cleanup-references":
        results = cleanup_references(args.run_dir, config_path=args.config)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return
    if args.command == "decide":
        attempt = decide_source(
            args.run_dir,
            attempt_number=args.attempt,
            decision=args.decision,
            reason=args.reason,
        )
        print(json.dumps(attempt, ensure_ascii=False, indent=2))
        return
    if args.command == "convert":
        run_dir = convert_run(
            args.run_dir,
            config_path=args.config,
            alpha_policy=args.alpha_policy,
            mask_override=args.mask_override,
            background_method=args.background_method,
            background_model=args.background_model,
            square_output=args.square_output,
        )
        print(run_dir)
        return
    parser.error(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()

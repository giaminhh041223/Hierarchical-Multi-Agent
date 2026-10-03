"""Small, explicit provider adapters. Secrets stay in memory; no shell evaluation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
from urllib import error, parse, request


class AdapterError(RuntimeError):
    """A displayable error which contains no upstream response or credential."""


def _command(name: str) -> list[str] | None:
    path = shutil.which(name)
    if not path:
        return None
    candidate = Path(path)
    if os.name != "nt" or candidate.suffix.lower() == ".exe":
        return [str(candidate)]
    # Windows npm shims invoke a shell. Resolve only known package entry points.
    if name == "codex":
        binaries = sorted((candidate.parent / "node_modules/@openai/codex/node_modules/@openai").glob("codex-win32-*/vendor/*/bin/codex.exe"))
        if binaries:
            return [str(binaries[0])]
        script = candidate.parent / "node_modules/@openai/codex/bin/codex.js"
        node = shutil.which("node")
        if node and script.is_file():
            return [node, str(script)]
    if name == "opencode":
        binary = candidate.parent / "node_modules/opencode-ai/bin/opencode.exe"
        if binary.is_file():
            return [str(binary)]
    return None


def _stop(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        killer = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/taskkill.exe"
        try:
            subprocess.run([str(killer), "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=10)


def _run(args: list[str], cwd: Path | None = None, stdin: str = "", timeout: int = 180,
         cancel_event: threading.Event | None = None) -> str:
    if cancel_event and cancel_event.is_set():
        raise AdapterError("Tác vụ đã hủy.")
    # Cached CLI login is used by the CLI itself; API keys are not forwarded.
    env = {k: v for k, v in os.environ.items()
           if not any(part in k.upper() for part in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    try:
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace", **options)
    except OSError:
        raise AdapterError("Không thể khởi động CLI. Kiểm tra cài đặt của provider.") from None
    deadline, initial = time.monotonic() + timeout, True
    try:
        while True:
            if cancel_event and cancel_event.is_set():
                raise AdapterError("Tác vụ đã hủy.")
            if time.monotonic() >= deadline:
                raise AdapterError("CLI quá thời gian; worker đã được dừng.")
            try:
                stdout, _ = proc.communicate(input=stdin if initial else None, timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                initial = False
        if proc.returncode:
            raise AdapterError("CLI không hoàn tất. Kiểm tra đăng nhập, quyền model hoặc quota trong client chính thức.")
        if len(stdout) > 4_000_000:
            raise AdapterError("Phản hồi CLI quá lớn.")
        return stdout
    finally:
        if proc.poll() is None:
            _stop(proc)
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe:
                pipe.close()


def discover() -> list[dict]:
    """Inspect CLI paths, versions and Antigravity's public model catalog only."""
    result = []
    for provider, name, login in (("codex", "codex", "codex login"),
                                  ("opencode", "opencode", "opencode auth login"),
                                  ("antigravity", "agy", "agy")):
        command = _command(name)
        item = {"id": provider, "name": provider.title(), "installed": bool(command),
                "path": command[0] if command else None, "version": None, "auth": "unknown",
                "login_command": login, "models": [],
                "note": "Phát hiện CLI không chứng minh tài khoản/quota/model dùng được.",
                "executable": provider == "codex" and bool(command)}
        if command:
            try:
                output = _run(command + ["--version"], timeout=10)
                version = re.search(r"\b\d+\.\d+\.\d+(?:[-+][\w.-]+)?\b", output)
                item["version"] = version.group() if version else "unknown"
                if provider == "antigravity":
                    lines = _run(command + ["models"], timeout=15).splitlines()
                    item["models"] = [line.split("\t")[0] for line in lines
                                      if "\t" in line and re.fullmatch(r"[a-zA-Z0-9][\w./:-]{0,199}", line.split("\t")[0])]
            except AdapterError:
                item["note"] = "Tìm thấy CLI; version hoặc model discovery chưa hoàn tất. Auth chưa xác minh."
        if provider in ("opencode", "antigravity"):
            item["note"] += " v0.1 chỉ discovery; cần adapter cô lập quyền trước khi chạy tự động."
        result.append(item)
    return result


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AdapterError("Provider trả redirect; hãy cấu hình endpoint trực tiếp.")


def _endpoint(base: str, suffix: str) -> str:
    try:
        url = parse.urlsplit(base)
        valid = (url.scheme == "https" or (url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")))
        if not valid or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError
        if any(ord(c) < 33 for c in base):
            raise ValueError
    except ValueError:
        raise AdapterError("Endpoint cần HTTPS (HTTP chỉ cho localhost), không chứa tài khoản/query/fragment.") from None
    return base.rstrip("/") + suffix


def _post(url: str, body: dict, headers: dict) -> dict:
    req = request.Request(url, data=json.dumps(body).encode("utf-8"),
                          headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        # Do not forward credentials to redirect destinations or implicit proxies.
        opener = request.build_opener(request.ProxyHandler({}), _NoRedirect())
        with opener.open(req, timeout=60) as response:
            raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise AdapterError("Phản hồi API quá lớn.")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError
        return data
    except error.HTTPError as exc:
        raise AdapterError(f"API trả HTTP {exc.code}; kiểm tra key, model, quota và endpoint.") from None
    except (error.URLError, OSError, ValueError):
        raise AdapterError("Không nhận được JSON hợp lệ từ API; kiểm tra kết nối và endpoint.") from None


def _result(text: str, usage: dict, input_field: str, output_field: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise AdapterError("Provider không trả nội dung văn bản hoàn tất.")
    usage = usage if isinstance(usage, dict) else {}
    def count(field):
        value = usage.get(field)
        return value if type(value) is int and value >= 0 else None
    incoming, outgoing = count(input_field), count(output_field)
    return {"text": text, "input_tokens": incoming, "output_tokens": outgoing,
            "usage_source": "provider" if incoming is not None or outgoing is not None else "unknown"}


def execute(provider: str, model: str, prompt: str, workspace: Path, key: str = "",
            base_url: str = "", max_output_tokens: int = 2000,
            cancel_event: threading.Event | None = None) -> dict:
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", model):
        raise AdapterError("Chọn model ID hợp lệ từ provider.")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 500_000:
        raise AdapterError("Prompt trống hoặc quá lớn.")
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 100_000:
        raise AdapterError("Giới hạn output phải trong 1–100000 token.")
    if cancel_event and cancel_event.is_set():
        raise AdapterError("Tác vụ đã hủy.")
    try:
        workspace = Path(workspace).resolve(strict=True)
    except (OSError, ValueError, TypeError):
        raise AdapterError("Workspace không hợp lệ.") from None
    if not workspace.is_dir():
        raise AdapterError("Workspace không hợp lệ.")
    if provider in ("antigravity", "opencode"):
        raise AdapterError("CLI này đã hỗ trợ headless nhưng adapter v0.1 chỉ discovery; cần cấu hình worker cô lập quyền trước khi chạy.")
    if provider == "codex":
        command = _command("codex")
        if not command:
            raise AdapterError("Chưa tìm thấy Codex CLI có thể chạy trực tiếp.")
        raw = _run(command + ["exec", "--json", "--sandbox", "workspace-write", "--ignore-user-config",
                   "-c", 'approval_policy="never"', "--skip-git-repo-check", "-C", str(workspace),
                   "--model", model, "-"], cwd=workspace, stdin=prompt, cancel_event=cancel_event)
        messages, usage, completed = [], {}, False
        for line in raw.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") in ("error", "turn.failed"):
                raise AdapterError("Codex báo lỗi tác vụ; xem đăng nhập/model/quota trong client.")
            item = event.get("item") or {}
            if not isinstance(item, dict):
                raise AdapterError("Codex trả event sai định dạng.")
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
            if event.get("type") == "turn.completed":
                completed, usage = True, event.get("usage") or {}
        if not completed:
            raise AdapterError("Codex chưa xác nhận turn.completed.")
        if cancel_event and cancel_event.is_set():
            raise AdapterError("Tác vụ đã hủy.")
        if not all(isinstance(message, str) for message in messages):
            raise AdapterError("Codex trả message sai định dạng.")
        return _result("\n".join(messages), usage, "input_tokens", "output_tokens")
    if not isinstance(key, str) or not key or any(ord(c) < 32 for c in key):
        raise AdapterError("Provider API cần key hợp lệ; nhập ở vùng credentials.")
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_output_tokens}
    if provider == "openai_compatible":
        url = _endpoint(base_url or "https://api.openai.com/v1", "/chat/completions")
        data = _post(url, body, {"Authorization": "Bearer " + key})
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") in ("length", "content_filter", "tool_calls"):
                raise AdapterError("API chưa trả kết quả văn bản hoàn tất (giới hạn token hoặc tool call).")
            result = _result(choice["message"]["content"], data.get("usage") or {}, "prompt_tokens", "completion_tokens")
        except (KeyError, IndexError, TypeError):
            raise AdapterError("API không trả định dạng Chat Completions mong đợi.") from None
    elif provider == "anthropic":
        data = _post(_endpoint(base_url or "https://api.anthropic.com/v1", "/messages"), body,
                     {"x-api-key": key, "anthropic-version": "2023-06-01"})
        if data.get("stop_reason") not in ("end_turn", "stop_sequence"):
            raise AdapterError("Anthropic chưa trả kết quả hoàn tất.")
        result = _result("\n".join(p.get("text", "") for p in data.get("content", []) if p.get("type") == "text"),
                         data.get("usage") or {}, "input_tokens", "output_tokens")
    elif provider == "gemini":
        slug = model.removeprefix("models/")
        url = _endpoint(base_url or "https://generativelanguage.googleapis.com/v1beta", "/models/" + parse.quote(slug, safe="") + ":generateContent")
        data = _post(url, {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                           "generationConfig": {"maxOutputTokens": max_output_tokens}}, {"x-goog-api-key": key})
        candidates = data.get("candidates") or []
        if not candidates or candidates[0].get("finishReason") != "STOP":
            raise AdapterError("Gemini chưa trả kết quả hoàn tất.")
        parts = candidates[0].get("content", {}).get("parts", [])
        result = _result("\n".join(p.get("text", "") for p in parts if not p.get("thought")),
                         data.get("usageMetadata") or {}, "promptTokenCount", "candidatesTokenCount")
    else:
        raise AdapterError("Provider chưa được hỗ trợ.")
    if cancel_event and cancel_event.is_set():
        raise AdapterError("Tác vụ đã hủy; phản hồi đang truyền đã bị bỏ qua.")
    return result

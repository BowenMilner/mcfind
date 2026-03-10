from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue
from urllib.error import URLError
from urllib.request import urlopen


_CLOUDFLARE_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


class McfindChatgptError(RuntimeError):
    pass


@dataclass
class _Forwarder:
    name: str
    process: subprocess.Popen[str]
    queue: Queue[str]
    quiet: bool = False

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._run, name=f"{self.name}-forwarder", daemon=True)
        thread.start()
        return thread

    def _run(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            line = line.rstrip("\n")
            self.queue.put(line)
            if not self.quiet:
                print(f"[{self.name}] {line}", flush=True)


def _extract_cloudflare_url(line: str) -> str | None:
    match = _CLOUDFLARE_URL_RE.search(line)
    return match.group(0) if match else None


def _wait_for_health(url: str, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    last_error: str | None = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
                last_error = f"unexpected status {response.status}"
        except URLError as exc:
            last_error = str(exc.reason)
        time.sleep(0.25)
    raise McfindChatgptError(f"MCP server did not become healthy at {url}: {last_error or 'timed out'}")


def _wait_for_cloudflare_url(
    process: subprocess.Popen[str],
    queue: Queue[str],
    timeout_seconds: float,
) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            raise McfindChatgptError(f"cloudflared exited with status {process.returncode}")
        try:
            line = queue.get(timeout=0.25)
        except Empty:
            continue
        url = _extract_cloudflare_url(line)
        if url:
            return url
    raise McfindChatgptError("Timed out waiting for cloudflared to report a public URL")


def _terminate_process(process: subprocess.Popen[str] | None, name: str) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    print(f"Stopped {name}.", flush=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcfind-chatgpt",
        description="Start mcfind MCP plus a Cloudflare quick tunnel for ChatGPT developer-mode testing.",
    )
    parser.add_argument("--port", type=int, default=8001, help="Local MCP port to bind. Default: 8001.")
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Local MCP host to bind. Default: 0.0.0.0.",
    )
    parser.add_argument(
        "--cloudflared-bin",
        default="cloudflared",
        help="Path to the cloudflared executable. Default: cloudflared.",
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for the local MCP server health check. Default: 15.",
    )
    parser.add_argument(
        "--tunnel-timeout",
        type=float,
        default=20.0,
        help="Seconds to wait for cloudflared to print a public URL. Default: 20.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress child process logs and print only the startup summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    cloudflared_path = shutil.which(args.cloudflared_bin)
    if not cloudflared_path:
        raise SystemExit(
            f'cloudflared not found: "{args.cloudflared_bin}". Install it or pass --cloudflared-bin /path/to/cloudflared.'
        )

    env = os.environ.copy()
    env["MCFIND_MCP_HOST"] = args.host
    env["MCFIND_MCP_PORT"] = str(args.port)
    env["MCFIND_MCP_DISABLE_DNS_REBINDING_PROTECTION"] = "1"

    local_base_url = f"http://127.0.0.1:{args.port}"
    health_url = f"{local_base_url}/health"

    mcp_process: subprocess.Popen[str] | None = None
    cloudflared_process: subprocess.Popen[str] | None = None
    try:
        mcp_process = subprocess.Popen(
            [sys.executable, "-u", "-m", "mcfind.mcp_server"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _Forwarder("mcfind-mcp", mcp_process, Queue[str](), quiet=args.quiet).start()
        _wait_for_health(health_url, args.health_timeout)

        cloudflared_queue: Queue[str] = Queue()
        cloudflared_process = subprocess.Popen(
            [cloudflared_path, "tunnel", "--url", local_base_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _Forwarder("cloudflared", cloudflared_process, cloudflared_queue, quiet=args.quiet).start()
        public_base_url = _wait_for_cloudflare_url(cloudflared_process, cloudflared_queue, args.tunnel_timeout)

        print("", flush=True)
        print("mcfind ChatGPT connector is running.", flush=True)
        print(f"Local health:  {health_url}", flush=True)
        print(f"Local MCP:     {local_base_url}/mcp", flush=True)
        print(f"Public health: {public_base_url}/health", flush=True)
        print(f"Public MCP:    {public_base_url}/mcp", flush=True)
        print("Use the public /mcp URL as the ChatGPT connector URL.", flush=True)
        print("Press Ctrl-C to stop both processes.", flush=True)

        while True:
            if mcp_process.poll() is not None:
                raise McfindChatgptError(f"mcfind-mcp exited with status {mcp_process.returncode}")
            if cloudflared_process.poll() is not None:
                raise McfindChatgptError(f"cloudflared exited with status {cloudflared_process.returncode}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("", flush=True)
        print("Stopping mcfind ChatGPT connector...", flush=True)
        return 130
    except McfindChatgptError as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        _terminate_process(cloudflared_process, "cloudflared")
        _terminate_process(mcp_process, "mcfind-mcp")


if __name__ == "__main__":
    raise SystemExit(main())

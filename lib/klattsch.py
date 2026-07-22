"""Persistent-bridge wrapper around the klattsch JS synth.

Spawns one node process running klattsch_bridge.mjs and feeds it
line-delimited JSON requests. Renders Float32 samples come back base64-encoded.
"""
import base64
import json
import os
import subprocess
import threading
from pathlib import Path

import numpy as np

_DEFAULT_BRIDGE = Path(__file__).resolve().parent.parent / "klattsch_bridge.mjs"


class KlattschBridge:
    def __init__(self, bridge_js: str | os.PathLike = _DEFAULT_BRIDGE,
                 node_bin: str = "node"):
        self.bridge_js = Path(bridge_js)
        self._proc = subprocess.Popen(
            [node_bin, str(self.bridge_js)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(self.bridge_js.parent),
        )
        self._lock = threading.Lock()
        self._next_id = 1
        ready = self._read_one()
        if not ready.get("ready"):
            raise RuntimeError(f"klattsch bridge did not signal ready: {ready}")

    def _read_one(self) -> dict:
        line = self._proc.stdout.readline()
        if not line:
            stderr = self._proc.stderr.read().decode("utf-8", "replace")
            raise RuntimeError(f"klattsch bridge died. stderr:\n{stderr}")
        return json.loads(line)

    def _request(self, req: dict) -> dict:
        with self._lock:
            req["id"] = self._next_id
            self._next_id += 1
            self._proc.stdin.write((json.dumps(req) + "\n").encode("utf-8"))
            self._proc.stdin.flush()
            resp = self._read_one()
        if not resp.get("ok"):
            raise RuntimeError(f"klattsch error: {resp.get('error')}")
        return resp

    @staticmethod
    def _decode(resp: dict) -> tuple[np.ndarray, int]:
        b = base64.b64decode(resp["samples_b64"])
        samples = np.frombuffer(b, dtype=np.float32).copy()
        return samples, int(resp["sampleRate"])

    def render_text(self, text: str, sample_rate: int = 48000) -> tuple[np.ndarray, int, list[str]]:
        """Compile a phoneme string and render. Returns (samples, sr, warnings)."""
        resp = self._request({"mode": "compile", "text": text, "sampleRate": sample_rate})
        samples, sr = self._decode(resp)
        return samples, sr, resp.get("warnings", [])

    def compile_schedule(self, text: str) -> tuple[list[dict], float, list[str]]:
        """Compile a phoneme string to a klattsch schedule, no rendering.

        Returns: (schedule, total_ms, warnings).
        """
        resp = self._request({"mode": "schedule", "text": text})
        return resp["schedule"], float(resp["totalMs"]), resp.get("warnings", [])

    def render_schedule(self, schedule: list[dict], dur_ms: float,
                        sample_rate: int = 48000,
                        initial_target: dict | None = None) -> tuple[np.ndarray, int]:
        """Render a raw schedule. schedule items: {atMs, target, transitionMs}."""
        req = {"mode": "raw", "schedule": schedule, "durMs": float(dur_ms),
               "sampleRate": sample_rate}
        if initial_target is not None:
            req["initialTarget"] = initial_target
        resp = self._request(req)
        return self._decode(resp)

    def close(self):
        if self._proc.poll() is None:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

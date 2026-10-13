"""Real local HTTP timing with the server's outbound sockets/DNS blocked.

Run after installing dependencies: python tools/verify_service.py
Does not change network adapters, catalogue data, or the normal demo server.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import http.client
import json
import math
from pathlib import Path
import platform
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def guarded_server(port):
    import uvicorn
    from parttrace.api import app

    original_connect, original_pair = socket.socket.connect, socket.socketpair
    internal = threading.local()

    def blocked(*args, **kwargs):
        print("BLOCKED_OUTBOUND", file=sys.stderr, flush=True)
        raise AssertionError("Verification server must not make outbound network calls")

    def connect(sock, address):
        if getattr(internal, "pair", False) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        return blocked()

    def pair(*args, **kwargs):
        internal.pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            internal.pair = False

    socket.socket.connect = connect
    socket.socket.connect_ex = blocked
    socket.socketpair = pair
    socket.create_connection = blocked
    socket.getaddrinfo = blocked
    uvicorn.run(app, host="127.0.0.1", port=port, lifespan="on", log_level="warning", access_log=False)


def request(port, path, expected=200):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    start = time.perf_counter()
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
        elapsed = time.perf_counter() - start
        assert response.status == expected, (path, response.status, body[:200])
        return elapsed, body
    finally:
        connection.close()


def stats(samples):
    ordered = sorted(samples)
    return {"requests": len(samples), "median_ms": round(ordered[len(ordered) // 2] * 1000, 3),
            "p95_ms": round(ordered[math.ceil(len(ordered) * .95) - 1] * 1000, 3),
            "max_ms": round(max(ordered) * 1000, 3)}


def verify(output):
    from parttrace import Catalogue

    start = time.perf_counter()
    catalogue = Catalogue.from_directory()
    build_seconds = time.perf_counter() - start
    # Use the public part query to enumerate the rooted catalogue.
    pending, members = [catalogue.root], set()
    while pending:
        part = pending.pop()
        if part in members:
            continue
        members.add(part)
        pending.extend(c["part_number"] for c in catalogue.part(part)["children"])
    path_counts = {p: len(catalogue.paths(p)["paths"]) for p in members}
    heaviest = max(sorted(members), key=path_counts.get)
    serials = {0, 2500}
    with (ROOT / "data" / "service_parts.csv").open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            for field in ("serial_from", "serial_to"):
                if row[field].strip().isdigit():
                    bound = int(row[field])
                    serials.update(max(0, bound + offset) for offset in (-1, 0, 1))
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    log_path = ROOT / "tmp" / "phase5-guarded-server.log"
    log_path.parent.mkdir(exist_ok=True)
    samples = {name: [] for name in ("health", "validation", "part", "paths", "serial", "demo_assets", "errors")}
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--server", str(port)],
                                   cwd=ROOT, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Verification server exited; inspect " + str(log_path))
                try:
                    _, body = request(port, "/health")
                    assert json.loads(body) == {"status": "ok"}
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Server did not become ready")
                    time.sleep(.1)
            for name, path in (("health", "/health"), ("validation", "/api/validation")):
                for _ in range(30):
                    elapsed, body = request(port, path)
                    samples[name].append(elapsed)
                    expected = {"status": "ok"} if name == "health" else catalogue.validation()
                    assert json.loads(body) == expected
            for part in sorted(members):
                for name, suffix, expected in (("part", "", catalogue.part(part)),
                                               ("paths", "/paths", catalogue.paths(part))):
                    elapsed, body = request(port, f"/api/parts/{part.lower()}{suffix}")
                    samples[name].append(elapsed)
                    assert json.loads(body) == expected
            for serial in sorted(serials):
                for _ in range(5):
                    elapsed, body = request(port, f"/api/serial/{serial}")
                    samples["serial"].append(elapsed)
                    assert json.loads(body) == catalogue.serial(serial)
            for path in ("/", "/static/app.js", "/static/style.css", "/demo/search?q=washer",
                         "/demo/quality", f"/demo/parts/{heaviest}/explanation?serial=2500"):
                elapsed, body = request(port, path)
                samples["demo_assets"].append(elapsed)
                assert body
            for path, status in (("/api/parts/OUTSIDE-TEST", 404), ("/api/parts/OUTSIDE-TEST/paths", 404),
                                 ("/api/serial/2.5", 422)):
                elapsed, _ = request(port, path, status)
                samples["errors"].append(elapsed)
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda _: request(port, f"/api/parts/{heaviest}/paths"), range(64)))
            samples["concurrent_paths_8_workers"] = [elapsed for elapsed, _ in results]
            for _, body in results:
                assert json.loads(body) == catalogue.paths(heaviest)
        finally:
            process.terminate()  # Only the child server created by this script.
            process.wait(timeout=10)
    assert "BLOCKED_OUTBOUND" not in log_path.read_text(encoding="utf-8")
    result = {"platform": platform.platform(), "python": platform.python_version(),
              "catalogue_load_ms": round(build_seconds * 1000, 3), "parts_checked": len(members),
              "largest_path_result": {"part": heaviest, "paths": path_counts[heaviest]},
              "serials_checked": sorted(serials), "timings": {name: stats(values) for name, values in samples.items()},
              "all_observed_requests_under_one_second": all(t < 1 for v in samples.values() for t in v),
              "server_outbound_connections_and_dns_blocked": True,
              "blocked_outbound_attempts": 0, "network_adapter_disabled": False,
              "limits": "Local measurements, supplied export, warm OS caches; not a guarantee for arbitrary graphs/hardware. Client timings include TCP connection and full body read. Imports precede the guard; catalogue startup and all requests run under it."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    assert result["all_observed_requests_under_one_second"], "A measured request exceeded the budget"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, default=ROOT / "audit" / "phase5-performance.json")
    arguments = parser.parse_args()
    if arguments.server:
        guarded_server(arguments.server)
    else:
        verify(arguments.output)

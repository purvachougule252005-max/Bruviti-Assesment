import csv
import socket
import threading

import pytest


HEADERS = {
    "bom.csv": ("parent_pn", "child_pn", "quantity"),
    "parts_master.csv": ("part_number", "revision", "description", "category", "unit_cost"),
    "service_parts.csv": ("part_number", "field_replaceable", "serial_from", "serial_to"),
}


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    original_connect = socket.socket.connect
    original_pair = socket.socketpair
    internal = threading.local()

    def blocked(*args, **kwargs):
        raise AssertionError("Tests must not open a network connection")

    def connect(sock, address):
        # Windows implements socketpair with a loopback connection. Permit
        # only that call, on the thread creating the pair; app calls still fail.
        if getattr(internal, "creating_pair", False) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        return blocked(sock, address)

    def socketpair(*args, **kwargs):
        internal.creating_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            internal.creating_pair = False

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "socketpair", socketpair)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.fixture
def export(tmp_path):
    """Write small source fixtures. Short master/service tuples get neutral defaults."""
    def write(bom=(), master=(), service=()):
        tables = {
            "bom.csv": list(bom),
            "parts_master.csv": [tuple(r) + ("Test", "1.00") if len(r) == 3 else r for r in master],
            "service_parts.csv": [tuple(r) + ("", "") if len(r) == 2 else r for r in service],
        }
        for name, rows in tables.items():
            with (tmp_path / name).open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(HEADERS[name])
                writer.writerows(rows)
        return tmp_path
    return write

"""The Windows async-loop exception must not permit app connections."""

import socket

import pytest


@pytest.mark.parametrize("address", [("127.0.0.1", 8000), ("192.0.2.1", 443)])
def test_application_socket_connections_stay_blocked(address):
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="must not open a network connection"):
            connection.connect(address)


def test_internal_socketpair_is_allowed_without_leaving_guard_disabled():
    left, right = socket.socketpair()
    try:
        left.sendall(b"ok")
        assert right.recv(2) == b"ok"
    finally:
        left.close()
        right.close()
    with pytest.raises(AssertionError, match="must not open a network connection"):
        socket.create_connection(("127.0.0.1", 8000))

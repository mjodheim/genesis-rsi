"""Run the independent diagnostic without asserting historical SHA outcomes."""
from __future__ import annotations

import socket

import diagnose_citation_membership as diagnostic

def test_diagnose_citation_membership(
    monkeypatch, capsys, request, record_property
) -> None:
    def offline(*args, **kwargs):
        raise AssertionError("Network access is forbidden in this diagnostic")

    monkeypatch.setattr(socket, "create_connection", offline)
    monkeypatch.setattr(socket, "getaddrinfo", offline)
    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(socket.socket, "connect_ex", offline)

    try:
        assert diagnostic.main() == 0
    finally:
        captured = capsys.readouterr()
        output = captured.out + captured.err
        request.node.add_report_section("call", "citation diagnostic", output)
        record_property("citation_membership_diagnostic", output)
        with capsys.disabled():
            print(output, end="")

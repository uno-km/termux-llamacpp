import os
import sys
from unittest.mock import patch, MagicMock
import pytest

from termux_llamacpp.cluster import (
    parse_cluster_rpc_spec,
    resolve_auto_tensor_split,
    verify_rpc_cluster_nodes,
    ensure_wakelock,
    check_cluster_license,
    setup_cluster_guard_tunnels,
)
from termux_llamacpp.exceptions import (
    ClusterConnectionError,
    ClusterConfigurationError,
    ClusterLicenseRequiredError,
)
from termux_llamacpp.engine import LlamaRuntime


def test_parse_cluster_rpc_spec():
    assert parse_cluster_rpc_spec(None) == []
    assert parse_cluster_rpc_spec("") == []

    parsed = parse_cluster_rpc_spec("192.0.2.10:50052, 192.0.2.11:50052")
    assert parsed == ["192.0.2.10:50052", "192.0.2.11:50052"]

    with pytest.raises(ClusterConfigurationError):
        parse_cluster_rpc_spec("invalid_host_no_port")

    with pytest.raises(ClusterConfigurationError):
        parse_cluster_rpc_spec("127.0.0.1:99999")


def test_verify_rpc_cluster_nodes_failfast():
    # Should raise ClusterConnectionError if host is unreachable
    with pytest.raises(ClusterConnectionError):
        verify_rpc_cluster_nodes(["127.0.0.1:54321"], timeout=0.1)


def test_check_cluster_license_without_package():
    # When ameva_cluster is not importable, ClusterLicenseRequiredError must be raised
    with pytest.raises(ClusterLicenseRequiredError) as exc_info:
        check_cluster_license()
    assert "E403" in str(exc_info.value)
    assert "pip install ameva-cluster" in str(exc_info.value)


def test_check_cluster_license_with_invalid_token():
    mock_guard = MagicMock()
    mock_guard.verify_cluster_license.return_value = False
    with patch.dict(sys.modules, {"ameva_cluster.guard": mock_guard}):
        with pytest.raises(ClusterLicenseRequiredError) as exc_info:
            check_cluster_license("INVALID_KEY")
        assert "E403" in str(exc_info.value)


def test_resolve_auto_tensor_split():
    mock_orch = MagicMock()
    mock_orch.resolve_auto_tensor_split.return_value = (["192.0.2.10:50052", "192.0.2.11:50052"], "38,33,29")
    with patch.dict(sys.modules, {"termux_ai_orchestrator.auto_split": mock_orch}):
        servers, ts = resolve_auto_tensor_split("192.0.2.10:50052,192.0.2.11:50052", "auto")
        assert servers == ["192.0.2.10:50052", "192.0.2.11:50052"]
        assert ts == "38,33,29"

    # Static split is untouched
    servers, ts = resolve_auto_tensor_split("192.0.2.10:50052", "50,50")
    assert ts == "50,50"


def test_engine_generate_rpc_without_license_fails(tmp_path):
    dummy_model = tmp_path / "dummy.gguf"
    dummy_model.write_text("gguf")

    runtime = LlamaRuntime()
    runtime.models.resolve_model_path = MagicMock(return_value=dummy_model)
    runtime.get_binary_path = MagicMock(return_value="/bin/llama-cli")

    with pytest.raises(ClusterLicenseRequiredError):
        runtime.generate(
            model=str(dummy_model),
            prompt="Hello",
            rpc="192.0.2.10:50052,192.0.2.11:50052",
        )


def test_engine_generate_rpc_with_license_and_tunnels(tmp_path):
    dummy_model = tmp_path / "dummy.gguf"
    dummy_model.write_text("gguf")

    runtime = LlamaRuntime()
    runtime.models.resolve_model_path = MagicMock(return_value=dummy_model)
    runtime.get_binary_path = MagicMock(return_value="/bin/llama-cli")

    mock_tunnel = MagicMock()
    mock_tunnel.local_port = 51052

    with patch("termux_llamacpp.engine.resolve_device_backend", return_value=("cpu", 0)), \
         patch("termux_llamacpp.cluster.check_cluster_license"), \
         patch("termux_llamacpp.cluster.verify_rpc_cluster_nodes"), \
         patch("termux_llamacpp.cluster.setup_cluster_guard_tunnels", return_value=(["127.0.0.1:51052"], [mock_tunnel])), \
         patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Assistant: Hello from distributed Llama!\n"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        res = runtime.generate(
            model=str(dummy_model),
            prompt="Hello",
            rpc="192.0.2.10:50052",
            tensor_split="50,50",
        )

        assert mock_run.call_count == 1
        cmd_args = mock_run.call_args[0][0]
        assert "--rpc" in cmd_args
        rpc_idx = cmd_args.index("--rpc")
        # Confirms loopback tunnel endpoint replacement
        assert cmd_args[rpc_idx + 1] == "127.0.0.1:51052"
        assert "--tensor-split" in cmd_args
        # Confirms tunnel teardown on completion
        assert mock_tunnel.stop.call_count == 1


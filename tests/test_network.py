"""Testes unitários para o módulo de diagnóstico de rede."""

from sysdiag.core.logger import DiagnosticLogger
from sysdiag.diagnostics.network import NetworkDiagnostic


class TestNetworkDiagnostic:
    """Testes para a classe NetworkDiagnostic."""

    def setup_method(self):
        """Configura o ambiente para cada teste."""
        self.logger = DiagnosticLogger(output_dir="/tmp/sysdiag_test")
        self.net = NetworkDiagnostic(self.logger)

    def test_init(self):
        """Deve inicializar com logger e SO detectado."""
        assert self.net.logger is self.logger
        assert self.net.os_name in ("windows", "linux", "darwin")
        assert self.net.MODULE == "rede"

    def test_ping_localhost(self):
        """Ping para localhost deve funcionar."""
        result = self.net.ping(host="127.0.0.1", count=1, timeout=10)
        assert result.success is True
        assert result.return_code == 0

    def test_ping_registers_log(self):
        """Ping deve registrar entrada no logger."""
        self.net.ping(host="127.0.0.1", count=1, timeout=10)
        entries = self.logger.get_entries(module="rede")
        assert len(entries) > 0
        ping_entries = [e for e in entries if e.action == "ping"]
        assert len(ping_entries) > 0

    def test_dns_resolve_python(self):
        """Resolução DNS via Python deve retornar dicionário."""
        result = self.net.dns_resolve_python("localhost")
        assert isinstance(result, dict)
        assert "hostname" in result
        assert "addresses" in result

    def test_check_port_closed(self):
        """Verificação de porta fechada deve retornar False."""
        # Porta improvável de estar aberta
        result = self.net.check_port("127.0.0.1", 59999, timeout=2)
        assert result is False

    def test_get_interfaces(self):
        """Coleta de interfaces deve retornar CommandResult."""
        result = self.net.get_interfaces(timeout=10)
        assert hasattr(result, "success")
        assert hasattr(result, "stdout")

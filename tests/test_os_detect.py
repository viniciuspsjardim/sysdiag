"""Testes unitários para o módulo de detecção de SO."""

import platform
from unittest.mock import patch

from sysdiag.core.os_detect import (
    detect_os,
    get_os_version,
    get_architecture,
    get_hostname,
    get_display_name,
    get_system_info,
    print_system_info,
    SystemInfo,
)


class TestDetectOS:
    """Testes para a função detect_os."""

    def test_returns_string(self):
        """Deve retornar uma string."""
        result = detect_os()
        assert isinstance(result, str)

    def test_returns_lowercase(self):
        """Deve retornar o nome do SO em minúsculas."""
        result = detect_os()
        assert result == result.lower()

    def test_returns_known_os(self):
        """Deve retornar um dos SOs suportados."""
        result = detect_os()
        assert result in ("windows", "linux", "darwin")

    @patch("platform.system", return_value="Windows")
    def test_detect_windows(self, mock_system):
        """Deve detectar Windows corretamente."""
        assert detect_os() == "windows"

    @patch("platform.system", return_value="Linux")
    def test_detect_linux(self, mock_system):
        """Deve detectar Linux corretamente."""
        assert detect_os() == "linux"

    @patch("platform.system", return_value="Darwin")
    def test_detect_macos(self, mock_system):
        """Deve detectar macOS corretamente."""
        assert detect_os() == "darwin"


class TestGetOSVersion:
    """Testes para a função get_os_version."""

    def test_returns_string(self):
        """Deve retornar uma string não vazia."""
        result = get_os_version()
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("sysdiag.core.os_detect.detect_os", return_value="windows")
    @patch("platform.version", return_value="10.0.19041")
    @patch("platform.release", return_value="10")
    def test_windows_version_format(self, mock_release, mock_version, mock_os):
        """Deve formatar versão do Windows corretamente."""
        result = get_os_version()
        assert "Windows" in result
        assert "10" in result

    @patch("sysdiag.core.os_detect.detect_os", return_value="linux")
    @patch("platform.release", return_value="5.15.0-generic")
    def test_linux_version_format(self, mock_release, mock_os):
        """Deve formatar versão do Linux corretamente."""
        result = get_os_version()
        assert "Linux" in result
        assert "kernel" in result


class TestGetArchitecture:
    """Testes para a função get_architecture."""

    def test_returns_string(self):
        """Deve retornar uma string não vazia."""
        result = get_architecture()
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetHostname:
    """Testes para a função get_hostname."""

    def test_returns_string(self):
        """Deve retornar uma string não vazia."""
        result = get_hostname()
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetSystemInfo:
    """Testes para a função get_system_info."""

    def test_returns_system_info(self):
        """Deve retornar um objeto SystemInfo."""
        result = get_system_info()
        assert isinstance(result, SystemInfo)

    def test_all_fields_populated(self):
        """Todos os campos obrigatórios devem estar preenchidos."""
        result = get_system_info()
        assert result.os_name
        assert result.os_display
        assert result.version
        assert result.architecture
        assert result.hostname
        assert result.python_version
        assert isinstance(result.is_elevated, bool)
        assert isinstance(result.extra, dict)


class TestPrintSystemInfo:
    """Testes para a função print_system_info."""

    def test_returns_formatted_string(self):
        """Deve retornar string formatada com separadores."""
        result = print_system_info()
        assert "INFORMAÇÕES DO SISTEMA" in result
        assert "=" * 50 in result

    def test_accepts_system_info(self):
        """Deve aceitar um SystemInfo pré-criado."""
        info = SystemInfo(
            os_name="linux",
            os_display="Ubuntu 22.04",
            version="Linux (kernel 5.15)",
            architecture="x86_64",
            hostname="test-host",
            python_version="3.11.0",
            is_elevated=False,
            extra={"platform": "Linux-5.15"},
        )
        result = print_system_info(info)
        assert "Ubuntu 22.04" in result
        assert "test-host" in result

"""Testes unitários para o módulo de execução de comandos."""

from unittest.mock import patch, MagicMock

from sysdiag.core.executor import (
    run_command,
    run_platform_command,
    get_platform_command,
    is_command_available,
    CommandResult,
    PLATFORM_COMMANDS,
)


class TestRunCommand:
    """Testes para a função run_command."""

    def test_successful_command(self):
        """Deve executar um comando simples com sucesso."""
        result = run_command(["python", "--version"])
        assert isinstance(result, CommandResult)
        assert result.success is True
        assert result.return_code == 0
        assert "Python" in result.stdout or "Python" in result.stderr

    def test_failed_command(self):
        """Deve capturar falha em comando inexistente."""
        result = run_command(["comando_inexistente_xyz"])
        assert result.success is False
        assert result.error_type == "not_found"

    def test_command_timeout(self):
        """Deve capturar timeout corretamente."""
        # Comando que demora mais que o timeout
        result = run_command(["python", "-c", "import time; time.sleep(10)"], timeout=1)
        assert result.success is False
        assert result.error_type == "timeout"

    def test_result_has_timestamp(self):
        """Deve incluir timestamp na resposta."""
        result = run_command(["python", "--version"])
        assert result.timestamp
        assert "T" in result.timestamp  # ISO 8601

    def test_result_has_duration(self):
        """Deve medir a duração da execução."""
        result = run_command(["python", "--version"])
        assert result.duration_ms >= 0

    def test_result_has_platform(self):
        """Deve incluir a plataforma na resposta."""
        result = run_command(["python", "--version"])
        assert result.platform in ("windows", "linux", "darwin")

    def test_command_as_list(self):
        """Deve aceitar comando como lista."""
        result = run_command(["python", "-c", "print('hello')"])
        assert result.success is True
        assert "hello" in result.stdout


class TestGetPlatformCommand:
    """Testes para a função get_platform_command."""

    def test_returns_list(self):
        """Deve retornar uma lista de strings."""
        result = get_platform_command("ping")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_unknown_command_raises(self):
        """Deve levantar KeyError para comando desconhecido."""
        try:
            get_platform_command("comando_inexistente")
            assert False, "Deveria ter levantado KeyError"
        except KeyError:
            pass

    def test_extra_args_appended(self):
        """Deve adicionar argumentos extras ao final."""
        result = get_platform_command("ping", extra_args=["google.com"])
        assert "google.com" in result

    def test_all_generic_commands_have_current_platform(self):
        """Todos os comandos genéricos devem ter entrada para a plataforma atual."""
        from sysdiag.core.os_detect import detect_os
        current_os = detect_os()
        for cmd_name, platforms in PLATFORM_COMMANDS.items():
            assert current_os in platforms, f"'{cmd_name}' não tem suporte para '{current_os}'"


class TestRunPlatformCommand:
    """Testes para a função run_platform_command."""

    def test_unsupported_command(self):
        """Deve retornar erro para comando não mapeado."""
        result = run_platform_command("comando_fake_xyz")
        assert result.success is False
        assert result.error_type == "unsupported"

    def test_ping_command(self):
        """Deve executar ping via mapeamento de plataforma."""
        result = run_platform_command("ping", extra_args=["127.0.0.1"], timeout=15)
        assert isinstance(result, CommandResult)
        # Ping para localhost deve funcionar na maioria dos ambientes
        assert result.command  # Deve ter o comando registrado


class TestIsCommandAvailable:
    """Testes para a função is_command_available."""

    def test_python_available(self):
        """Python deve estar disponível no PATH."""
        assert is_command_available("python") is True

    def test_nonexistent_command(self):
        """Comando inexistente não deve estar no PATH."""
        assert is_command_available("comando_xyz_nao_existe") is False

"""
Módulo de reparos automatizados.

Executa ações de reparo como flush de DNS, liberação de cache,
verificação de disco e reset de rede. Todas as ações destrutivas
requerem confirmação explícita do usuário.
"""

from typing import Callable, Optional

from sysdiag.core.executor import run_platform_command, run_command, CommandResult
from sysdiag.core.logger import DiagnosticLogger
from sysdiag.core.os_detect import detect_os, is_elevated


def _confirm_action(message: str) -> bool:
    """
    Solicita confirmação do usuário antes de executar uma ação de reparo.

    Args:
        message: Descrição da ação a ser confirmada.

    Returns:
        True se o usuário confirmar (s/S/sim/y/yes).
    """
    try:
        response = input(f"\n⚠ {message}\nDeseja continuar? (s/N): ").strip().lower()
        return response in ("s", "sim", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


class RepairModule:
    """
    Classe para reparos automatizados do sistema.

    Todas as ações de reparo são opcionais e requerem confirmação
    do usuário antes de executar. Ativado apenas com a flag --reparar.
    """

    MODULE = "reparo"

    def __init__(self, logger: DiagnosticLogger, auto_confirm: bool = False):
        """
        Inicializa o módulo de reparos.

        Args:
            logger: Instância do DiagnosticLogger para registro.
            auto_confirm: Se True, pula confirmações (uso em testes).
        """
        self.logger = logger
        self.os_name = detect_os()
        self.auto_confirm = auto_confirm

    def _confirm(self, message: str) -> bool:
        """Solicita confirmação, respeitando auto_confirm."""
        if self.auto_confirm:
            return True
        return _confirm_action(message)

    def _require_elevated(self, action_name: str) -> Optional[CommandResult]:
        """
        Verifica se a ação requer privilégios e retorna erro se não os tiver.

        Returns:
            CommandResult com erro se não tiver privilégios, ou None se tiver.
        """
        if not is_elevated():
            msg = (
                f"A ação '{action_name}' requer privilégios elevados. "
                "Execute novamente como Administrador (Windows) ou com sudo (Linux/macOS)."
            )
            self.logger.warning(self.MODULE, action_name, msg)
            return CommandResult(
                command=action_name,
                return_code=-1,
                stdout="",
                stderr=msg,
                success=False,
                timestamp="",
                duration_ms=0,
                error_type="permission_denied",
                platform=self.os_name,
            )
        return None

    def flush_dns(self, timeout: int = 30) -> CommandResult:
        """
        Limpa o cache de DNS do sistema.

        Ação relativamente segura, mas solicita confirmação.

        Returns:
            CommandResult com o resultado da operação.
        """
        if not self._confirm("Limpar cache de DNS (flush DNS)"):
            self.logger.info(self.MODULE, "flush_dns", "Ação cancelada pelo usuário")
            return CommandResult(
                command="flush_dns", return_code=-1, stdout="", stderr="Cancelado pelo usuário",
                success=False, timestamp="", duration_ms=0, platform=self.os_name,
            )

        result = run_platform_command("flush_dns", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "flush_dns", "Cache DNS limpo com sucesso")
        else:
            self.logger.error(self.MODULE, "flush_dns", "Falha ao limpar cache DNS",
                              error_detail=result.stderr)

        return result

    def check_disk(self, timeout: int = 300) -> CommandResult:
        """
        Executa verificação de disco.

        ATENÇÃO: Pode levar vários minutos e requer privilégios elevados.

        Returns:
            CommandResult com o resultado da verificação.
        """
        elevated_check = self._require_elevated("check_disk")
        if elevated_check:
            return elevated_check

        if not self._confirm("Executar verificação de disco (pode levar vários minutos)"):
            self.logger.info(self.MODULE, "check_disk", "Ação cancelada pelo usuário")
            return CommandResult(
                command="check_disk", return_code=-1, stdout="", stderr="Cancelado pelo usuário",
                success=False, timestamp="", duration_ms=0, platform=self.os_name,
            )

        result = run_platform_command("check_disk", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "check_disk", "Verificação de disco concluída")
        else:
            self.logger.warning(self.MODULE, "check_disk", "Verificação de disco com problemas",
                                data={"error": result.stderr})

        return result

    def network_reset(self, timeout: int = 60) -> CommandResult:
        """
        Reseta as configurações de rede.

        ATENÇÃO: Pode desconectar temporariamente da rede.

        Returns:
            CommandResult com o resultado do reset.
        """
        if not self._confirm("Resetar configurações de rede (pode causar desconexão temporária)"):
            self.logger.info(self.MODULE, "network_reset", "Ação cancelada pelo usuário")
            return CommandResult(
                command="network_reset", return_code=-1, stdout="", stderr="Cancelado pelo usuário",
                success=False, timestamp="", duration_ms=0, platform=self.os_name,
            )

        result = run_platform_command("network_reset", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "network_reset", "Reset de rede concluído")
        else:
            self.logger.error(self.MODULE, "network_reset", "Falha no reset de rede",
                              error_detail=result.stderr)

        return result

    def clear_temp_files(self, timeout: int = 60) -> CommandResult:
        """
        Limpa arquivos temporários do sistema.

        Returns:
            CommandResult com o resultado da limpeza.
        """
        if not self._confirm("Limpar arquivos temporários do sistema"):
            self.logger.info(self.MODULE, "clear_temp", "Ação cancelada pelo usuário")
            return CommandResult(
                command="clear_temp", return_code=-1, stdout="", stderr="Cancelado pelo usuário",
                success=False, timestamp="", duration_ms=0, platform=self.os_name,
            )

        if self.os_name == "windows":
            cmd = ["powershell", "-Command",
                   "Remove-Item -Path $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; "
                   "Write-Output 'Arquivos temporários limpos'"]
        elif self.os_name == "linux":
            cmd = ["bash", "-c", "rm -rf /tmp/sysdiag_* 2>/dev/null; echo 'Arquivos temporários limpos'"]
        else:
            cmd = ["bash", "-c", "rm -rf /tmp/sysdiag_* 2>/dev/null; echo 'Arquivos temporários limpos'"]

        result = run_command(cmd, timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "clear_temp", "Arquivos temporários limpos")
        else:
            self.logger.warning(self.MODULE, "clear_temp", "Falha ao limpar temporários",
                                data={"error": result.stderr})

        return result

    def run_all(self) -> dict[str, CommandResult]:
        """
        Executa todos os reparos disponíveis (com confirmação individual).

        Returns:
            Dicionário com os resultados de cada reparo.
        """
        self.logger.info(self.MODULE, "inicio", "Iniciando módulo de reparos")

        results = {
            "flush_dns": self.flush_dns(),
            "clear_temp": self.clear_temp_files(),
            "network_reset": self.network_reset(),
            "check_disk": self.check_disk(),
        }

        self.logger.info(self.MODULE, "fim", "Módulo de reparos concluído")
        return results

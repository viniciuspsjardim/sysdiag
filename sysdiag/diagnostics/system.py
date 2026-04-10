"""
Módulo de diagnóstico de sistema.

Coleta informações sobre processos em execução, serviços, logs de erros
e integridade de arquivos do sistema. Adapta os comandos para cada plataforma.
"""

from typing import Optional

from sysdiag.core.executor import run_platform_command, run_command, CommandResult
from sysdiag.core.logger import DiagnosticLogger
from sysdiag.core.os_detect import detect_os, is_elevated


class SystemDiagnostic:
    """
    Classe para diagnósticos do sistema operacional.

    Coleta informações sobre processos, serviços, logs de erros
    e integridade do sistema.
    """

    MODULE = "sistema"

    def __init__(self, logger: DiagnosticLogger):
        """
        Inicializa o módulo de diagnóstico de sistema.

        Args:
            logger: Instância do DiagnosticLogger para registro.
        """
        self.logger = logger
        self.os_name = detect_os()

    def process_list(self, timeout: int = 30) -> CommandResult:
        """
        Lista os processos em execução no sistema.

        Returns:
            CommandResult com a lista de processos.
        """
        result = run_platform_command("process_list", timeout=timeout)

        if result.success:
            lines = result.stdout.strip().split("\n")
            self.logger.success(self.MODULE, "processos",
                                f"Processos listados: {len(lines)} linhas",
                                data={"total_lines": len(lines)})
        else:
            self.logger.error(self.MODULE, "processos", "Falha ao listar processos",
                              error_detail=result.stderr)

        return result

    def error_logs(self, timeout: int = 30) -> CommandResult:
        """
        Coleta logs de erros recentes do sistema.

        Em Windows usa o Event Log via PowerShell; em Linux usa journalctl;
        em macOS usa o comando log.

        Returns:
            CommandResult com logs de erros.
        """
        if self.os_name == "windows":
            cmd = [
                "powershell", "-Command",
                "Get-EventLog -LogName System -EntryType Error -Newest 20 | "
                "Format-Table -AutoSize TimeGenerated, Source, Message"
            ]
            result = run_command(cmd, timeout=timeout)
        else:
            result = run_platform_command("system_integrity", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "logs_erro", "Logs de erro coletados")
        else:
            self.logger.warning(self.MODULE, "logs_erro",
                                "Falha ao coletar logs de erro (pode requerer privilégios)",
                                data={"error": result.stderr})

        return result

    def system_integrity(self, timeout: int = 300) -> CommandResult:
        """
        Verifica a integridade dos arquivos do sistema.

        ATENÇÃO: Em Windows (sfc /scannow), requer privilégios de administrador
        e pode levar vários minutos.

        Returns:
            CommandResult com resultado da verificação.
        """
        if not is_elevated():
            msg = (
                "Verificação de integridade requer privilégios elevados. "
                "Execute novamente como Administrador (Windows) ou com sudo (Linux/macOS)."
            )
            self.logger.warning(self.MODULE, "integridade", msg)
            return CommandResult(
                command="system_integrity",
                return_code=-1,
                stdout="",
                stderr=msg,
                success=False,
                timestamp="",
                duration_ms=0,
                error_type="permission_denied",
                platform=self.os_name,
            )

        if self.os_name == "windows":
            result = run_command(["sfc", "/scannow"], timeout=timeout)
        elif self.os_name == "linux":
            result = run_command(["journalctl", "-p", "err", "--no-pager", "-n", "50"], timeout=timeout)
        else:
            result = run_command(
                ["log", "show", "--predicate", "eventType == logEvent AND logLevel == error", "--last", "1h"],
                timeout=timeout,
            )

        if result.success:
            self.logger.success(self.MODULE, "integridade", "Verificação de integridade concluída")
        else:
            self.logger.error(self.MODULE, "integridade", "Falha na verificação de integridade",
                              error_detail=result.stderr)

        return result

    def services_status(self, timeout: int = 30) -> CommandResult:
        """
        Lista serviços do sistema e seus estados.

        Returns:
            CommandResult com lista de serviços.
        """
        if self.os_name == "windows":
            cmd = ["powershell", "-Command",
                   "Get-Service | Where-Object {$_.Status -ne 'Stopped'} | "
                   "Format-Table -AutoSize Name, Status, DisplayName"]
        elif self.os_name == "linux":
            cmd = ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"]
        else:
            cmd = ["launchctl", "list"]

        result = run_command(cmd, timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "servicos", "Serviços listados com sucesso")
        else:
            self.logger.warning(self.MODULE, "servicos", "Falha ao listar serviços",
                                data={"error": result.stderr})

        return result

    def uptime(self, timeout: int = 10) -> CommandResult:
        """
        Retorna o tempo de atividade (uptime) do sistema.

        Returns:
            CommandResult com o uptime.
        """
        if self.os_name == "windows":
            cmd = ["powershell", "-Command",
                   "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | "
                   "Select-Object Days, Hours, Minutes | Format-List"]
        elif self.os_name == "linux":
            cmd = ["uptime"]
        else:
            cmd = ["uptime"]

        result = run_command(cmd, timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "uptime", f"Uptime: {result.stdout.strip()}")
        else:
            self.logger.warning(self.MODULE, "uptime", "Falha ao obter uptime")

        return result

    def run_all(self, check_integrity: bool = False) -> dict:
        """
        Executa todos os diagnósticos de sistema disponíveis.

        Args:
            check_integrity: Se True, executa verificação de integridade
                             (requer privilégios elevados e pode demorar).

        Returns:
            Dicionário com os resultados de cada diagnóstico.
        """
        self.logger.info(self.MODULE, "inicio", "Iniciando diagnóstico completo de sistema")

        results = {
            "uptime": self.uptime(),
            "process_list": self.process_list(),
            "services": self.services_status(),
            "error_logs": self.error_logs(),
        }

        if check_integrity:
            results["integrity"] = self.system_integrity()

        self.logger.info(self.MODULE, "fim", "Diagnóstico de sistema concluído")
        return results

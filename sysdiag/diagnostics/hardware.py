"""
Módulo de diagnóstico de hardware.

Coleta informações sobre CPU, memória RAM, discos e temperatura
(quando disponível). Adapta os comandos para cada plataforma.
"""

import os
from typing import Optional

from sysdiag.core.executor import run_platform_command, run_command, CommandResult
from sysdiag.core.logger import DiagnosticLogger
from sysdiag.core.os_detect import detect_os


class HardwareDiagnostic:
    """
    Classe para diagnósticos de hardware.

    Coleta informações sobre CPU, memória, disco e temperatura,
    registrando tudo no logger fornecido.
    """

    MODULE = "hardware"

    def __init__(self, logger: DiagnosticLogger):
        """
        Inicializa o módulo de diagnóstico de hardware.

        Args:
            logger: Instância do DiagnosticLogger para registro.
        """
        self.logger = logger
        self.os_name = detect_os()

    def cpu_info(self, timeout: int = 30) -> CommandResult:
        """
        Coleta informações sobre o processador (CPU).

        Returns:
            CommandResult com dados da CPU.
        """
        result = run_platform_command("cpu_info", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "cpu_info", "Informações da CPU coletadas")
        else:
            self.logger.error(self.MODULE, "cpu_info", "Falha ao coletar informações da CPU",
                              error_detail=result.stderr)

        return result

    def memory_info(self, timeout: int = 30) -> CommandResult:
        """
        Coleta informações sobre a memória RAM.

        Returns:
            CommandResult com dados de memória.
        """
        result = run_platform_command("memory_info", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "memory_info", "Informações de memória coletadas")
        else:
            self.logger.error(self.MODULE, "memory_info", "Falha ao coletar informações de memória",
                              error_detail=result.stderr)

        return result

    def disk_info(self, timeout: int = 30) -> CommandResult:
        """
        Coleta informações sobre os discos instalados.

        Returns:
            CommandResult com dados dos discos.
        """
        result = run_platform_command("disk_info", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "disk_info", "Informações de disco coletadas")
        else:
            self.logger.error(self.MODULE, "disk_info", "Falha ao coletar informações de disco",
                              error_detail=result.stderr)

        return result

    def disk_usage_python(self) -> dict:
        """
        Coleta uso de disco usando os.statvfs/shutil (stdlib).

        Funciona em qualquer plataforma sem depender de ferramentas externas.

        Returns:
            Dicionário com total, usado e livre em bytes e porcentagem.
        """
        import shutil

        try:
            total, used, free = shutil.disk_usage("/")
            result = {
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(free / (1024 ** 3), 2),
                "percent_used": round((used / total) * 100, 1),
            }
            self.logger.success(self.MODULE, "disk_usage",
                                f"Uso de disco: {result['percent_used']}% ({result['used_gb']}GB / {result['total_gb']}GB)",
                                data=result)
            return result
        except OSError as e:
            self.logger.error(self.MODULE, "disk_usage", "Falha ao obter uso de disco",
                              error_detail=str(e))
            return {"error": str(e)}

    def temperature(self, timeout: int = 30) -> CommandResult:
        """
        Tenta coletar informações de temperatura do hardware.

        Nota: Disponibilidade varia por plataforma e hardware.
        Em muitos sistemas requer privilégios elevados.

        Returns:
            CommandResult com dados de temperatura (se disponível).
        """
        if self.os_name == "windows":
            cmd = ["wmic", "/namespace:\\\\root\\OpenHardwareMonitor", "path", "Sensor",
                   "where", "SensorType='Temperature'", "get", "Name,Value"]
        elif self.os_name == "linux":
            # Tenta sensors (lm-sensors) primeiro, depois thermal zones
            cmd = ["sensors"]
            result = run_command(cmd, timeout=timeout)
            if not result.success:
                cmd = ["cat", "/sys/class/thermal/thermal_zone0/temp"]
                result = run_command(cmd, timeout=timeout)
                if result.success:
                    try:
                        temp_mc = int(result.stdout.strip())
                        result = CommandResult(
                            command="thermal_zone0",
                            return_code=0,
                            stdout=f"Temperatura CPU: {temp_mc / 1000:.1f}°C",
                            stderr="",
                            success=True,
                            timestamp=result.timestamp,
                            duration_ms=result.duration_ms,
                            platform=result.platform,
                        )
                    except ValueError:
                        pass
                self._log_temperature(result)
                return result
        else:  # darwin
            cmd = ["sudo", "powermetrics", "--samplers", "smc", "-n", "1"]

        result = run_command(cmd, timeout=timeout)
        self._log_temperature(result)
        return result

    def _log_temperature(self, result: CommandResult) -> None:
        """Registra o resultado da leitura de temperatura no log."""
        if result.success:
            self.logger.success(self.MODULE, "temperatura", "Temperatura coletada com sucesso")
        else:
            self.logger.warning(self.MODULE, "temperatura",
                                "Leitura de temperatura indisponível (pode requerer software adicional ou privilégios)",
                                data={"error": result.stderr})

    def cpu_count(self) -> dict:
        """
        Retorna o número de CPUs usando a stdlib do Python.

        Returns:
            Dicionário com contagem de CPUs lógicas.
        """
        count = os.cpu_count() or 0
        result = {"logical_cpus": count}
        self.logger.info(self.MODULE, "cpu_count", f"CPUs lógicas: {count}", data=result)
        return result

    def run_all(self) -> dict:
        """
        Executa todos os diagnósticos de hardware disponíveis.

        Returns:
            Dicionário com os resultados de cada diagnóstico.
        """
        self.logger.info(self.MODULE, "inicio", "Iniciando diagnóstico completo de hardware")

        results = {
            "cpu_info": self.cpu_info(),
            "cpu_count": self.cpu_count(),
            "memory_info": self.memory_info(),
            "disk_info": self.disk_info(),
            "disk_usage": self.disk_usage_python(),
            "temperature": self.temperature(),
        }

        self.logger.info(self.MODULE, "fim", "Diagnóstico de hardware concluído")
        return results

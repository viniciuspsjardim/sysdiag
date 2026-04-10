"""
Módulo de execução de comandos com abstração multiplataforma.

Encapsula a execução de subprocessos, tratando diferenças entre
Windows, macOS e Linux. Fornece tratamento uniforme de erros,
timeouts e captura de saída.
"""

import subprocess
import shutil
import shlex
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from sysdiag.core.os_detect import detect_os


@dataclass
class CommandResult:
    """Resultado da execução de um comando."""

    command: str              # Comando executado
    return_code: int          # Código de retorno (0 = sucesso)
    stdout: str               # Saída padrão
    stderr: str               # Saída de erro
    success: bool             # True se return_code == 0
    timestamp: str            # Momento da execução (ISO 8601)
    duration_ms: float        # Duração em milissegundos
    error_type: Optional[str] = None  # Tipo de erro, se houver
    platform: str = ""        # Plataforma onde foi executado


# Mapeamento de comandos equivalentes entre plataformas.
# Chave: nome genérico → valor: dict com comando por SO.
PLATFORM_COMMANDS: dict[str, dict[str, list[str]]] = {
    "ping": {
        "windows": ["ping", "-n", "4"],
        "linux": ["ping", "-c", "4"],
        "darwin": ["ping", "-c", "4"],
    },
    "traceroute": {
        "windows": ["tracert"],
        "linux": ["traceroute"],
        "darwin": ["traceroute"],
    },
    "dns_lookup": {
        "windows": ["nslookup"],
        "linux": ["dig"],
        "darwin": ["dig"],
    },
    "ip_config": {
        "windows": ["ipconfig", "/all"],
        "linux": ["ip", "addr"],
        "darwin": ["ifconfig"],
    },
    "open_ports": {
        "windows": ["netstat", "-an"],
        "linux": ["ss", "-tulnp"],
        "darwin": ["netstat", "-an"],
    },
    "flush_dns": {
        "windows": ["ipconfig", "/flushdns"],
        "linux": ["resolvectl", "flush-caches"],
        "darwin": ["dscacheutil", "-flushcache"],
    },
    "disk_info": {
        "windows": ["wmic", "diskdrive", "get", "Status,Size,Model"],
        "linux": ["df", "-h"],
        "darwin": ["df", "-h"],
    },
    "memory_info": {
        "windows": ["wmic", "memorychip", "get", "Capacity,Speed,Manufacturer"],
        "linux": ["free", "-h"],
        "darwin": ["vm_stat"],
    },
    "cpu_info": {
        "windows": ["wmic", "cpu", "get", "Name,NumberOfCores,MaxClockSpeed"],
        "linux": ["lscpu"],
        "darwin": ["sysctl", "-n", "machdep.cpu.brand_string"],
    },
    "process_list": {
        "windows": ["tasklist"],
        "linux": ["ps", "aux"],
        "darwin": ["ps", "aux"],
    },
    "check_disk": {
        "windows": ["chkdsk"],
        "linux": ["fsck", "-n"],
        "darwin": ["diskutil", "verifyVolume", "/"],
    },
    "system_integrity": {
        "windows": ["sfc", "/scannow"],
        "linux": ["journalctl", "-p", "err", "--no-pager", "-n", "50"],
        "darwin": ["log", "show", "--predicate", "eventType == logEvent AND logLevel == error", "--last", "1h"],
    },
    # ── Wi-Fi / Wireless ──────────────────────────────────────────
    "wifi_report": {
        "windows": ["netsh", "wlan", "show", "wlanreport"],
        "linux": ["nmcli", "device", "wifi", "list"],
        "darwin": ["system_profiler", "SPAirPortDataType"],
    },
    "wifi_interfaces": {
        "windows": ["netsh", "wlan", "show", "interfaces"],
        "linux": ["iw", "dev"],
        "darwin": [
            "/System/Library/PrivateFrameworks/Apple80211.framework/"
            "Versions/Current/Resources/airport", "-I",
        ],
    },
    "wifi_profiles": {
        "windows": ["netsh", "wlan", "show", "profiles"],
        "linux": ["nmcli", "connection", "show"],
        "darwin": ["networksetup", "-listpreferredwirelessnetworks", "en0"],
    },
    "wifi_drivers": {
        "windows": ["netsh", "wlan", "show", "drivers"],
        "linux": ["lspci", "-k"],
        "darwin": ["system_profiler", "SPAirPortDataType"],
    },
    # ── Reparos ────────────────────────────────────────────────────
    "network_reset": {
        "windows": ["netsh", "winsock", "reset"],
        "linux": ["systemctl", "restart", "NetworkManager"],
        "darwin": ["networksetup", "-setairportpower", "en0", "off"],
    },
}


def get_platform_command(generic_name: str, extra_args: Optional[list[str]] = None) -> list[str]:
    """
    Retorna o comando específico da plataforma para um nome genérico.

    Args:
        generic_name: Nome genérico do comando (ex: 'ping', 'traceroute').
        extra_args: Argumentos adicionais a serem adicionados ao comando.

    Returns:
        Lista de argumentos do comando para a plataforma atual.

    Raises:
        KeyError: Se o nome genérico não existir no mapeamento.
        NotImplementedError: Se o comando não estiver disponível na plataforma.
    """
    sistema = detect_os()
    if generic_name not in PLATFORM_COMMANDS:
        raise KeyError(f"Comando genérico '{generic_name}' não encontrado no mapeamento.")

    plataformas = PLATFORM_COMMANDS[generic_name]
    if sistema not in plataformas:
        raise NotImplementedError(
            f"Comando '{generic_name}' não disponível para a plataforma '{sistema}'."
        )

    cmd = list(plataformas[sistema])
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def is_command_available(command: str) -> bool:
    """
    Verifica se um comando está disponível no PATH do sistema.

    Args:
        command: Nome do executável a verificar.

    Returns:
        True se o comando for encontrado no PATH.
    """
    return shutil.which(command) is not None


def run_command(
    command: str | list[str],
    timeout: int = 60,
    shell: bool = False,
    encoding: str = "utf-8",
) -> CommandResult:
    """
    Executa um comando e retorna o resultado encapsulado.

    Trata automaticamente erros de timeout, comando não encontrado
    e permissão negada, retornando sempre um CommandResult válido.

    Args:
        command: Comando como string ou lista de argumentos.
        timeout: Tempo máximo de execução em segundos.
        shell: Se True, executa via shell (necessário para comandos compostos).
        encoding: Encoding para decodificação da saída.

    Returns:
        CommandResult com os dados da execução.
    """
    timestamp = datetime.now().isoformat()
    sistema = detect_os()

    # Normalizar comando para string de exibição
    if isinstance(command, list):
        cmd_display = " ".join(command)
    else:
        cmd_display = command
        if not shell:
            command = shlex.split(command) if sistema != "windows" else command.split()

    start = datetime.now()

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=shell,
            encoding=encoding,
            errors="replace",
        )
        duration = (datetime.now() - start).total_seconds() * 1000

        return CommandResult(
            command=cmd_display,
            return_code=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
            success=result.returncode == 0,
            timestamp=timestamp,
            duration_ms=round(duration, 2),
            platform=sistema,
        )

    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start).total_seconds() * 1000
        return CommandResult(
            command=cmd_display,
            return_code=-1,
            stdout="",
            stderr=f"Tempo limite excedido ({timeout}s).",
            success=False,
            timestamp=timestamp,
            duration_ms=round(duration, 2),
            error_type="timeout",
            platform=sistema,
        )

    except FileNotFoundError:
        duration = (datetime.now() - start).total_seconds() * 1000
        return CommandResult(
            command=cmd_display,
            return_code=-1,
            stdout="",
            stderr=f"Comando não encontrado: {cmd_display.split()[0]}",
            success=False,
            timestamp=timestamp,
            duration_ms=round(duration, 2),
            error_type="not_found",
            platform=sistema,
        )

    except PermissionError:
        duration = (datetime.now() - start).total_seconds() * 1000
        return CommandResult(
            command=cmd_display,
            return_code=-1,
            stdout="",
            stderr=(
                f"Permissão negada para executar: {cmd_display}. "
                "Tente re-executar com privilégios elevados "
                "(sudo no Linux/macOS ou Executar como Administrador no Windows)."
            ),
            success=False,
            timestamp=timestamp,
            duration_ms=round(duration, 2),
            error_type="permission_denied",
            platform=sistema,
        )

    except OSError as e:
        duration = (datetime.now() - start).total_seconds() * 1000
        return CommandResult(
            command=cmd_display,
            return_code=-1,
            stdout="",
            stderr=f"Erro de SO: {e}",
            success=False,
            timestamp=timestamp,
            duration_ms=round(duration, 2),
            error_type="os_error",
            platform=sistema,
        )


def run_platform_command(
    generic_name: str,
    extra_args: Optional[list[str]] = None,
    timeout: int = 60,
) -> CommandResult:
    """
    Executa um comando genérico usando o mapeamento de plataforma.

    Combina get_platform_command() e run_command() para simplificar
    a execução de comandos multiplataforma.

    Args:
        generic_name: Nome genérico do comando (ex: 'ping').
        extra_args: Argumentos adicionais (ex: ['google.com']).
        timeout: Tempo máximo em segundos.

    Returns:
        CommandResult com os dados da execução.
    """
    try:
        cmd = get_platform_command(generic_name, extra_args)
    except (KeyError, NotImplementedError) as e:
        return CommandResult(
            command=f"[{generic_name}]",
            return_code=-1,
            stdout="",
            stderr=str(e),
            success=False,
            timestamp=datetime.now().isoformat(),
            duration_ms=0,
            error_type="unsupported",
            platform=detect_os(),
        )

    return run_command(cmd, timeout=timeout)

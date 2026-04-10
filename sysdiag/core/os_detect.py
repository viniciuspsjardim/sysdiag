"""
Módulo de detecção de sistema operacional.

Identifica o SO em execução (Windows, macOS ou Linux), sua versão,
arquitetura e fornece uma interface unificada para consulta dessas
informações em qualquer plataforma.
"""

import platform
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SystemInfo:
    """Informações consolidadas sobre o sistema operacional."""

    os_name: str          # 'windows', 'linux' ou 'darwin'
    os_display: str       # Nome amigável (ex: 'Windows 11', 'Ubuntu 22.04')
    version: str          # Versão do kernel ou build
    architecture: str     # 'x86_64', 'arm64', etc.
    hostname: str         # Nome da máquina
    python_version: str   # Versão do Python em execução
    is_elevated: bool     # Se está rodando com privilégios elevados
    extra: dict = field(default_factory=dict)


def detect_os() -> str:
    """
    Retorna o identificador normalizado do SO.

    Returns:
        'windows', 'linux' ou 'darwin'
    """
    return platform.system().lower()


def get_os_version() -> str:
    """
    Retorna a versão do sistema operacional.

    Em Windows retorna a versão do build; em Linux/macOS retorna
    a versão do kernel.
    """
    sistema = detect_os()
    if sistema == "windows":
        ver = platform.version()
        release = platform.release()
        return f"Windows {release} (Build {ver})"
    elif sistema == "darwin":
        mac_ver = platform.mac_ver()[0]
        return f"macOS {mac_ver}" if mac_ver else f"macOS (kernel {platform.release()})"
    else:
        return f"Linux (kernel {platform.release()})"


def get_architecture() -> str:
    """Retorna a arquitetura do processador (ex: 'x86_64', 'arm64')."""
    return platform.machine()


def get_hostname() -> str:
    """Retorna o nome da máquina (hostname)."""
    return platform.node()


def is_elevated() -> bool:
    """
    Verifica se o processo está rodando com privilégios elevados.

    Em Windows verifica se é administrador; em Linux/macOS verifica
    se é root (UID 0).
    """
    sistema = detect_os()
    if sistema == "windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except (AttributeError, OSError):
            return False
    else:
        return os.geteuid() == 0


def get_display_name() -> str:
    """
    Retorna o nome amigável do SO para exibição.

    Tenta obter o nome da distribuição Linux, versão do macOS
    ou edição do Windows.
    """
    sistema = detect_os()
    if sistema == "windows":
        edition = platform.win32_edition() if hasattr(platform, "win32_edition") else ""
        release = platform.release()
        return f"Windows {release} {edition}".strip()
    elif sistema == "darwin":
        mac_ver = platform.mac_ver()[0]
        return f"macOS {mac_ver}" if mac_ver else "macOS"
    else:
        return _get_linux_distro()


def _get_linux_distro() -> str:
    """
    Tenta ler o nome da distribuição Linux a partir de /etc/os-release.

    Returns:
        Nome da distribuição ou 'Linux' se não for possível detectar.
    """
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            info = {}
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, _, value = line.partition("=")
                    info[key] = value.strip('"')
            return info.get("PRETTY_NAME", "Linux")
    except (FileNotFoundError, PermissionError):
        return "Linux"


def get_system_info() -> SystemInfo:
    """
    Coleta todas as informações do sistema e retorna um objeto consolidado.

    Returns:
        SystemInfo com todos os campos preenchidos.
    """
    return SystemInfo(
        os_name=detect_os(),
        os_display=get_display_name(),
        version=get_os_version(),
        architecture=get_architecture(),
        hostname=get_hostname(),
        python_version=platform.python_version(),
        is_elevated=is_elevated(),
        extra={
            "processor": platform.processor(),
            "platform": platform.platform(),
        },
    )


def print_system_info(info: Optional[SystemInfo] = None) -> str:
    """
    Formata as informações do sistema para exibição legível.

    Args:
        info: Objeto SystemInfo; se None, coleta automaticamente.

    Returns:
        String formatada com as informações do sistema.
    """
    if info is None:
        info = get_system_info()

    lines = [
        "=" * 50,
        "  INFORMAÇÕES DO SISTEMA",
        "=" * 50,
        f"  SO            : {info.os_display}",
        f"  Versão        : {info.version}",
        f"  Arquitetura   : {info.architecture}",
        f"  Hostname      : {info.hostname}",
        f"  Python        : {info.python_version}",
        f"  Privilegiado  : {'Sim' if info.is_elevated else 'Não'}",
        f"  Plataforma    : {info.extra.get('platform', 'N/A')}",
        "=" * 50,
    ]
    return "\n".join(lines)

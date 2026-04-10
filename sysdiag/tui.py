"""
Interface interativa (TUI) do SysDiag.

Exibe informacoes do sistema e permite ao usuario escolher
quais diagnosticos executar atraves de um menu interativo
antes de iniciar a execucao.
"""

import io
import os
import sys
import shutil
from datetime import datetime
from typing import Optional

from sysdiag.core.os_detect import get_system_info, SystemInfo, detect_os
from sysdiag.core.logger import DiagnosticLogger
from sysdiag.core.executor import is_command_available
from sysdiag.diagnostics.network import NetworkDiagnostic
from sysdiag.diagnostics.hardware import HardwareDiagnostic
from sysdiag.diagnostics.system import SystemDiagnostic
from sysdiag.repairs.repair import RepairModule
from sysdiag.report.report import DiagnosticReport


# ─── Constantes de layout ────────────────────────────────────────────────────

TERM_WIDTH = min(shutil.get_terminal_size((80, 24)).columns, 80)

# Cores ANSI (com fallback se terminal nao suportar)
class Colors:
    """Codigos de cores ANSI para formatacao do terminal."""

    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    GREEN   = "\033[92m"
    RED     = "\033[91m"
    YELLOW  = "\033[93m"
    CYAN    = "\033[96m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    WHITE   = "\033[97m"
    BG_DARK = "\033[48;5;235m"

    @classmethod
    def disable(cls):
        """Desativa todas as cores (para terminais sem suporte)."""
        for attr in dir(cls):
            if attr.isupper() and isinstance(getattr(cls, attr), str):
                setattr(cls, attr, "")


def _supports_color() -> bool:
    """Verifica se o terminal suporta cores ANSI."""
    if sys.platform == "win32":
        # Windows 10+ suporta ANSI se VIRTUAL_TERMINAL_PROCESSING estiver ativo
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Habilitar VT100 no console Windows
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
            return True
        except Exception:
            return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


C = Colors  # alias curto


def _line(char: str = "-", width: int = TERM_WIDTH) -> str:
    """Gera uma linha horizontal."""
    return char * width


def _center(text: str, width: int = TERM_WIDTH) -> str:
    """Centraliza texto na largura do terminal."""
    # Descontar codigos ANSI para calculo de padding
    import re
    clean = re.sub(r'\033\[[0-9;]*m', '', text)
    padding = max(0, (width - len(clean)) // 2)
    return " " * padding + text


def _clear_screen():
    """Limpa a tela do terminal."""
    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")


def _bar(value: float, max_val: float = 100, width: int = 30) -> str:
    """
    Gera uma barra de progresso visual.

    Args:
        value: Valor atual.
        max_val: Valor maximo.
        width: Largura em caracteres.

    Returns:
        String formatada com a barra.
    """
    ratio = min(value / max_val, 1.0) if max_val > 0 else 0
    filled = int(width * ratio)
    empty = width - filled

    if ratio < 0.6:
        color = C.GREEN
    elif ratio < 0.85:
        color = C.YELLOW
    else:
        color = C.RED

    bar = f"{color}{'#' * filled}{C.DIM}{'.' * empty}{C.RESET}"
    return f"[{bar}] {value:.1f}%"


# ─── Coleta rapida de dados ──────────────────────────────────────────────────

def _quick_disk_usage() -> dict:
    """Coleta uso de disco rapidamente via shutil."""
    import shutil as sh
    try:
        if sys.platform == "win32":
            total, used, free = sh.disk_usage("C:\\")
        else:
            total, used, free = sh.disk_usage("/")
        return {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
            "percent": round((used / total) * 100, 1) if total > 0 else 0,
        }
    except OSError:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}


def _quick_cpu_count() -> int:
    """Retorna numero de CPUs logicas."""
    return os.cpu_count() or 0


def _quick_memory_info() -> Optional[dict]:
    """Tenta obter info de memoria rapidamente (Windows via ctypes)."""
    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            total = mem.ullTotalPhys
            avail = mem.ullAvailPhys
            used = total - avail
            return {
                "total_gb": round(total / (1024**3), 1),
                "used_gb": round(used / (1024**3), 1),
                "avail_gb": round(avail / (1024**3), 1),
                "percent": round((used / total) * 100, 1) if total > 0 else 0,
            }
        except Exception:
            return None
    else:
        try:
            with open("/proc/meminfo", "r") as f:
                info = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(":")] = int(parts[1])
                total = info.get("MemTotal", 0)
                avail = info.get("MemAvailable", 0)
                used = total - avail
                return {
                    "total_gb": round(total / (1024**2), 1),
                    "used_gb": round(used / (1024**2), 1),
                    "avail_gb": round(avail / (1024**2), 1),
                    "percent": round((used / total) * 100, 1) if total > 0 else 0,
                }
        except (FileNotFoundError, KeyError):
            return None


# ─── Tela principal ──────────────────────────────────────────────────────────

def _print_header(info: SystemInfo):
    """Exibe o cabecalho com banner do SysDiag."""
    print()
    print(f"{C.CYAN}{C.BOLD}{_line('=')}{C.RESET}")
    print(_center(f"{C.CYAN}{C.BOLD}S Y S D I A G{C.RESET}"))
    print(_center(f"{C.DIM}Ferramenta de Diagnostico Multiplataforma v1.0.0{C.RESET}"))
    print(f"{C.CYAN}{C.BOLD}{_line('=')}{C.RESET}")
    print()


def _print_system_panel(info: SystemInfo, mem: Optional[dict], disk: dict):
    """Exibe o painel com informacoes do sistema."""

    # Titulo da secao
    print(f"  {C.BOLD}{C.WHITE}SISTEMA DETECTADO{C.RESET}")
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()

    # Info do SO
    elevated_str = f"{C.GREEN}Sim{C.RESET}" if info.is_elevated else f"{C.YELLOW}Nao{C.RESET}"
    print(f"  {C.DIM}SO{C.RESET}            {C.BOLD}{info.os_display}{C.RESET}")
    print(f"  {C.DIM}Versao{C.RESET}        {info.version}")
    print(f"  {C.DIM}Arquitetura{C.RESET}   {info.architecture}")
    print(f"  {C.DIM}Hostname{C.RESET}      {C.BOLD}{info.hostname}{C.RESET}")
    print(f"  {C.DIM}Python{C.RESET}        {info.python_version}")
    print(f"  {C.DIM}Privilegiado{C.RESET}  {elevated_str}")
    print()

    # Hardware resumido
    print(f"  {C.BOLD}{C.WHITE}RECURSOS DO HARDWARE{C.RESET}")
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()

    # CPU
    cpu_count = _quick_cpu_count()
    proc = info.extra.get("processor", "N/A")
    # Limitar nome do processador para caber
    if len(proc) > 50:
        proc = proc[:47] + "..."
    print(f"  {C.CYAN}CPU{C.RESET}   {proc}")
    print(f"        {cpu_count} nucleos logicos")
    print()

    # Memoria
    if mem:
        print(f"  {C.MAGENTA}RAM{C.RESET}   {mem['total_gb']} GB total | {mem['used_gb']} GB usado | {mem['avail_gb']} GB livre")
        print(f"        {_bar(mem['percent'])}")
    else:
        print(f"  {C.MAGENTA}RAM{C.RESET}   {C.DIM}Informacao indisponivel (execute diagnostico para detalhes){C.RESET}")
    print()

    # Disco
    drive = "C:\\" if sys.platform == "win32" else "/"
    print(f"  {C.BLUE}DISCO{C.RESET} {disk['total_gb']} GB total | {disk['used_gb']} GB usado | {disk['free_gb']} GB livre  ({drive})")
    print(f"        {_bar(disk['percent'])}")
    print()


def _print_menu(show_repair: bool = True) -> None:
    """Exibe o menu de opcoes de diagnostico."""
    print(f"  {C.BOLD}{C.WHITE}MODULOS DE DIAGNOSTICO{C.RESET}")
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()
    print(f"  {C.GREEN}[1]{C.RESET}  Diagnostico de Rede")
    print(f"       {C.DIM}Ping, traceroute, DNS, portas abertas, interfaces{C.RESET}")
    print()
    print(f"  {C.GREEN}[2]{C.RESET}  Diagnostico de Hardware")
    print(f"       {C.DIM}CPU, memoria RAM, disco, temperatura{C.RESET}")
    print()
    print(f"  {C.GREEN}[3]{C.RESET}  Diagnostico de Sistema")
    print(f"       {C.DIM}Processos, servicos, logs de erro, uptime{C.RESET}")
    print()
    print(f"  {C.GREEN}[4]{C.RESET}  Diagnostico de Wi-Fi")
    print(f"       {C.DIM}Interface wireless, perfis salvos, driver, relatorio WLAN{C.RESET}")
    print()
    print(f"  {C.CYAN}{C.BOLD}[5]{C.RESET}  {C.BOLD}Executar TODOS os diagnosticos{C.RESET}")
    print()
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()
    print(f"  {C.YELLOW}[6]{C.RESET}  Reparos automatizados")
    print(f"       {C.DIM}Flush DNS, limpeza cache, verificacao disco, reset rede{C.RESET}")
    print()
    print(f"  {C.YELLOW}[7]{C.RESET}  Verificacao de integridade do sistema")
    print(f"       {C.DIM}Requer privilegios elevados, pode demorar{C.RESET}")
    print()
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()
    print(f"  {C.MAGENTA}{C.BOLD}[8]{C.RESET}  {C.BOLD}Diagnostico manual de dominio{C.RESET}")
    print(f"       {C.DIM}Ping, traceroute, DNS e portas para um dominio especifico{C.RESET}")
    print()
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()
    print(f"  {C.RED}[0]{C.RESET}  Sair")
    print()


def _print_running_banner(module_name: str):
    """Exibe banner de modulo em execucao."""
    print()
    print(f"  {C.CYAN}{C.BOLD}>> Executando: {module_name}{C.RESET}")
    print(f"  {C.DIM}{_line('.', TERM_WIDTH - 4)}{C.RESET}")


def _print_test_status(name: str, success: bool, detail: str = ""):
    """Exibe status de um teste individual inline."""
    if success:
        icon = f"{C.GREEN}[OK]{C.RESET}"
    else:
        icon = f"{C.RED}[!!]{C.RESET}"
    line = f"     {icon} {name}"
    if detail:
        line += f"  {C.DIM}{detail}{C.RESET}"
    print(line)


def _print_module_results(name: str, results: dict):
    """Exibe resultado resumido de um modulo apos execucao."""
    success = 0
    errors = 0
    for key, val in results.items():
        if hasattr(val, "success"):
            if val.success:
                success += 1
                detail = f"{val.duration_ms:.0f}ms" if val.duration_ms else ""
                _print_test_status(key, True, detail)
            else:
                errors += 1
                detail = val.error_type or ""
                _print_test_status(key, False, detail)
        elif isinstance(val, dict):
            if "error" in val:
                errors += 1
                _print_test_status(key, False, str(val.get("error", ""))[:60])
            else:
                success += 1
                # Mostrar dados relevantes
                preview = ", ".join(f"{k}={v}" for k, v in list(val.items())[:3])
                _print_test_status(key, True, preview[:60])

    print()
    if errors == 0:
        print(f"     {C.GREEN}{C.BOLD}Resultado: {success} testes OK{C.RESET}")
    else:
        print(f"     {C.YELLOW}{C.BOLD}Resultado: {success} OK, {errors} com problemas{C.RESET}")
    print()


def _ask_choice(prompt: str, valid: list[str]) -> str:
    """
    Solicita uma escolha ao usuario com validacao.

    Args:
        prompt: Texto do prompt.
        valid: Lista de opcoes validas.

    Returns:
        Opcao escolhida (string).
    """
    while True:
        try:
            choice = input(f"  {C.BOLD}{prompt}{C.RESET} ").strip()
            if choice in valid:
                return choice
            print(f"  {C.RED}Opcao invalida. Escolha entre: {', '.join(valid)}{C.RESET}")
        except (EOFError, KeyboardInterrupt):
            print()
            return "0"


def _ask_output_dir() -> Optional[str]:
    """Pergunta diretorio de saida ao usuario."""
    print(f"  {C.DIM}Diretorio de saida para relatorios (Enter para ./logs):{C.RESET}")
    try:
        path = input(f"  {C.BOLD}> {C.RESET}").strip()
        return path if path else None
    except (EOFError, KeyboardInterrupt):
        return None


def _save_and_show_report(report: DiagnosticReport, logger: DiagnosticLogger):
    """Salva relatorios e exibe resumo final."""
    print()
    print(f"  {C.BOLD}{C.WHITE}GERANDO RELATORIOS{C.RESET}")
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")

    json_path = report.save_json()
    txt_path = report.save_txt()
    log_json = logger.save_json()
    log_txt = logger.save_txt()

    print()
    print(f"  {C.GREEN}Relatorio JSON:{C.RESET}  {json_path}")
    print(f"  {C.GREEN}Relatorio TXT:{C.RESET}   {txt_path}")
    print(f"  {C.DIM}Log JSON:         {log_json}{C.RESET}")
    print(f"  {C.DIM}Log TXT:          {log_txt}{C.RESET}")

    # Resumo final
    print()
    summary_text = report.print_summary()
    # Colorizar o resumo
    for line in summary_text.split("\n"):
        if "[OK]" in line:
            print(f"  {C.GREEN}{line}{C.RESET}")
        elif "[!!]" in line:
            print(f"  {C.YELLOW}{line}{C.RESET}")
        elif "Nenhum problema" in line:
            print(f"  {C.GREEN}{C.BOLD}{line}{C.RESET}")
        elif "problema(s)" in line:
            print(f"  {C.YELLOW}{C.BOLD}{line}{C.RESET}")
        else:
            print(f"  {line}")
    print()


# ─── Fluxo de diagnostico manual de dominio ──────────────────────────────────

def _run_manual_domain(info: SystemInfo, output_dir: Optional[str] = None) -> None:
    """
    Fluxo interativo completo para diagnostico manual de um dominio.

    Exibe tela propria, solicita o alvo ao usuario, executa os testes
    com feedback em tempo real e gera relatorio focado.
    """
    _clear_screen()
    _print_header(info)

    print(f"  {C.MAGENTA}{C.BOLD}DIAGNOSTICO MANUAL DE DOMINIO{C.RESET}")
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()
    print(f"  Informe o dominio ou IP que esta com problemas.")
    print(f"  {C.DIM}Exemplos: github.com, 192.168.1.1, meusite.com.br{C.RESET}")
    print()

    # ── Solicitar alvo ────────────────────────────────────────────────
    try:
        target = input(f"  {C.BOLD}Dominio/IP alvo: {C.RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not target:
        print(f"  {C.RED}Nenhum alvo informado. Retornando ao menu.{C.RESET}")
        _pause()
        return

    # ── Opcoes do diagnostico ─────────────────────────────────────────
    print()
    print(f"  {C.BOLD}{C.WHITE}CONFIGURACAO DO DIAGNOSTICO{C.RESET}")
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()
    print(f"  {C.GREEN}[1]{C.RESET}  Diagnostico completo (ping + traceroute + DNS + portas)")
    print(f"  {C.GREEN}[2]{C.RESET}  Apenas Ping estendido (10 pacotes)")
    print(f"  {C.GREEN}[3]{C.RESET}  Apenas Traceroute")
    print(f"  {C.GREEN}[4]{C.RESET}  Apenas DNS + verificacao de portas")
    print()

    test_choice = _ask_choice(
        "Selecione [1-4]:",
        ["1", "2", "3", "4"],
    )

    # ── Preparar logger e report ──────────────────────────────────────
    selected_dir = output_dir if output_dir else _ask_output_dir()

    logger = DiagnosticLogger(output_dir=selected_dir)
    report = DiagnosticReport(logger, output_dir=selected_dir)

    logger.info("core", "inicio", f"Diagnostico manual iniciado para: {target}", data={
        "target": target,
        "mode": "manual_dominio",
        "os": info.os_name,
    })

    net = NetworkDiagnostic(logger)
    results: dict = {}

    _clear_screen()
    _print_header(info)

    print(f"  {C.MAGENTA}{C.BOLD}DIAGNOSTICO MANUAL: {C.WHITE}{target}{C.RESET}")
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")

    # ── Execucao conforme escolha ─────────────────────────────────────

    if test_choice in ("1", "4"):
        # DNS
        _print_running_banner(f"RESOLUCAO DNS  >>  {target}")
        dns_results = net.manual_dns(target)
        results["dns_nativo"] = dns_results["native"]
        results["dns_python"] = dns_results["python"]

        # Exibir resultado DNS inline
        native = dns_results["native"]
        python = dns_results["python"]
        if native.success:
            _print_test_status("DNS nativo", True, f"{native.duration_ms:.0f}ms")
        else:
            _print_test_status("DNS nativo", False, native.stderr[:60] if native.stderr else "")

        if "error" not in python:
            addrs = ", ".join(python.get("addresses", []))
            _print_test_status("DNS python", True, addrs[:60])
        else:
            _print_test_status("DNS python", False, str(python.get("error", ""))[:60])
        print()

    if test_choice in ("1", "2"):
        # Ping estendido
        _print_running_banner(f"PING ESTENDIDO  >>  {target}  (10 pacotes)")
        ping_result = net.manual_ping(target, count=10)
        results["ping"] = ping_result

        if ping_result.success:
            _print_test_status("Ping", True, f"{ping_result.duration_ms:.0f}ms")
            # Extrair bloco de estatisticas do output
            lines_out = ping_result.stdout.splitlines()
            in_stats = False
            for sl in lines_out:
                sl_lower = sl.lower().strip()
                # Detectar inicio do bloco de estatisticas
                if any(kw in sl_lower for kw in [
                    "statistics", "estat", "packets", "pacotes",
                    "round-trip", "approximate", "aproximar",
                ]):
                    in_stats = True
                if in_stats and sl.strip():
                    print(f"       {C.DIM}{sl.strip()}{C.RESET}")
        else:
            _print_test_status("Ping", False, ping_result.stderr[:60] if ping_result.stderr else "")
        print()

    if test_choice in ("1", "3"):
        # Traceroute
        _print_running_banner(f"TRACEROUTE  >>  {target}")
        print(f"       {C.DIM}Aguarde, pode levar ate 3 minutos...{C.RESET}")
        trace_result = net.manual_traceroute(target)
        results["traceroute"] = trace_result

        if trace_result.success:
            hops = [
                l for l in trace_result.stdout.splitlines()
                if l.strip() and l.strip()[0].isdigit()
            ]
            _print_test_status("Traceroute", True, f"{len(hops)} saltos, {trace_result.duration_ms:.0f}ms")
            # Mostrar primeiros e ultimos saltos
            print()
            print(f"       {C.DIM}Rota ({len(hops)} saltos):{C.RESET}")
            display_hops = hops[:5]
            if len(hops) > 8:
                display_hops.append("       ...")
                display_hops.extend(hops[-3:])
            elif len(hops) > 5:
                display_hops.extend(hops[5:])
            for hop in display_hops:
                hop_str = hop.strip() if isinstance(hop, str) else str(hop)
                print(f"       {C.CYAN}|{C.RESET} {hop_str}")
        else:
            _print_test_status("Traceroute", False, trace_result.error_type or "timeout")
        print()

    if test_choice in ("1", "4"):
        # Port scan
        _print_running_banner(f"VERIFICACAO DE PORTAS  >>  {target}")
        scan = net.manual_port_scan(target)
        results["port_scan"] = scan

        open_p = scan.get("open_ports", [])
        closed_p = scan.get("closed_ports", [])
        total = len(open_p) + len(closed_p)

        if open_p:
            _print_test_status(
                "Portas abertas", True,
                ", ".join(str(p) for p in open_p),
            )
        else:
            _print_test_status("Portas abertas", False, "nenhuma porta aberta encontrada")

        print(f"       {C.DIM}Portas verificadas: {total} | Abertas: {len(open_p)} | Fechadas: {len(closed_p)}{C.RESET}")

        if open_p:
            print()
            port_labels = {
                21: "FTP", 22: "SSH", 25: "SMTP", 53: "DNS", 80: "HTTP",
                443: "HTTPS", 993: "IMAPS", 3306: "MySQL", 3389: "RDP",
                8080: "HTTP-Alt", 8443: "HTTPS-Alt",
            }
            for p in open_p:
                label = port_labels.get(p, "")
                print(f"       {C.GREEN}|{C.RESET} :{p}  {C.DIM}{label}{C.RESET}")
        print()

    # ── Analise de diagnostico ────────────────────────────────────────

    print()
    print(f"  {C.BOLD}{C.WHITE}ANALISE DO DIAGNOSTICO{C.RESET}")
    print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
    print()

    issues = []

    # Checar DNS
    dns_native = results.get("dns_nativo")
    dns_python = results.get("dns_python")
    if dns_native and not dns_native.success:
        issues.append(("DNS", f"Resolucao DNS falhou para {target} (ferramenta nativa)"))
    if isinstance(dns_python, dict) and "error" in dns_python:
        issues.append(("DNS", f"Resolucao DNS falhou para {target} (Python): {dns_python['error']}"))

    # Checar Ping
    ping_r = results.get("ping")
    if ping_r and not ping_r.success:
        issues.append(("CONECTIVIDADE", f"Ping falhou para {target}: host inacessivel ou bloqueado"))
    elif ping_r and ping_r.success:
        # Verificar perda de pacotes no output
        import re
        for line in ping_r.stdout.splitlines():
            ll = line.lower().strip()
            # Detectar linhas de estatisticas com porcentagem de perda
            loss_match = re.search(r'(\d+)%\s*(de\s+)?(?:loss|perda)', ll)
            if loss_match:
                loss_pct = int(loss_match.group(1))
                if loss_pct == 100:
                    issues.append(("CONECTIVIDADE", f"100% de perda de pacotes para {target}"))
                elif loss_pct > 0:
                    issues.append(("INSTABILIDADE", f"Perda de {loss_pct}% dos pacotes: {line.strip()}"))
                break

    # Checar Traceroute
    trace_r = results.get("traceroute")
    if trace_r and not trace_r.success:
        if trace_r.error_type == "timeout":
            issues.append(("ROTA", f"Traceroute expirou — rota para {target} pode estar bloqueada"))
        else:
            issues.append(("ROTA", f"Traceroute falhou: {trace_r.stderr[:80] if trace_r.stderr else 'erro desconhecido'}"))

    # Checar Portas
    scan_r = results.get("port_scan")
    if isinstance(scan_r, dict):
        open_p = scan_r.get("open_ports", [])
        if not open_p:
            issues.append(("PORTAS", f"Nenhuma porta aberta em {target} (servico pode estar fora do ar)"))
        else:
            # Verificar se portas web estao abertas
            web_ports = {80, 443}
            if not web_ports.intersection(open_p):
                issues.append(("PORTAS", f"Portas HTTP/HTTPS (80, 443) fechadas em {target}"))

    # Exibir resultado
    if not issues:
        print(f"  {C.GREEN}{C.BOLD}  Nenhum problema detectado na conexao com {target}.{C.RESET}")
        print(f"  {C.DIM}  O dominio esta acessivel e respondendo normalmente.{C.RESET}")
    else:
        print(f"  {C.YELLOW}{C.BOLD}  {len(issues)} problema(s) detectado(s):{C.RESET}")
        print()
        for i, (category, message) in enumerate(issues, 1):
            print(f"  {C.RED}  {i}. [{category}]{C.RESET} {message}")
        print()
        print(f"  {C.DIM}  Sugestoes:{C.RESET}")
        has_dns = any(c == "DNS" for c, _ in issues)
        has_conn = any(c == "CONECTIVIDADE" for c, _ in issues)
        has_route = any(c == "ROTA" for c, _ in issues)
        has_port = any(c == "PORTAS" for c, _ in issues)
        has_jitter = any(c == "INSTABILIDADE" for c, _ in issues)

        if has_dns:
            print(f"  {C.YELLOW}  - Verifique a configuracao de DNS (tente 8.8.8.8 ou 1.1.1.1){C.RESET}")
            print(f"  {C.YELLOW}  - Execute flush de DNS (opcao 6 > Reparos){C.RESET}")
        if has_conn:
            print(f"  {C.YELLOW}  - Verifique se ha conexao com a internet (ping 8.8.8.8){C.RESET}")
            print(f"  {C.YELLOW}  - O host pode estar bloqueando ICMP (ping){C.RESET}")
        if has_route:
            print(f"  {C.YELLOW}  - A rota ate o destino pode estar congestionada ou bloqueada{C.RESET}")
            print(f"  {C.YELLOW}  - Tente novamente em outro horario ou via VPN{C.RESET}")
        if has_port:
            print(f"  {C.YELLOW}  - O servico no destino pode estar fora do ar{C.RESET}")
            print(f"  {C.YELLOW}  - Um firewall pode estar bloqueando as portas{C.RESET}")
        if has_jitter:
            print(f"  {C.YELLOW}  - Conexao instavel — verifique cabo/WiFi ou contate o provedor{C.RESET}")

    print()

    # ── Salvar relatorio ──────────────────────────────────────────────

    report.add_results(f"dominio_{target}", results)

    logger.info("core", "fim", f"Diagnostico manual para {target} concluido")
    _save_and_show_report(report, logger)
    _pause()


def _pause():
    """Pausa aguardando Enter do usuario."""
    try:
        input(f"  {C.DIM}Pressione Enter para continuar...{C.RESET}")
    except (EOFError, KeyboardInterrupt):
        pass


# ─── Loop principal ──────────────────────────────────────────────────────────

def interactive_main(output_dir: Optional[str] = None) -> int:
    """
    Loop principal da interface interativa.

    Mostra info do sistema, menu de opcoes, executa diagnosticos
    selecionados e gera relatorios.

    Args:
        output_dir: Diretorio de saida (opcional).

    Returns:
        Codigo de saida (0 = sucesso).
    """
    # Configurar encoding UTF-8 no Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    # Detectar suporte a cores
    if not _supports_color():
        Colors.disable()

    # Coletar info rapida do sistema
    info = get_system_info()
    mem = _quick_memory_info()
    disk = _quick_disk_usage()

    while True:
        _clear_screen()

        # Cabecalho
        _print_header(info)

        # Painel de info do sistema
        _print_system_panel(info, mem, disk)

        # Menu
        _print_menu()

        # Escolha do usuario
        choice = _ask_choice(
            "Selecione uma opcao [0-8]:",
            ["0", "1", "2", "3", "4", "5", "6", "7", "8"]
        )

        if choice == "0":
            print()
            print(f"  {C.DIM}Encerrando SysDiag. Ate mais!{C.RESET}")
            print()
            return 0

        # Opcao 8: fluxo proprio de diagnostico manual
        if choice == "8":
            _run_manual_domain(info, output_dir=output_dir)
            continue

        # Configurar saida
        if output_dir is None:
            selected_dir = _ask_output_dir()
        else:
            selected_dir = output_dir

        # Inicializar logger e relatorio
        logger = DiagnosticLogger(output_dir=selected_dir)
        report = DiagnosticReport(logger, output_dir=selected_dir)

        logger.info("core", "inicio", "Sessao de diagnostico iniciada", data={
            "os": info.os_name,
            "version": info.version,
            "elevated": info.is_elevated,
            "mode": "interativo",
        })

        run_rede      = choice in ("1", "5")
        run_hardware  = choice in ("2", "5")
        run_sistema   = choice in ("3", "5")
        run_wifi      = choice in ("4", "5")
        run_reparos   = choice == "6"
        run_integridade = choice == "7"

        _clear_screen()
        _print_header(info)

        # ── Executar modulos selecionados ─────────────────────────────

        if run_rede:
            _print_running_banner("DIAGNOSTICO DE REDE")
            net = NetworkDiagnostic(logger)
            net_results = net.run_all(host="8.8.8.8", domain="google.com")
            report.add_results("rede", net_results)
            _print_module_results("rede", net_results)

        if run_wifi and not run_rede:
            # Se run_rede ja rodou, wifi ja esta incluso no run_all
            _print_running_banner("DIAGNOSTICO DE WI-FI")
            net = NetworkDiagnostic(logger)
            wifi_results = net.wifi_run_all()
            report.add_results("wifi", wifi_results)
            _print_module_results("wifi", wifi_results)

        if run_hardware:
            _print_running_banner("DIAGNOSTICO DE HARDWARE")
            hw = HardwareDiagnostic(logger)
            hw_results = hw.run_all()
            report.add_results("hardware", hw_results)
            _print_module_results("hardware", hw_results)

        if run_sistema:
            _print_running_banner("DIAGNOSTICO DE SISTEMA")
            sys_diag = SystemDiagnostic(logger)
            sys_results = sys_diag.run_all(check_integrity=False)
            report.add_results("sistema", sys_results)
            _print_module_results("sistema", sys_results)

        if run_integridade:
            _print_running_banner("VERIFICACAO DE INTEGRIDADE")
            sys_diag = SystemDiagnostic(logger)
            integrity_result = sys_diag.system_integrity(timeout=300)
            report.add_results("integridade", {"system_integrity": integrity_result})
            _print_module_results("integridade", {"system_integrity": integrity_result})

        if run_reparos:
            _print_running_banner("REPAROS AUTOMATIZADOS")
            print(f"  {C.YELLOW}Cada acao requer confirmacao individual.{C.RESET}")
            print()
            repair = RepairModule(logger)
            repair_results = repair.run_all()
            report.add_results("reparos", repair_results)
            _print_module_results("reparos", repair_results)

        # ── Salvar e exibir relatorio ─────────────────────────────────

        logger.info("core", "fim", "Sessao de diagnostico encerrada")
        _save_and_show_report(report, logger)

        # Perguntar se quer continuar
        print(f"  {C.DIM}{_line('-', TERM_WIDTH - 4)}{C.RESET}")
        again = _ask_choice("Voltar ao menu principal? (s/n):", ["s", "n", "S", "N"])
        if again.lower() != "s":
            print()
            print(f"  {C.DIM}Encerrando SysDiag. Ate mais!{C.RESET}")
            print()
            return 0

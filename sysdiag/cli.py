"""
Interface de linha de comando (CLI) do SysDiag.

Ponto de entrada principal da aplicacao. Quando executado sem argumentos,
abre a interface interativa (TUI). Com argumentos, executa em modo direto.
"""

import argparse
import io
import os
import sys
from typing import Optional

from sysdiag.core.os_detect import get_system_info, print_system_info
from sysdiag.core.logger import DiagnosticLogger
from sysdiag.diagnostics.network import NetworkDiagnostic
from sysdiag.diagnostics.hardware import HardwareDiagnostic
from sysdiag.diagnostics.system import SystemDiagnostic
from sysdiag.repairs.repair import RepairModule
from sysdiag.report.report import DiagnosticReport


def create_parser() -> argparse.ArgumentParser:
    """
    Cria o parser de argumentos da CLI.

    Returns:
        ArgumentParser configurado com todas as opcoes.
    """
    parser = argparse.ArgumentParser(
        prog="sysdiag",
        description="SysDiag -- Ferramenta de diagnostico multiplataforma de sistema, rede e hardware.",
        epilog="Exemplos:\n"
               "  sysdiag                       # Interface interativa\n"
               "  sysdiag --direto               # Diagnostico completo (sem menu)\n"
               "  sysdiag --direto -m rede       # Apenas rede (sem menu)\n"
               "  sysdiag --direto --reparar     # Diagnostico + reparos\n"
               "  sysdiag --saida ./meus_logs    # Salvar em diretorio especifico\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--direto", "-d",
        action="store_true",
        default=False,
        help="Executar em modo direto (sem interface interativa).",
    )

    parser.add_argument(
        "--modulo", "-m",
        choices=["rede", "hardware", "sistema", "todos"],
        default="todos",
        help="Modulo de diagnostico a executar (padrao: todos).",
    )

    parser.add_argument(
        "--reparar", "-r",
        action="store_true",
        default=False,
        help="Ativar reparos automatizados (com confirmacao).",
    )

    parser.add_argument(
        "--saida", "-s",
        type=str,
        default=None,
        help="Diretorio de saida para logs e relatorios (padrao: ./logs).",
    )

    parser.add_argument(
        "--formato", "-f",
        choices=["json", "txt", "ambos"],
        default="ambos",
        help="Formato do relatorio de saida (padrao: ambos).",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="8.8.8.8",
        help="Host para testes de rede (padrao: 8.8.8.8).",
    )

    parser.add_argument(
        "--dominio",
        type=str,
        default="google.com",
        help="Dominio para testes DNS (padrao: google.com).",
    )

    parser.add_argument(
        "--integridade",
        action="store_true",
        default=False,
        help="Incluir verificacao de integridade do sistema (requer privilegios, pode demorar).",
    )

    parser.add_argument(
        "--versao", "-v",
        action="version",
        version="SysDiag 1.0.0",
    )

    return parser


def run_direct(opts) -> int:
    """
    Executa diagnostico em modo direto (sem interface interativa).

    Args:
        opts: Argumentos parseados pelo argparse.

    Returns:
        Codigo de saida (0 = sucesso).
    """
    # Garantir encoding UTF-8 no console Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    # Inicializar logger e coletar info do sistema
    logger = DiagnosticLogger(output_dir=opts.saida)
    sys_info = get_system_info()

    print("\n" + "=" * 50)
    print("  SysDiag -- Diagnostico Multiplataforma")
    print("=" * 50)
    print(print_system_info(sys_info))

    logger.info("core", "inicio", "Sessao de diagnostico iniciada", data={
        "os": sys_info.os_name,
        "version": sys_info.version,
        "elevated": sys_info.is_elevated,
    })

    # Preparar relatorio
    report = DiagnosticReport(logger, output_dir=opts.saida)

    # Executar modulos conforme selecao
    modulo = opts.modulo

    if modulo in ("rede", "todos"):
        print("\n>> Executando diagnostico de REDE...")
        net = NetworkDiagnostic(logger)
        net_results = net.run_all(host=opts.host, domain=opts.dominio)
        report.add_results("rede", net_results)
        print("   Diagnostico de rede concluido.")

    if modulo in ("hardware", "todos"):
        print("\n>> Executando diagnostico de HARDWARE...")
        hw = HardwareDiagnostic(logger)
        hw_results = hw.run_all()
        report.add_results("hardware", hw_results)
        print("   Diagnostico de hardware concluido.")

    if modulo in ("sistema", "todos"):
        print("\n>> Executando diagnostico de SISTEMA...")
        sys_diag = SystemDiagnostic(logger)
        sys_results = sys_diag.run_all(check_integrity=opts.integridade)
        report.add_results("sistema", sys_results)
        print("   Diagnostico de sistema concluido.")

    # Reparos (se solicitado)
    if opts.reparar:
        print("\n>> Executando modulo de REPAROS...")
        repair = RepairModule(logger)
        repair_results = repair.run_all()
        report.add_results("reparos", repair_results)
        print("   Modulo de reparos concluido.")

    # Gerar relatorio
    print("\n>> Gerando relatorio...")

    if opts.formato in ("json", "ambos"):
        json_path = report.save_json()
        print(f"   Relatorio JSON: {json_path}")

    if opts.formato in ("txt", "ambos"):
        txt_path = report.save_txt()
        print(f"   Relatorio TXT:  {txt_path}")

    # Salvar logs separados
    log_json = logger.save_json()
    log_txt = logger.save_txt()
    print(f"   Log JSON:       {log_json}")
    print(f"   Log TXT:        {log_txt}")

    # Exibir resumo
    print(report.print_summary())

    logger.info("core", "fim", "Sessao de diagnostico encerrada")

    return 0


def run(args: Optional[list[str]] = None) -> int:
    """
    Funcao principal de execucao do SysDiag.

    Sem argumentos ou sem --direto: abre interface interativa.
    Com --direto: executa em modo direto.

    Args:
        args: Lista de argumentos (se None, usa sys.argv).

    Returns:
        Codigo de saida (0 = sucesso).
    """
    parser = create_parser()
    opts = parser.parse_args(args)

    if opts.direto:
        return run_direct(opts)
    else:
        # Modo interativo
        from sysdiag.tui import interactive_main
        return interactive_main(output_dir=opts.saida)


def main() -> None:
    """Ponto de entrada para o console_scripts."""
    sys.exit(run())

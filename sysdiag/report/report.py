"""
Módulo de geração de relatórios de diagnóstico.

Consolida os dados coletados de todos os módulos e gera relatórios
formatados em JSON e TXT com resumo executivo.
"""

import json
import os
from datetime import datetime
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from sysdiag.core.os_detect import SystemInfo, get_system_info
from sysdiag.core.executor import CommandResult
from sysdiag.core.logger import DiagnosticLogger


class DiagnosticReport:
    """
    Gerador de relatórios consolidados de diagnóstico.

    Recebe resultados de todos os módulos e gera saída formatada
    em JSON e/ou TXT.
    """

    def __init__(self, logger: DiagnosticLogger, output_dir: Optional[str] = None):
        """
        Inicializa o gerador de relatórios.

        Args:
            logger: Instância do DiagnosticLogger com os dados da sessão.
            output_dir: Diretório de saída. Se None, usa 'logs/'.
        """
        self.logger = logger
        self.output_dir = output_dir or os.path.join(os.getcwd(), "logs")
        self.system_info = get_system_info()
        self.results: dict[str, dict] = {}
        self.timestamp = datetime.now()

    def add_results(self, module_name: str, results: dict) -> None:
        """
        Adiciona resultados de um módulo ao relatório.

        Args:
            module_name: Nome do módulo (ex: 'rede', 'hardware', 'sistema').
            results: Dicionário com os resultados do módulo.
        """
        serialized = {}
        for key, value in results.items():
            if isinstance(value, CommandResult):
                serialized[key] = {
                    "command": value.command,
                    "success": value.success,
                    "return_code": value.return_code,
                    "stdout": value.stdout[:2000] if value.stdout else "",
                    "stderr": value.stderr[:500] if value.stderr else "",
                    "duration_ms": value.duration_ms,
                    "error_type": value.error_type,
                }
            elif isinstance(value, dict):
                serialized[key] = value
            else:
                serialized[key] = str(value)

        self.results[module_name] = serialized

    def _build_summary(self) -> dict:
        """
        Gera um resumo executivo do diagnóstico.

        Returns:
            Dicionário com contadores de sucesso/erro por módulo.
        """
        summary = {}
        for module, results in self.results.items():
            success_count = 0
            error_count = 0
            warning_count = 0
            for key, val in results.items():
                if isinstance(val, dict):
                    if val.get("success") is True:
                        success_count += 1
                    elif val.get("success") is False:
                        error_count += 1
                    elif "error" in val:
                        warning_count += 1
            summary[module] = {
                "total_tests": success_count + error_count + warning_count,
                "sucesso": success_count,
                "erros": error_count,
                "avisos": warning_count,
            }
        return summary

    def to_dict(self) -> dict:
        """
        Converte o relatório completo para dicionário.

        Returns:
            Dicionário com todas as informações do relatório.
        """
        return {
            "sysdiag_report": {
                "version": "1.0.0",
                "generated_at": self.timestamp.isoformat(),
                "system_info": asdict(self.system_info),
                "summary": self._build_summary(),
                "results": self.results,
                "log": self.logger.to_dict(),
            }
        }

    def save_json(self, filename: Optional[str] = None) -> str:
        """
        Salva o relatório em formato JSON.

        Args:
            filename: Nome do arquivo. Se None, gera automaticamente.

        Returns:
            Caminho completo do arquivo salvo.
        """
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        if filename is None:
            ts = self.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"relatorio_{ts}.json"

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        return filepath

    def save_txt(self, filename: Optional[str] = None) -> str:
        """
        Salva o relatório em formato texto legível.

        Args:
            filename: Nome do arquivo. Se None, gera automaticamente.

        Returns:
            Caminho completo do arquivo salvo.
        """
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        if filename is None:
            ts = self.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"relatorio_{ts}.txt"

        filepath = os.path.join(self.output_dir, filename)
        summary = self._build_summary()

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("  SysDiag — Relatório de Diagnóstico\n")
            f.write(f"  Gerado em: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            # Informações do sistema
            f.write("─" * 60 + "\n")
            f.write("  INFORMAÇÕES DO SISTEMA\n")
            f.write("─" * 60 + "\n")
            f.write(f"  SO           : {self.system_info.os_display}\n")
            f.write(f"  Versão       : {self.system_info.version}\n")
            f.write(f"  Arquitetura  : {self.system_info.architecture}\n")
            f.write(f"  Hostname     : {self.system_info.hostname}\n")
            f.write(f"  Python       : {self.system_info.python_version}\n")
            f.write(f"  Privilegiado : {'Sim' if self.system_info.is_elevated else 'Não'}\n\n")

            # Resumo executivo
            f.write("─" * 60 + "\n")
            f.write("  RESUMO EXECUTIVO\n")
            f.write("─" * 60 + "\n")
            for module, stats in summary.items():
                status = "OK" if stats["erros"] == 0 else "ATENÇÃO"
                f.write(f"  [{status}] {module.upper()}: "
                        f"{stats['sucesso']} ok / {stats['erros']} erros / {stats['avisos']} avisos\n")
            f.write("\n")

            # Resultados detalhados
            for module, results in self.results.items():
                f.write("─" * 60 + "\n")
                f.write(f"  {module.upper()} — Resultados Detalhados\n")
                f.write("─" * 60 + "\n")

                for test_name, data in results.items():
                    if isinstance(data, dict):
                        success = data.get("success")
                        if success is True:
                            icon = "[OK]"
                        elif success is False:
                            icon = "[ERRO]"
                        else:
                            icon = "[INFO]"

                        f.write(f"\n  {icon} {test_name}\n")

                        if "command" in data:
                            f.write(f"    Comando: {data['command']}\n")
                        if "duration_ms" in data:
                            f.write(f"    Duração: {data['duration_ms']}ms\n")
                        if data.get("stdout"):
                            # Limitar output a 10 linhas no TXT
                            lines = data["stdout"].split("\n")[:10]
                            for line in lines:
                                f.write(f"    | {line}\n")
                            if len(data["stdout"].split("\n")) > 10:
                                f.write(f"    | ... (saída truncada)\n")
                        if data.get("stderr") and data.get("success") is False:
                            f.write(f"    Erro: {data['stderr'][:200]}\n")
                        if data.get("error_type"):
                            f.write(f"    Tipo de erro: {data['error_type']}\n")

                        # Para dicts sem 'command' (ex: disk_usage, dns_resolve)
                        if "command" not in data and "success" not in data:
                            for k, v in data.items():
                                f.write(f"    {k}: {v}\n")

                f.write("\n")

            # Log de operações
            f.write("─" * 60 + "\n")
            f.write("  LOG DE OPERAÇÕES\n")
            f.write("─" * 60 + "\n")
            for entry in self.logger.entries:
                icon = {"sucesso": "[OK]", "erro": "[ERRO]", "aviso": "[!]", "info": "[i]"}.get(entry.status, "[?]")
                f.write(f"  {icon} {entry.timestamp} | {entry.module}/{entry.action}: {entry.message}\n")

            f.write("\n" + "=" * 60 + "\n")
            f.write("  Fim do relatório\n")
            f.write("=" * 60 + "\n")

        return filepath

    def print_summary(self) -> str:
        """
        Gera um resumo para exibição no terminal.

        Returns:
            String formatada com o resumo.
        """
        summary = self._build_summary()
        lines = [
            "",
            "=" * 50,
            "  SysDiag — Resumo do Diagnóstico",
            "=" * 50,
            f"  Sistema: {self.system_info.os_display}",
            f"  Data: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        for module, stats in summary.items():
            status = "[OK]" if stats["erros"] == 0 else "[!!]"
            lines.append(
                f"  {status} {module.upper()}: "
                f"{stats['sucesso']} ok | {stats['erros']} erros | {stats['avisos']} avisos"
            )

        total_errors = sum(s["erros"] for s in summary.values())
        if total_errors == 0:
            lines.append("\n  Resultado: Nenhum problema crítico encontrado.")
        else:
            lines.append(f"\n  Resultado: {total_errors} problema(s) detectado(s). Verifique o relatório completo.")

        lines.append("=" * 50)
        return "\n".join(lines)

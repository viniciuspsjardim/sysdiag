"""
Módulo de logging estruturado do SysDiag.

Registra resultados de diagnósticos, erros e ações de reparo
em arquivos JSON e/ou TXT com timestamp. Mantém um histórico
completo de todas as operações realizadas durante a sessão.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class LogEntry:
    """Entrada individual no log de diagnóstico."""

    timestamp: str
    module: str         # Ex: 'rede', 'hardware', 'sistema', 'reparo'
    action: str         # Ex: 'ping', 'flush_dns', 'cpu_info'
    status: str         # 'sucesso', 'erro', 'aviso', 'info'
    message: str        # Descrição legível do resultado
    data: Optional[dict] = None   # Dados estruturados adicionais
    error: Optional[str] = None   # Mensagem de erro, se houver


class DiagnosticLogger:
    """
    Logger central para registro de todas as operações do SysDiag.

    Armazena entradas em memória e permite exportar para JSON e TXT.
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        Inicializa o logger.

        Args:
            output_dir: Diretório para salvar os logs. Se None, usa o
                        diretório atual com subpasta 'logs'.
        """
        self.entries: list[LogEntry] = []
        self.session_start = datetime.now().isoformat()
        self.output_dir = output_dir or os.path.join(os.getcwd(), "logs")

    def log(
        self,
        module: str,
        action: str,
        status: str,
        message: str,
        data: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> LogEntry:
        """
        Registra uma nova entrada no log.

        Args:
            module: Nome do módulo que gerou o log.
            action: Ação executada.
            status: Status da operação ('sucesso', 'erro', 'aviso', 'info').
            message: Descrição legível do resultado.
            data: Dados estruturados adicionais (opcional).
            error: Mensagem de erro (opcional).

        Returns:
            A entrada de log criada.
        """
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            module=module,
            action=action,
            status=status,
            message=message,
            data=data,
            error=error,
        )
        self.entries.append(entry)
        return entry

    def info(self, module: str, action: str, message: str, data: Optional[dict] = None) -> LogEntry:
        """Atalho para registrar uma entrada informativa."""
        return self.log(module, action, "info", message, data=data)

    def success(self, module: str, action: str, message: str, data: Optional[dict] = None) -> LogEntry:
        """Atalho para registrar uma operação bem-sucedida."""
        return self.log(module, action, "sucesso", message, data=data)

    def warning(self, module: str, action: str, message: str, data: Optional[dict] = None) -> LogEntry:
        """Atalho para registrar um aviso."""
        return self.log(module, action, "aviso", message, data=data)

    def error(self, module: str, action: str, message: str, error_detail: Optional[str] = None) -> LogEntry:
        """Atalho para registrar um erro."""
        return self.log(module, action, "erro", message, error=error_detail)

    def get_entries(self, module: Optional[str] = None, status: Optional[str] = None) -> list[LogEntry]:
        """
        Retorna entradas filtradas por módulo e/ou status.

        Args:
            module: Filtrar por nome do módulo (opcional).
            status: Filtrar por status (opcional).

        Returns:
            Lista de entradas que correspondem aos filtros.
        """
        result = self.entries
        if module:
            result = [e for e in result if e.module == module]
        if status:
            result = [e for e in result if e.status == status]
        return result

    def to_dict(self) -> dict:
        """
        Converte todo o log para um dicionário serializável.

        Returns:
            Dicionário com metadados da sessão e lista de entradas.
        """
        return {
            "session_start": self.session_start,
            "session_end": datetime.now().isoformat(),
            "total_entries": len(self.entries),
            "entries": [asdict(e) for e in self.entries],
        }

    def save_json(self, filename: Optional[str] = None) -> str:
        """
        Salva o log completo em formato JSON.

        Args:
            filename: Nome do arquivo (sem caminho). Se None, gera
                      automaticamente com timestamp.

        Returns:
            Caminho completo do arquivo salvo.
        """
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sysdiag_{ts}.json"

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        return filepath

    def save_txt(self, filename: Optional[str] = None) -> str:
        """
        Salva o log completo em formato texto legível.

        Args:
            filename: Nome do arquivo (sem caminho). Se None, gera
                      automaticamente com timestamp.

        Returns:
            Caminho completo do arquivo salvo.
        """
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sysdiag_{ts}.txt"

        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("  SysDiag — Relatório de Diagnóstico\n")
            f.write(f"  Sessão iniciada em: {self.session_start}\n")
            f.write("=" * 60 + "\n\n")

            for entry in self.entries:
                status_icon = {
                    "sucesso": "[OK]",
                    "erro": "[ERRO]",
                    "aviso": "[AVISO]",
                    "info": "[INFO]",
                }.get(entry.status, "[?]")

                f.write(f"{status_icon} [{entry.timestamp}] {entry.module}/{entry.action}\n")
                f.write(f"  {entry.message}\n")
                if entry.error:
                    f.write(f"  Erro: {entry.error}\n")
                if entry.data:
                    for k, v in entry.data.items():
                        f.write(f"  {k}: {v}\n")
                f.write("\n")

            f.write("=" * 60 + "\n")
            f.write(f"  Total de entradas: {len(self.entries)}\n")
            f.write(f"  Sessão encerrada em: {datetime.now().isoformat()}\n")
            f.write("=" * 60 + "\n")

        return filepath

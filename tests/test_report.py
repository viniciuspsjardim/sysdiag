"""Testes unitários para o módulo de relatórios."""

import json
import os
import tempfile

from sysdiag.core.logger import DiagnosticLogger, LogEntry
from sysdiag.core.executor import CommandResult
from sysdiag.report.report import DiagnosticReport


class TestDiagnosticLogger:
    """Testes para o DiagnosticLogger."""

    def setup_method(self):
        """Configura logger com diretório temporário."""
        self.tmpdir = tempfile.mkdtemp()
        self.logger = DiagnosticLogger(output_dir=self.tmpdir)

    def test_log_entry(self):
        """Deve registrar uma entrada de log."""
        entry = self.logger.log("rede", "ping", "sucesso", "Ping OK")
        assert isinstance(entry, LogEntry)
        assert entry.module == "rede"
        assert entry.status == "sucesso"

    def test_log_shortcuts(self):
        """Atalhos devem criar entradas com status correto."""
        self.logger.info("hw", "cpu", "Info CPU")
        self.logger.success("hw", "mem", "Memória OK")
        self.logger.warning("hw", "temp", "Temp alta")
        self.logger.error("hw", "disco", "Disco falhou", error_detail="I/O Error")

        entries = self.logger.entries
        assert entries[0].status == "info"
        assert entries[1].status == "sucesso"
        assert entries[2].status == "aviso"
        assert entries[3].status == "erro"
        assert entries[3].error == "I/O Error"

    def test_filter_by_module(self):
        """Deve filtrar entradas por módulo."""
        self.logger.info("rede", "ping", "OK")
        self.logger.info("hardware", "cpu", "OK")
        self.logger.info("rede", "dns", "OK")

        rede = self.logger.get_entries(module="rede")
        assert len(rede) == 2

    def test_filter_by_status(self):
        """Deve filtrar entradas por status."""
        self.logger.success("a", "b", "OK")
        self.logger.error("a", "c", "Falhou")
        self.logger.success("a", "d", "OK")

        errors = self.logger.get_entries(status="erro")
        assert len(errors) == 1

    def test_to_dict(self):
        """Deve converter log para dicionário."""
        self.logger.info("test", "x", "msg")
        d = self.logger.to_dict()
        assert "session_start" in d
        assert "entries" in d
        assert len(d["entries"]) == 1

    def test_save_json(self):
        """Deve salvar arquivo JSON válido."""
        self.logger.info("test", "x", "msg")
        path = self.logger.save_json()
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_entries"] == 1

    def test_save_txt(self):
        """Deve salvar arquivo TXT legível."""
        self.logger.success("rede", "ping", "Ping OK")
        path = self.logger.save_txt()
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "SysDiag" in content
        assert "[OK]" in content


class TestDiagnosticReport:
    """Testes para o DiagnosticReport."""

    def setup_method(self):
        """Configura relatório com diretório temporário."""
        self.tmpdir = tempfile.mkdtemp()
        self.logger = DiagnosticLogger(output_dir=self.tmpdir)
        self.report = DiagnosticReport(self.logger, output_dir=self.tmpdir)

    def test_add_results_with_command_result(self):
        """Deve serializar CommandResult corretamente."""
        cr = CommandResult(
            command="ping 127.0.0.1",
            return_code=0,
            stdout="Reply from 127.0.0.1",
            stderr="",
            success=True,
            timestamp="2024-01-01T00:00:00",
            duration_ms=150.5,
            platform="windows",
        )
        self.report.add_results("rede", {"ping": cr})
        assert "rede" in self.report.results
        assert self.report.results["rede"]["ping"]["success"] is True

    def test_add_results_with_dict(self):
        """Deve aceitar dicionários simples."""
        self.report.add_results("hardware", {"disk_usage": {"total_gb": 500, "free_gb": 200}})
        assert self.report.results["hardware"]["disk_usage"]["total_gb"] == 500

    def test_to_dict(self):
        """Deve gerar dicionário completo do relatório."""
        d = self.report.to_dict()
        assert "sysdiag_report" in d
        assert "system_info" in d["sysdiag_report"]
        assert "summary" in d["sysdiag_report"]

    def test_save_json(self):
        """Deve salvar relatório JSON válido."""
        self.report.add_results("rede", {"test": {"success": True}})
        path = self.report.save_json()
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "sysdiag_report" in data

    def test_save_txt(self):
        """Deve salvar relatório TXT legível."""
        cr = CommandResult(
            command="ping", return_code=0, stdout="OK", stderr="",
            success=True, timestamp="", duration_ms=10, platform="windows",
        )
        self.report.add_results("rede", {"ping": cr})
        path = self.report.save_txt()
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "REDE" in content

    def test_print_summary(self):
        """Deve gerar resumo formatado."""
        self.report.add_results("rede", {
            "ping": {"success": True},
            "dns": {"success": False},
        })
        summary = self.report.print_summary()
        assert "REDE" in summary
        assert "1 ok" in summary
        assert "1 erros" in summary

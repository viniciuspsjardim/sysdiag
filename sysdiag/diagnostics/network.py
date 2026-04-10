"""
Módulo de diagnóstico de rede.

Executa testes de conectividade, resolução DNS, verificação de portas,
traceroute e coleta informações sobre interfaces de rede.
Adapta os comandos automaticamente para cada plataforma.
"""

import socket
from typing import Optional

from sysdiag.core.executor import run_platform_command, run_command, CommandResult
from sysdiag.core.logger import DiagnosticLogger
from sysdiag.core.os_detect import detect_os


class NetworkDiagnostic:
    """
    Classe principal para diagnósticos de rede.

    Todos os métodos registram resultados no logger fornecido
    e retornam o CommandResult para uso programático.
    """

    MODULE = "rede"

    def __init__(self, logger: DiagnosticLogger):
        """
        Inicializa o módulo de diagnóstico de rede.

        Args:
            logger: Instância do DiagnosticLogger para registro.
        """
        self.logger = logger
        self.os_name = detect_os()

    def ping(self, host: str = "8.8.8.8", count: int = 4, timeout: int = 30) -> CommandResult:
        """
        Executa ping para o host especificado.

        Args:
            host: Endereço IP ou hostname (padrão: DNS do Google).
            count: Número de pacotes a enviar.
            timeout: Tempo máximo em segundos.

        Returns:
            CommandResult com a saída do ping.
        """
        if self.os_name == "windows":
            cmd = ["ping", "-n", str(count), host]
        else:
            cmd = ["ping", "-c", str(count), host]

        result = run_command(cmd, timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "ping", f"Ping para {host}: OK", data={"host": host})
        else:
            self.logger.error(self.MODULE, "ping", f"Ping para {host}: falhou", error_detail=result.stderr)

        return result

    def traceroute(self, host: str = "8.8.8.8", timeout: int = 120) -> CommandResult:
        """
        Executa traceroute para o host especificado.

        Args:
            host: Endereço IP ou hostname de destino.
            timeout: Tempo máximo em segundos.

        Returns:
            CommandResult com a saída do traceroute.
        """
        result = run_platform_command("traceroute", extra_args=[host], timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "traceroute", f"Traceroute para {host}: completo")
        else:
            self.logger.warning(self.MODULE, "traceroute", f"Traceroute para {host}: incompleto ou falhou",
                                data={"error": result.stderr})

        return result

    def dns_lookup(self, domain: str = "google.com", timeout: int = 30) -> CommandResult:
        """
        Realiza consulta DNS para o domínio especificado.

        Args:
            domain: Domínio a consultar.
            timeout: Tempo máximo em segundos.

        Returns:
            CommandResult com a saída da consulta DNS.
        """
        result = run_platform_command("dns_lookup", extra_args=[domain], timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "dns_lookup", f"Resolução DNS para {domain}: OK")
        else:
            self.logger.error(self.MODULE, "dns_lookup", f"Resolução DNS para {domain}: falhou",
                              error_detail=result.stderr)

        return result

    def dns_resolve_python(self, domain: str = "google.com") -> dict:
        """
        Realiza resolução DNS usando a stdlib do Python (socket).

        Funciona em qualquer plataforma sem depender de ferramentas externas.

        Args:
            domain: Domínio a resolver.

        Returns:
            Dicionário com hostname, aliases e endereços IP.
        """
        try:
            hostname, aliases, addresses = socket.gethostbyname_ex(domain)
            result = {
                "hostname": hostname,
                "aliases": aliases,
                "addresses": addresses,
            }
            self.logger.success(self.MODULE, "dns_resolve", f"Resolução de {domain}: {addresses}")
            return result
        except socket.gaierror as e:
            self.logger.error(self.MODULE, "dns_resolve", f"Falha ao resolver {domain}", error_detail=str(e))
            return {"hostname": domain, "aliases": [], "addresses": [], "error": str(e)}

    def get_interfaces(self, timeout: int = 30) -> CommandResult:
        """
        Lista as interfaces de rede e seus endereços.

        Returns:
            CommandResult com a saída de ipconfig/ip addr/ifconfig.
        """
        result = run_platform_command("ip_config", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "interfaces", "Interfaces de rede coletadas com sucesso")
        else:
            self.logger.error(self.MODULE, "interfaces", "Falha ao coletar interfaces",
                              error_detail=result.stderr)

        return result

    def get_open_ports(self, timeout: int = 30) -> CommandResult:
        """
        Lista as portas abertas e conexões ativas.

        Returns:
            CommandResult com a saída de netstat/ss.
        """
        result = run_platform_command("open_ports", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "portas", "Portas abertas coletadas com sucesso")
        else:
            self.logger.error(self.MODULE, "portas", "Falha ao coletar portas abertas",
                              error_detail=result.stderr)

        return result

    def check_port(self, host: str, port: int, timeout: int = 5) -> bool:
        """
        Verifica se uma porta específica está acessível em um host.

        Usa socket puro do Python, funciona em qualquer plataforma.

        Args:
            host: Endereço IP ou hostname.
            port: Número da porta.
            timeout: Tempo máximo de espera em segundos.

        Returns:
            True se a porta estiver acessível.
        """
        try:
            with socket.create_connection((host, port), timeout=timeout):
                self.logger.success(self.MODULE, "check_port",
                                    f"Porta {port} em {host}: aberta",
                                    data={"host": host, "port": port})
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            self.logger.warning(self.MODULE, "check_port",
                                f"Porta {port} em {host}: fechada ou inacessível",
                                data={"host": host, "port": port})
            return False

    # ── Diagnósticos Wi-Fi ──────────────────────────────────────────────────

    def wifi_report(self, timeout: int = 30) -> CommandResult:
        """
        Gera relatorio completo de Wi-Fi.

        Windows: netsh wlan show wlanreport (gera HTML em ProgramData).
        Linux  : nmcli device wifi list (redes disponiveis).
        macOS  : system_profiler SPAirPortDataType.

        Returns:
            CommandResult com a saida do relatorio Wi-Fi.
        """
        result = run_platform_command("wifi_report", timeout=timeout)

        if result.success:
            msg = "Relatorio Wi-Fi gerado com sucesso"
            # No Windows, informar onde o HTML foi salvo
            if self.os_name == "windows":
                html_path = r"C:\ProgramData\Microsoft\Windows\WlanReport\wlan-report-latest.html"
                msg += f" (HTML: {html_path})"
            self.logger.success(self.MODULE, "wifi_report", msg)
        else:
            self.logger.warning(
                self.MODULE, "wifi_report",
                "Falha ao gerar relatorio Wi-Fi (adaptador ausente ou Wi-Fi desativado)",
                data={"error": result.stderr},
            )

        return result

    def wifi_interfaces(self, timeout: int = 15) -> CommandResult:
        """
        Mostra estado atual da interface Wi-Fi.

        Windows: netsh wlan show interfaces (SSID, sinal, banda, canal).
        Linux  : iw dev (interfaces wireless detectadas).
        macOS  : airport -I (conexao atual, RSSI, canal).

        Returns:
            CommandResult com informacoes da interface wireless.
        """
        result = run_platform_command("wifi_interfaces", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "wifi_interfaces",
                                "Interfaces Wi-Fi coletadas com sucesso")
        else:
            self.logger.warning(self.MODULE, "wifi_interfaces",
                                "Falha ao coletar interfaces Wi-Fi (adaptador wireless nao encontrado)",
                                data={"error": result.stderr})

        return result

    def wifi_profiles(self, timeout: int = 15) -> CommandResult:
        """
        Lista perfis de rede Wi-Fi salvos no sistema.

        Windows: netsh wlan show profiles.
        Linux  : nmcli connection show.
        macOS  : networksetup -listpreferredwirelessnetworks en0.

        Returns:
            CommandResult com a lista de perfis Wi-Fi.
        """
        result = run_platform_command("wifi_profiles", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "wifi_profiles",
                                "Perfis Wi-Fi coletados com sucesso")
        else:
            self.logger.warning(self.MODULE, "wifi_profiles",
                                "Falha ao listar perfis Wi-Fi",
                                data={"error": result.stderr})

        return result

    def wifi_drivers(self, timeout: int = 15) -> CommandResult:
        """
        Mostra informacoes do driver do adaptador wireless.

        Windows: netsh wlan show drivers.
        Linux  : lspci -k (filtra dispositivos de rede).
        macOS  : system_profiler SPAirPortDataType.

        Returns:
            CommandResult com informacoes do driver Wi-Fi.
        """
        result = run_platform_command("wifi_drivers", timeout=timeout)

        if result.success:
            self.logger.success(self.MODULE, "wifi_drivers",
                                "Informacoes do driver Wi-Fi coletadas")
        else:
            self.logger.warning(self.MODULE, "wifi_drivers",
                                "Falha ao coletar informacoes do driver Wi-Fi",
                                data={"error": result.stderr})

        return result

    def wifi_run_all(self) -> dict[str, CommandResult]:
        """
        Executa todos os diagnosticos Wi-Fi disponiveis.

        Returns:
            Dicionario com resultados de cada teste Wi-Fi.
        """
        self.logger.info(self.MODULE, "wifi_inicio",
                         "Iniciando diagnostico completo de Wi-Fi")

        results = {
            "wifi_interfaces": self.wifi_interfaces(),
            "wifi_profiles": self.wifi_profiles(),
            "wifi_drivers": self.wifi_drivers(),
            "wifi_report": self.wifi_report(),
        }

        self.logger.info(self.MODULE, "wifi_fim",
                         "Diagnostico de Wi-Fi concluido")
        return results

    # ── Diagnostico manual de dominio ────────────────────────────────────

    def manual_ping(
        self,
        target: str,
        count: int = 10,
        timeout: int = 60,
    ) -> CommandResult:
        """
        Executa ping estendido para um alvo especifico (dominio ou IP).

        Usa contagem maior que o padrao para capturar melhor a estabilidade
        da conexao, incluindo jitter e perda de pacotes.

        Args:
            target: Dominio ou IP de destino.
            count: Numero de pacotes (padrao: 10 para analise detalhada).
            timeout: Tempo maximo em segundos.

        Returns:
            CommandResult com a saida completa do ping.
        """
        if self.os_name == "windows":
            cmd = ["ping", "-n", str(count), target]
        else:
            cmd = ["ping", "-c", str(count), target]

        result = run_command(cmd, timeout=timeout)

        if result.success:
            self.logger.success(
                self.MODULE, "manual_ping",
                f"Ping estendido para {target}: OK ({count} pacotes)",
                data={"target": target, "count": count},
            )
        else:
            self.logger.error(
                self.MODULE, "manual_ping",
                f"Ping estendido para {target}: falhou",
                error_detail=result.stderr,
            )

        return result

    def manual_traceroute(
        self,
        target: str,
        timeout: int = 180,
    ) -> CommandResult:
        """
        Executa traceroute detalhado para um alvo especifico.

        Args:
            target: Dominio ou IP de destino.
            timeout: Tempo maximo em segundos (padrao maior para rotas longas).

        Returns:
            CommandResult com a saida completa do traceroute.
        """
        result = run_platform_command(
            "traceroute", extra_args=[target], timeout=timeout,
        )

        if result.success:
            # Contar numero de saltos
            hops = len([
                l for l in result.stdout.splitlines()
                if l.strip() and l.strip()[0].isdigit()
            ])
            self.logger.success(
                self.MODULE, "manual_traceroute",
                f"Traceroute para {target}: completo ({hops} saltos)",
                data={"target": target, "hops": hops},
            )
        else:
            self.logger.error(
                self.MODULE, "manual_traceroute",
                f"Traceroute para {target}: falhou ou timeout",
                error_detail=result.stderr,
            )

        return result

    def manual_dns(self, target: str, timeout: int = 15) -> dict:
        """
        Resolucao DNS completa para um dominio: via ferramenta nativa + Python.

        Args:
            target: Dominio a resolver.
            timeout: Tempo maximo em segundos.

        Returns:
            Dicionario com resultados de ambas as resolucoes.
        """
        # Resolucao via ferramenta nativa (nslookup/dig)
        native = run_platform_command("dns_lookup", extra_args=[target], timeout=timeout)

        if native.success:
            self.logger.success(
                self.MODULE, "manual_dns_native",
                f"DNS nativo para {target}: OK",
            )
        else:
            self.logger.error(
                self.MODULE, "manual_dns_native",
                f"DNS nativo para {target}: falhou",
                error_detail=native.stderr,
            )

        # Resolucao via Python
        python_result = self.dns_resolve_python(target)

        return {
            "native": native,
            "python": python_result,
        }

    def manual_port_scan(
        self,
        target: str,
        ports: list[int] | None = None,
        timeout_per_port: int = 3,
    ) -> dict:
        """
        Verifica as portas mais comuns em um alvo especifico.

        Args:
            target: Dominio ou IP de destino.
            ports: Lista de portas (padrao: portas web/mail/ftp comuns).
            timeout_per_port: Timeout por porta em segundos.

        Returns:
            Dicionario com status de cada porta verificada.
        """
        if ports is None:
            ports = [21, 22, 25, 53, 80, 443, 993, 3306, 3389, 8080, 8443]

        results = {}
        for port in ports:
            is_open = self.check_port(target, port, timeout=timeout_per_port)
            results[port] = is_open

        open_ports = [p for p, s in results.items() if s]
        closed_ports = [p for p, s in results.items() if not s]

        self.logger.info(
            self.MODULE, "manual_port_scan",
            f"Scan em {target}: {len(open_ports)} abertas, {len(closed_ports)} fechadas",
            data={
                "target": target,
                "open": open_ports,
                "closed": closed_ports,
            },
        )

        return {
            "target": target,
            "open_ports": open_ports,
            "closed_ports": closed_ports,
            "details": results,
        }

    def manual_domain_diagnostic(
        self,
        target: str,
        ping_count: int = 10,
        scan_ports: bool = True,
    ) -> dict:
        """
        Executa diagnostico completo focado em um dominio/IP especifico.

        Combina ping estendido, traceroute, resolucao DNS e scan de portas
        em um unico fluxo, gerando dados suficientes para identificar onde
        esta o problema de conectividade.

        Args:
            target: Dominio ou IP a diagnosticar.
            ping_count: Numero de pacotes no ping estendido.
            scan_ports: Se True, verifica portas comuns.

        Returns:
            Dicionario com resultados de todos os testes.
        """
        self.logger.info(
            self.MODULE, "manual_inicio",
            f"Iniciando diagnostico manual para: {target}",
            data={"target": target},
        )

        results: dict = {}

        # 1. Resolucao DNS
        results["dns"] = self.manual_dns(target)

        # 2. Ping estendido
        results["ping"] = self.manual_ping(target, count=ping_count)

        # 3. Traceroute
        results["traceroute"] = self.manual_traceroute(target)

        # 4. Scan de portas
        if scan_ports:
            results["port_scan"] = self.manual_port_scan(target)

        self.logger.info(
            self.MODULE, "manual_fim",
            f"Diagnostico manual para {target} concluido",
        )

        return results

    # ── Execucao completa ─────────────────────────────────────────────────

    def run_all(self, host: str = "8.8.8.8", domain: str = "google.com") -> dict[str, CommandResult | dict]:
        """
        Executa todos os diagnósticos de rede disponíveis (incluindo Wi-Fi).

        Args:
            host: Host para testes de conectividade.
            domain: Domínio para testes DNS.

        Returns:
            Dicionário com os resultados de cada diagnóstico.
        """
        self.logger.info(self.MODULE, "inicio", "Iniciando diagnóstico completo de rede")

        results = {
            "ping": self.ping(host),
            "dns_lookup": self.dns_lookup(domain),
            "dns_resolve": self.dns_resolve_python(domain),
            "interfaces": self.get_interfaces(),
            "open_ports": self.get_open_ports(),
        }

        # Traceroute pode demorar
        results["traceroute"] = self.traceroute(host)

        # Wi-Fi
        wifi = self.wifi_run_all()
        results.update(wifi)

        self.logger.info(self.MODULE, "fim", "Diagnóstico de rede concluído")
        return results

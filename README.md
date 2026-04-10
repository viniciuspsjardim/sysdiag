# SysDiag — Ferramenta de Diagnóstico Multiplataforma

Ferramenta de diagnóstico de sistema, rede e hardware via linha de comando. Detecta automaticamente o sistema operacional (Windows, macOS e Linux) e adapta os comandos utilizados.

## Funcionalidades

- **Detecção de SO**: Identifica automaticamente o sistema operacional, versão e arquitetura
- **Diagnóstico de Rede**: ping, traceroute, DNS, portas abertas, interfaces de rede
- **Diagnóstico de Hardware**: CPU, memória RAM, disco, temperatura (quando disponível)
- **Diagnóstico de Sistema**: processos, serviços, logs de erros, integridade de arquivos
- **Reparos Automatizados**: flush DNS, limpeza de cache, verificação de disco, reset de rede
- **Relatórios**: Geração de relatórios em JSON e TXT com timestamp

## Requisitos

- Python 3.9 ou superior
- Nenhuma dependência externa obrigatória (usa apenas a biblioteca padrão)
- pytest (opcional, para testes)

## Instalação

```bash
# Clonar o repositório
git clone <url-do-repositorio>
cd sysdiag

# Instalar em modo desenvolvimento
pip install -e .

# Ou instalar com dependências de desenvolvimento
pip install -e ".[dev]"
```

## Uso

### Execução básica (diagnóstico completo)

```bash
# Via módulo Python
python -m sysdiag

# Ou via console script (após instalação)
sysdiag
```

### Opções disponíveis

```
Uso: sysdiag [opções]

Opções:
  --modulo, -m {rede,hardware,sistema,todos}
                        Módulo de diagnóstico a executar (padrão: todos)
  --reparar, -r         Ativar reparos automatizados (com confirmação)
  --saida, -s DIRETÓRIO Diretório de saída para logs e relatórios
  --formato, -f {json,txt,ambos}
                        Formato do relatório de saída (padrão: ambos)
  --host HOST           Host para testes de rede (padrão: 8.8.8.8)
  --dominio DOMÍNIO     Domínio para testes DNS (padrão: google.com)
  --integridade         Verificação de integridade do sistema (requer privilégios)
  --versao, -v          Exibir versão
```

### Exemplos

```bash
# Apenas diagnóstico de rede
sysdiag --modulo rede

# Diagnóstico de hardware com saída em JSON
sysdiag --modulo hardware --formato json

# Diagnóstico completo com reparos
sysdiag --reparar

# Salvar relatórios em diretório específico
sysdiag --saida ./meus_relatorios

# Testar conectividade com host e domínio específicos
sysdiag --modulo rede --host 1.1.1.1 --dominio cloudflare.com

# Verificação de integridade (requer privilégios)
sudo sysdiag --integridade       # Linux/macOS
# Executar como Administrador no Windows
```

## Estrutura do Projeto

```
sysdiag/
├── sysdiag/
│   ├── __init__.py          # Pacote principal
│   ├── __main__.py          # Entrada via python -m sysdiag
│   ├── cli.py               # Interface de linha de comando
│   ├── core/
│   │   ├── os_detect.py     # Detecção de SO
│   │   ├── executor.py      # Execução de comandos
│   │   └── logger.py        # Logging estruturado
│   ├── diagnostics/
│   │   ├── network.py       # Diagnóstico de rede
│   │   ├── hardware.py      # Diagnóstico de hardware
│   │   └── system.py        # Diagnóstico de sistema
│   ├── repairs/
│   │   └── repair.py        # Reparos automatizados
│   └── report/
│       └── report.py        # Geração de relatórios
├── tests/                   # Testes unitários
├── examples/                # Exemplos de relatórios
├── pyproject.toml           # Configuração do projeto
└── README.md
```

## Executando Testes

```bash
# Instalar pytest
pip install pytest

# Executar todos os testes
pytest

# Executar com output detalhado
pytest -v

# Executar testes de um módulo específico
pytest tests/test_os_detect.py
```

## Ferramentas por Plataforma

| Função         | Windows                     | Linux                    | macOS                      |
|----------------|-----------------------------|--------------------------|-----------------------------|
| IP/Interfaces  | `ipconfig /all`             | `ip addr`                | `ifconfig`                  |
| Ping           | `ping -n`                   | `ping -c`                | `ping -c`                   |
| Traceroute     | `tracert`                   | `traceroute`             | `traceroute`                |
| DNS            | `nslookup`                  | `dig`                    | `dig`                       |
| Portas         | `netstat -an`               | `ss -tulnp`              | `netstat -an`               |
| CPU            | `wmic cpu`                  | `lscpu`                  | `sysctl`                    |
| Memória        | `wmic memorychip`           | `free -h`                | `vm_stat`                   |
| Disco          | `wmic diskdrive`            | `df -h`                  | `df -h`                     |
| Processos      | `tasklist`                  | `ps aux`                 | `ps aux`                    |
| Logs de erro   | `Get-EventLog`              | `journalctl`             | `log show`                  |
| Flush DNS      | `ipconfig /flushdns`        | `resolvectl flush-caches`| `dscacheutil -flushcache`   |
| Verificar disco| `chkdsk`                    | `fsck -n`                | `diskutil verifyVolume`     |
| Integridade    | `sfc /scannow`              | `journalctl -p err`      | `log show (error)`          |

## Segurança

- Reparos nunca são executados sem confirmação explícita do usuário
- Comandos que requerem privilégios elevados informam o usuário
- Todas as exceções de subprocesso são tratadas (timeout, permissão, comando não encontrado)
- Nenhum dado é enviado para servidores externos

## Licença

MIT

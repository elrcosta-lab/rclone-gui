# Rclone GUI

Interface gráfica para **rclone** — gerencie remotos, sincronize arquivos, monte drives virtuais e verifique integridade, tudo sem abrir o terminal.

Inspirado no Google Drive for desktop, roda como daemon de background com ícone no tray, scheduler de jobs e notificações do sistema.

## Funcionalidades

| Feature | Descrição |
|---------|-----------|
| **Wizard de Remotos** | Adicione qualquer backend suportado pelo rclone (~50+) via assistente visual com busca, formulários dinâmicos e OAuth delegado |
| **Explorador Two-Panel** | Navegue entre sistema local e remotos com dois painéis lado a lado, cópia e movimentação por arrasto |
| **Jobs de Sincronização** | Crie e agende jobs `sync`, `copy`, `move` e `bisync` com flags customizadas, dry-run, filtros e histórico de execução |
| **Montagem VFS (FUSE)** | Monte remotos como pastas locais com cache configurável e montagem automática no login |
| **Transferências One-Shot** | Copie ou mova arquivos/pastas entre qualquer origem e destino sem criar job persistente |
| **Verificação de Integridade** | Compare origem e destino com `rclone check`, exporte relatório de diferenças |
| **Daemon + Tray** | Processo em background com scheduler de jobs, monitoramento de mounts e notificações |
| **Tema Escuro** | Interface Catppuccin Mocha — escuro por padrão, consistente e confortável |

## Stack

- **Python 3.10+** — runtime
- **PySide6** — interface gráfica Qt
- **SQLite (WAL)** — persistência local (jobs, histórico, config)
- **croniter** — parsing e validação de expressões cron
- **rclone** — engine de transferências (subprocess + RC API)

## Pré-requisitos

- **rclone ≥ 1.60** no PATH ([instalação oficial](https://rclone.org/install/))
- **Python 3.10+**
- **FUSE** (para montagem de remotos): `sudo apt install fuse3` (Debian/Ubuntu)

## Instalação e Uso

```bash
git clone https://github.com/elrcosta-lab/rclone-gui.git
cd rclone-gui
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Modo GUI (janela principal)
python3 -m rclone_gui

# Modo daemon (tray + scheduler em background)
python3 -m rclone_gui --daemon
```

## Testes

```bash
source .venv/bin/activate
pip install -e ".[test]"

# Todos os testes
python3 -m pytest -v

# Por nível
python3 -m pytest tests/unit/ -v
python3 -m pytest tests/integration/ -v
python3 -m pytest tests/contract/ -v
python3 -m pytest tests/regression/ -v

# E2E (Qt offscreen)
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/e2e/ -v
```

## Estrutura

```
rclone_gui/
├── __main__.py          # Entry point (GUI ou --daemon)
├── db/database.py       # SQLite (WAL, migrações)
├── models/              # Dataclasses (remote, job, mount)
├── services/
│   ├── rclone_service.py  # Subprocess + RC API + catálogo backends
│   └── job_service.py     # Persistência e execução de jobs
├── daemon/
│   ├── daemon_app.py    # Gerenciamento rcd + scheduler
│   └── tray_manager.py  # QSystemTrayIcon + menu
├── gui/
│   ├── main_window.py   # Sidebar + 8 páginas navegáveis
│   ├── remote/          # Listagem + wizard de configuração
│   ├── explorer/        # Two-panel browser (local/remoto)
│   ├── jobs/            # Editor + histórico de jobs
│   ├── mount/           # Diálogo de montagem VFS
│   ├── transfer/        # Transferência one-shot
│   ├── verification/    # Check + hash + export CSV
│   └── settings/        # Preferências globais
└── resources/backends.json  # Catálogo de 22 backends

tests/
├── unit/       # 53 testes — models, DB mockado, service mockado
├── integration/ # 13 testes — JobService + DB + scheduler
├── contract/   # 26 testes — formato I/O rclone, schema DB, flags CLI
├── regression/ # 23 testes — fields, DB, backends, edge cases
└── e2e/        # 17 testes — app startup, navegação, fluxos completos
```

## Licença

MIT

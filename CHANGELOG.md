# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/spec/v2.0.0.html).

## [0.3.0] — 2026-07-05

### Corrigido
- **Sync folders não sincronizavam na primeira execução**: `sync_now()` não passava `--resync`, necessário quando diretório local está vazio e remoto populado. Agora passa `resync=True` automaticamente na primeira sincronização (`last_sync_at is None`).
- **SyncFolderManager não disparava sync inicial**: ao iniciar uma pasta monitorada, o manager agora chama `request_sync()` via `QTimer.singleShot(0)` para sincronizar imediatamente, sem depender do primeiro tick do poller (5 min).
- **SyncFolderList não carregava dados ao iniciar**: `refresh()` não era chamado no `__init__`, então o painel ficava vazio até o usuário adicionar/editar/remover. Configurações existentes no banco não apareciam na GUI.
- **`--conflict-resolve` quebrava no rclone v1.60**: flag adicionada na v1.63. `bisync()` agora só passa `--conflict-resolve` quando `conflict_resolution` não for vazio; default do model alterado de `"newer"` para `""`.
- **`remote_path` sem `:` não funcionava**: `list_remotes()` remove o `:` do final do remote, mas o rclone precisa do `:` para reconhecer como remote. `register()` e `sync_now()` agora normalizam o `remote_path` adicionando `:` se ausente.

### Adicionado
- **RF-16 — Pastas de Sincronização (Sync Folders)**: pastas locais sincronizadas bidirecionalmente com remotos via `rclone bisync`
- `SyncFolderConfig` model + `sync_folders` table no SQLite (migração v2) com CRUD completo
- `SyncFolderService`: register, get_all, get_enabled, set_enabled, unregister, sync_now
- `RcloneService.bisync()` — novo método com `--conflict-resolve`, `--resync` e flags arbitrárias
- `SyncFolderWatcher`: detecção de alterações locais via inotify (watchdog) com debounce e ponte QSignal (cross-thread)
- `SyncFolderPoller`: polling periódico via QTimer com suporte a suppress (debounce sobrepõe polling)
- `SyncFolderManager`: orquestrador `_ManagedFolder` (watcher + poller + sync) integrado ao DaemonApp
- `DaemonApp` migrado para `QCoreApplication` + `QTimer` heartbeat (substitui blocking loop)
- GUI `SyncFolderList` + `SyncFolderEditor` (dialog): página no sidebar com Add/Edit/Remove/Sync Now
- Tray submenu "Sync Folders" com status e atalho para sincronizar
- First-run wizard: cria `~/RcloneSync/` e exibe boas-vindas
- Bisync flags no JobEditor: `--resync`, `--conflict-resolve`, `--workgroup` (ativo apenas para tipo bisync)
- **Unificação GUI/Daemon/Tray**: `RcloneGUI` (`__main__.py`) inicia daemon (rcd, scheduler, sync folders) + tray no mesmo processo; janela só abre quando usuário clica no tray
- `MainWindow` aceita serviços injetados (`rclone`, `job_service`, `sync_folder_service`, `tray`)
- `_check_rclone()` aprimorado: pergunta se deseja instalar rclone via `curl rclone.org/install.sh | sudo bash`
- **Empacotamento .deb**: `scripts/build-deb.sh` (fpm), `postinst.sh`, `prerm.sh`, desktop files, ícone SVG
- 22 novos testes unitários (model, service, watcher, poller, manager)

### Alterado
- `pyproject.toml`: dependência `watchdog>=3.0` adicionada
- `rclone_gui/daemon/daemon_app.py`: blocking loop substituído por QCoreApplication + QTimer heartbeat; integra SyncFolderManager
- `rclone_gui/gui/main_window.py`: sidebar ganha página "Sync Folders" (índice 5, desloca Verificação→6, Transferir→7, Preferências→8); `closeEvent` não limpa mais tray/db
- `rclone_gui/daemon/tray_manager.py`: novo signal `sync_folder_triggered`, submenu Sync Folders com status, `parent` opcional
- `rclone_gui/__main__.py`: modo padrão inicia `RcloneGUI` (daemon + tray + lazy window); `--daemon` mantido para headless
- 192 testes passando (anteriormente: 86 unit + 26 contract + 13 integration + 23 regression + 38 e2e + 6 validation)

## [0.2.0] — 2026-07-04

### Adicionado
- 21 testes funcionais E2E (`tests/e2e/test_functional.py`): navegação remota, copy/move, wizard, jobs, verificação, preferências, daemon/tray/autostart
- Testes de navegação remota com duplo-clique em diretórios e arquivos
- Testes de transferência copy/move real via `RcloneService.copy()` / `move()`
- Testes de CRUD de jobs com execução real via `JobService.execute_job()`
- Testes de wizard de OAuth, edição de remotos, daemon e autostart
- `closeEvent` no `FilePanel` para lifecycle seguro do QThread

### Corrigido
- **Crash crítico do Explorer**: `threading.Thread` emitindo signals PySide6 eram silenciosamente descartados. Migrado para `QThread` + `moveToThread` worker pattern (`_LsWorker`).
- **Segfault no QVariant**: `dict` em `Qt.UserRole + 1` causava crash quando o view ordenava itens. Migrado para JSON serializado (`json.dumps`/`json.loads`).
- **Navegação quebrada por sort order**: `_items_by_row` array paralelo quebrava quando QTreeView reordenava alfabeticamente. Navegação agora usa `index.data(Qt.UserRole + 1)` que é independente da ordem visual.
- **QThread lifecycle**: app crashava ao fechar (`QThread: Destroyed while thread is still running`). Adicionado `shutdown()` no `RemoteFileModel` chamado pelo `closeEvent` do `FilePanel`, com cleanup seguro (`quit` → `wait` → `terminate` fallback) e proteção `try/except RuntimeError` para objetos Qt já destruídos.
- **Race condition no explorer**: `blockSignals(True/False)` ao trocar modelo + guard `_is_local` em `_on_listing_ready` evita signals do modelo antigo corromperem o path atual.
- **QFileSystemModel.refresh() inexistente no Qt6**: substituído por `setRootPath()` com ajuste de parent/child path.

### Alterado
- `test_comprehensive.py`: decorator `test()` → `val_test()` para evitar conflito com pytest fixture discovery
- E2E tests de navegação: agora escaneiam o modelo ordenado para encontrar a linha correta (em vez de hardcoded row index)
- E2E test de copy: seta JSON metadata em `Qt.UserRole + 1` nos QStandardItems manualmente criados

## [0.1.0] — 2026-07-04

### Adicionado
- MVP completo: 15 requisitos funcionais (RF-01 a RF-15)
- Wizard de configuração de remotos com OAuth delegado via `rclone authorize` (QProcess)
- Explorador two-panel (local + remoto) com navegação, breadcrumb e operações de arquivo
- Jobs de sincronização (sync, copy, move, bisync) com scheduler (croniter)
- Montagem VFS (FUSE) com configurações de cache
- Transferências pontuais one-shot
- Verificação de integridade (check + hash)
- Daemon de background com system tray
- Autostart no login (`.desktop` em `~/.config/autostart/`)
- Notificações do sistema (D-Bus)
- Preferências globais
- Suporte a filtros
- 132 testes automatizados (unit/integration/contract/regression/e2e)
- 36 testes de validação contra rclone real + Google Drive
- Tema escuro Catppuccin Mocha
- Catálogo de 22 backends (`resources/backends.json`)
- Build-backend corrigido para `setuptools.build_meta`

### Corrigido
- OAuth: `QProcess` com signals em vez de `subprocess.Popen`
- Token extraction de `rclone authorize` lida com prefixos `NOTICE:`
- DB singleton: `closeEvent` não fecha mais conexão (isolation entre testes via `_instance = None`)
- `about()` aceita parâmetro `timeout` (90s padrão para backends lentos como Google Drive)
- RC API: validação usa POST (não GET) para `/rc/noop`
- `rclone.conf` precisa ser owned pelo usuário (não root) para `rclone authorize` funcionar

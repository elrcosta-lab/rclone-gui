# Spec 08 — Pastas de Sincronização (Sync Folders)

> **Funcionalidade:** Pastas locais sincronizadas bidirecionalmente com remotos, estilo Google Drive for desktop
> **Responsável:** Emerson
> **Status:** Implementado v0.3.0
> **Dependências:** RF-11 (Daemon/Tray), RF-12 (Autostart), RF-01 (Remotos)

---

## 1. Visão Geral

O usuário registra uma pasta local (`~/RcloneSync/MeuDrive/`) associada a um remoto (`gdrive:`). O daemon detecta alterações locais via inotify (watchdog) e alterações remotas via polling periódico (bisync a cada N minutos), mantendo os dois lados sincronizados com resolução automática de conflitos (newest wins).

---

## 2. Comportamento Esperado

### 2.1 Registro

- O usuário informa nome, caminho local e remote path
- O sistema cria a pasta local se não existir
- A configuração é persistida no SQLite (`sync_folders` table)
- Default: polling 5 min, debounce 5 s, conflict-resolve `newer`, enabled

### 2.2 Sincronização

- **Local → Remoto:** Alterações locais detectadas por inotify (watchdog) disparam bisync após debounce
- **Remoto → Local**: Polling periódico executa bisync para capturar mudanças remotas
- Durante bisync já em andamento, novas detecções são ignoradas (não acumular)

### 2.3 Ciclo de Vida

- **Daemon**: gerencia watchers + pollers de pastas ativas (enabled)
- **GUI**: página Sync Folders no sidebar para listar/adicionar/editar/remover
- **Tray**: submenu com status e atalho "Sincronizar agora"
- **First-run**: pasta `~/RcloneSync/` criada automaticamente

### 2.4 Tratamento de Conflitos

- `--conflict-resolve newer` (padrão) — arquivo mais recente vence
- Alternativas: path, local, remote (configurável por pasta)

---

## 3. Arquitetura

### 3.1 Camadas

| Camada | Componente | Função |
|--------|-----------|--------|
| Model | `SyncFolderConfig` | Dataclass com id, name, local_path, remote_path, polling_interval, debounce_seconds, enabled, last_sync_at, last_sync_status |
| DB | `Database._migrate_v2` | Tabela `sync_folders`, coluna `sync_folder_root_path` em `app_config`, CRUD em `save_sync_folder`/`get_all_sync_folders`/`delete_sync_folder` |
| Service | `SyncFolderService` | register, get_all, get_enabled, set_enabled, unregister, sync_now (chama RcloneService.bisync) |
| Watcher | `SyncFolderWatcher` | watchdog Observer + `_DebouncedHandler` + QSignal bridge para main thread |
| Poller | `SyncFolderPoller` | QTimer periódico com suppress (para debounce sobrepor polling) |
| Manager | `SyncFolderManager` | Orquestra `_ManagedFolder` instances (watcher + poller + sync execution por pasta) |
| Daemon | `DaemonApp` | QCoreApplication + QTimer heartbeat + SyncFolderManager |
| GUI | `SyncFolderList` | Página no sidebar com lista, botões Add/Edit/Remove/Sync Now |
| GUI | `SyncFolderEditor` | Dialog de configuração (nome, caminhos, polling, debounce, enabled) |
| GUI | `PreferencesDialog` | Defaults de polling interval e debounce (se DB suportar key-value) |
| Tray | `TrayManager` | Submenu Sync Folders com status e ações |

### 3.2 Fluxo de Sincronização

```
[inotify] → _DebouncedHandler.on_any_event → changes_detected Signal (cross-thread)
    → _ManagedFolder._on_changes → poller.set_suppressed(True) → _do_sync()
    → SyncFolderService.sync_now() → RcloneService.bisync() → atualiza last_sync_at
    → poller.set_suppressed(False)

[poller QTimer timeout] → time_to_sync Signal → _ManagedFolder._on_poll
    → _do_sync() (se não estiver sync em andamento e não suprimido)
```

### 3.3 Ignorados pelo Watcher

- Arquivos ocultos (`.` prefix)
- Lock files: `.rclonelck`, `.binaysynclck`

---

## 4. Casos de Teste

### 4.1 Unitários (22 existentes)

| Teste | O quê verifica |
|-------|---------------|
| `test_sync_folder.py:TestSyncFolderModel` | defaults, custom values, to_dict, from_row |
| `test_sync_folder.py:TestSyncFolderDB` | CRUD no SQLite |
| `test_sync_folder_service.py` | register, get_all, enable/disable, unregister, sync_now, last_sync_at |
| `test_sync_folder_watcher.py` | start/stop, signal emit, debounce, ignore patterns |
| `test_sync_folder_poller.py` | start/stop, signal emit, suppressed state |
| `test_sync_folder_manager.py` | start_all/stop_all, enabled filter, watcher trigger, active_folders |

### 4.2 Integração

- DaemonApp com SyncFolderManager (mock bisync)
- MainWindow com SyncFolderList page carregada

---

## 5. Critérios de Aceitação

1. [x] Usuário pode registrar pasta local + remoto via GUI
2. [x] Alterações locais disparam bisync (com debounce)
3. [x] Polling periódico captura mudanças remotas
4. [x] Watcher ignora arquivos ocultos e lock files
5. [x] Sincronização simultânea não acumula (suppress + _syncing guard)
6. [x] Daemon gerencia pastas ativas automaticamente
7. [x] Tray mostra status das pastas
8. [x] First-run cria ~/RcloneSync/
9. [x] Jobs de bisync têm flags --resync, --conflict-resolve, --workgroup no editor
10. [x] 86+ unit tests passando

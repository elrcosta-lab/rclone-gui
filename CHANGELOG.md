# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/spec/v2.0.0.html).

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

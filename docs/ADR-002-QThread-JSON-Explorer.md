# ADR-002: QThread Worker Pattern + JSON Item Data no Explorer

## Status
Aceito — implementado em 2026-07-04

## Contexto
O explorador de arquivos two-panel (`FilePanel` + `RemoteFileModel`) sofreu três crashes críticos em sequência durante os testes E2E e uso real:

1. **Signals perdidos:** `threading.Thread` emitindo `pyqtSignal`/`Signal` do PySide6 eram **silenciosamente descartados** — a callback `_on_listing_ready` nunca era chamada, deixando o modelo vazio após a listagem remota.
2. **Segfault no QVariant:** Armazenar Python `dict` diretamente em `QStandardItem.setData(role=Qt.UserRole+1)` causava crash (`SIGSEGV`) quando o `QTreeView` reordenava itens alfabeticamente (sort).
3. **Navegação quebrada por sort order:** Um array paralelo `_items_by_row` indexava itens pela linha visual. Quando o `QTreeView` reordenava alfabeticamente, duplo-clique em uma pasta navegava para o item errado (ou crashava).

Além disso, ao fechar a janela principal, o `QThread` do `RemoteFileModel` era destruído pelo garbage collector do Python enquanto ainda rodava uma chamada `rclone lsjson`, gerando `QThread: Destroyed while thread is still running` e abortando o processo.

## Decisão

### 1. Worker Pattern: `QThread` + `moveToThread`
- Criar `_LsWorker(QObject)` com signal `listing_done`
- Mover o worker para uma `QThread` via `moveToThread(self._thread)`
- Conectar `thread.started` → `worker.do_work`
- Conectar `worker.listing_done` → `thread.quit` (auto-cleanup)
- Cleanup explícito via `shutdown()` chamado pelo `closeEvent` do `FilePanel`

### 2. JSON Serialization em `Qt.UserRole + 1`
- Serializar cada entrada `lsjson` com `json.dumps()` antes de `setData(entry_json, Qt.UserRole + 1)`
- Desserializar com `json.loads()` em `_on_double_click` e `selected_files()`
- Remover completamente o array paralelo `_items_by_row`

### 3. Race Condition Guard
- `blockSignals(True)` antes de `setModel(None)` + `setModel(new_model)` + `blockSignals(False)`
- Guard `_is_local` em `_on_listing_ready` — ignora signals de modelos antigos

## Consequências

### Positivas
- Signals de thread são entregues 100% do tempo (event loop Qt garante)
- Navegação funciona independentemente da ordem visual do `QTreeView`
- App fecha sem crash (`shutdown()` → `quit` → `wait` → `terminate` fallback)
- Testes E2E passam de forma determinística

### Negativas
- Overhead de `json.dumps`/`json.loads` por item (negligível para diretórios com < 1000 itens)
- Complexidade adicional de gerenciamento de lifecycle do `QThread`
- Necessidade de proteção `try/except RuntimeError` em `_cleanup_thread()` para objetos Qt já destruídos pelo C++

## Alternativas Consideradas

| Alternativa | Por que rejeitada |
|-------------|------------------|
| `QProcess` assíncrono para cada `lsjson` | `QProcess` é mais pesado (fork); `lsjson` retorna rapidamente (< 5s), não justifica processo separado |
| `QThreadPool` + `QRunnable` | `QRunnable` não suporta signals nativamente; requer `QMetaObject.invokeMethod` ou callback via `QThreadPool` |
| `_items_by_row` com `model.rowCount()` sync | Não resolve o problema fundamental: a ordenação visual muda, e o array paralelo sempre ficaria desincronizado |
| `Qt.UserRole + 1` com `pickle` em vez de JSON | `pickle` é menos seguro e não legível para debug; JSON é suficiente e portável |
| `QStandardItem.setData()` com `QVariantMap` | `QVariantMap` (C++ `QMap<QString, QVariant>`) não é diretamente mapeável de Python `dict` no PySide6 sem conversão explícita |

## Implementação

Arquivos modificados:
- `rclone_gui/gui/explorer/file_panel.py` — `_LsWorker`, `RemoteFileModel`, `FilePanel`
- `tests/e2e/test_functional.py` — testes de navegação e copy atualizados para JSON metadata

## Referências
- Spec 02: Explorador de Arquivos — Seção 15 (Decision Log)
- PRD.md v1.5 — Histórico de Revisões
- CHANGELOG.md v0.2.0

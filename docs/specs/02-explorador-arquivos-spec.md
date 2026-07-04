# Spec: Explorador de Arquivos (Two-Panel Browser)

**Versão:** 1.2
**Status:** Implementado
**Autor:** Emerson
**Data:** 2026-07-04
**Reviewers:** N/A

---

## 1. Resumo

Interface de navegação de arquivos em dois painéis (origem/destino) que permite explorar arquivos e pastas tanto em sistemas locais quanto em remotos configurados, substituindo comandos CLI como `rclone lsf`, `lsd`, `lsjson`, `tree`, `cat`, `mkdir`, `rmdir`, `delete` por uma experiência visual de gerenciador de arquivos. Serve como fundação para seleção de paths em jobs de sync e transferências pontuais.

---

## 2. Contexto e Motivação

**Problema:**
Explorar arquivos em um remoto via CLI é lento e não intuitivo:
- `rclone lsf remote:path` lista nomes — precisa de comando diferente para ver detalhes (`lsl`, `lsjson`)
- `rclone lsjson` retorna JSON, útil para scripts mas não para consumo humano direto
- `rclone tree` não é interativo — não dá para expandir/colapsar pastas
- Operações básicas (criar pasta, renomear, excluir) exigem comandos separados (`mkdir`, `moveto`, `deletefile`)
- Não há visualização de espaço ocupado por diretório sem comandos adicionais (`size`)
- Navegar entre pastas profundamente aninhadas exige redigitar paths completos

**Evidências:**
- Ferramentas como FileZilla (FTP/SFTP) e Cyberduck provam que exploradores gráficos de armazenamento remoto são amplamente usados e valorizados
- O próprio Google Drive for desktop integra-se ao gerenciador de arquivos nativo (Nautilus/Dolphin/Finder) — usuários esperam essa experiência
- Issues do rclone pedindo "GUI file browser" aparecem recorrentemente

**Por que agora:**
O explorador de arquivos é o ponto de entrada para operações de transferência: o usuário precisa visualizar e selecionar arquivos/pastas antes de copiar, sincronizar ou verificar.

---

## 3. Goals (Objetivos)

- [ ] G-01: Permitir navegação visual em árvore de qualquer remoto configurado com latência aceitável (< 5s para diretórios com até 1000 itens)
- [ ] G-02: Exibir dois painéis lado a lado (origem e destino) que podem ser dois remotos diferentes ou um local + remoto
- [ ] G-03: Exibir colunas: nome, tamanho, data de modificação, tipo (ícone)
- [ ] G-04: Suportar atalhos de teclado padrão de gerenciadores de arquivos (F5=Copiar, F6=Mover, F7=Criar Pasta, F8=Excluir, Enter=Abrir, Backspace=Voltar)
- [ ] G-05: Permitir operações de contexto: Criar Pasta, Renomear, Excluir, Copiar Link (URL pública, quando suportado)
- [ ] G-06: Oferecer preview de arquivos de texto/imagem via `rclone cat` (para texto) ou RC API (para binário com limite de tamanho)
- [ ] G-07: Exibir breadcrumb clicável e campo de path editável para navegação direta

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| Tempo para listar diretório de 1000 itens | ~3-8s (CLI, depende do backend) | < 5s na GUI (com cache) | Lançamento |
| Navegação entre diretórios | Redigitar path (CLI) | ≤ 2 cliques | Lançamento |
| Cobertura de operações de arquivo | 6 comandos CLI | 6 operações visuais integradas | Lançamento |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: Editor de arquivos embutido — preview somente leitura; edição é delegada ao aplicativo padrão do sistema
- NG-02: Upload/download via drag-and-drop entre a GUI e o gerenciador de arquivos nativo — fase 2
- NG-03: Sync seletivo de pastas por checkbox — fase 2 (Spec 03 cobre sync por job)
- NG-04: Suporte a múltiplas abas de navegação — fase 2
- NG-05: Visualização de arquivos ocultos como toggle — fase 2 (MVP: mostrar tudo, respeitando `--exclude` patterns)

---

## 5. Usuários e Personas

**Usuário primário:** Ana — quer navegar entre Google Drive e Dropbox como se fossem pastas locais. Valoriza ícones familiares, breadcrumb clicável e preview rápido de imagens.

**Usuário secundário:** Bruno — quer encontrar rapidamente paths para configurar sync jobs. Valoriza atalhos de teclado, campo de path editável (para colar paths conhecidos) e a capacidade de copiar o path atual para uso em scripts.

**Jornada atual (sem a feature):**
1. Abre terminal e digita `rclone lsd gdrive:`
2. Para ver detalhes: `rclone lsl gdrive:`
3. Para navegar: digita path completo a cada nível
4. Para criar pasta: `rclone mkdir gdrive:nova-pasta`
5. Para excluir: `rclone deletefile gdrive:arquivo.txt`
6. Para ver preview: `rclone cat gdrive:arquivo.txt`

**Jornada futura (com a feature):**
1. Abre a GUI, vê painel esquerdo (local) e direito (remoto)
2. No painel direito, seleciona "gdrive:" no seletor de remotos — a árvore de diretórios carrega
3. Clica para expandir pastas, vê arquivos com ícones e metadados
4. Clica direito em um arquivo → Preview → vê conteúdo em popup
5. Clica em "Copiar Path" para usar o path em outro lugar

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-S02-01 | O sistema deve exibir dois painéis lado a lado, cada um com seletor de origem (local ou remoto configurado), breadcrumb e área de listagem de arquivos | Must | Layout horizontal dividido igualmente; seletor lista todos os remotos da Spec 01 + "Arquivos Locais"; painéis são independentes (podem mostrar paths diferentes) |
| RF-S02-02 | O sistema deve listar conteúdo de diretórios via `rclone lsjson`, exibindo nome, tamanho (formatado), data de modificação (relativa e absoluta no tooltip) e ícone por tipo/extensão | Must | Colunas: Ícone, Nome, Tamanho, Modificado; ordenação clicando no cabeçalho (asc/desc); diretórios listados antes de arquivos por padrão |
| RF-S02-03 | O sistema deve exibir árvore de diretórios (tree sidebar) para cada painel, sincronizada com o breadcrumb de navegação | Should | Painel de árvore lateral que carrega lazy (sob demanda) ao expandir um nó; breadcrumb no topo do painel reflete o path atual com segmentos clicáveis |
| RF-S02-04 | O sistema deve cachear resultados de `rclone lsjson` com TTL configurável para evitar requisições redundantes ao mesmo diretório | Must | Cache em memória (dicionário path → resultado + timestamp); TTL default 60s; botão "Atualizar" força refresh ignorando cache |
| RF-S02-05 | O sistema deve suportar navegação: duplo clique em pasta abre; Backspace/Alt+Esquerda volta ao diretório pai; campo de path editável aceita path digitado/colado com autocomplete | Must | Path digitado é validado ao pressionar Enter; se inválido, mensagem "Caminho não encontrado" com sugestão de path similar |
| RF-S02-06 | O sistema deve permitir criar pasta via atalho (F7 / Ctrl+Shift+N) ou menu de contexto, solicitando nome e confirmando criação | Must | Diálogo modal simples: "Nome da pasta:" + OK/Cancelar; executa `rclone mkdir remote:path/nova-pasta`; lista é atualizada após criação |
| RF-S02-07 | O sistema deve permitir renomear arquivo/pasta via atalho (F2) ou menu de contexto, com validação de nome | Must | Renomear executa `rclone moveto remote:path/velho remote:path/novo` (server-side move quando possível); erro se nome já existe |
| RF-S02-08 | O sistema deve permitir excluir arquivo/pasta via atalho (F8 / Delete) ou menu de contexto, com confirmação explícita | Must | Diálogo: "Excluir 'arquivo.txt'? Esta ação não pode ser desfeita." + checkbox "Também excluir de todos os remotos sincronizados"; executa `rclone deletefile` (arquivo) ou `rclone purge` (pasta) |
| RF-S02-09 | O sistema deve exibir preview de arquivos: texto (< 1 MB) via `rclone cat` em visualizador modal com syntax highlighting básico; imagem via download temporário exibido em QLabel/QPixmap | Should | Preview abre em diálogo modal com título do arquivo; arquivos > 10 MB exibem aviso "Arquivo muito grande para preview. Deseja baixar?"; timeout de 30s para download do preview |
| RF-S02-10 | O sistema deve copiar link público do arquivo (`rclone link`) para a área de transferência quando suportado pelo backend | Should | Item de menu "Copiar Link Público" no menu de contexto; se backend não suporta, item aparece desabilitado com tooltip "Não suportado por este backend" |
| RF-S02-11 | O sistema deve exibir barra de status no rodapé com: número de itens no diretório atual, espaço usado (se disponível), e indicador de carregamento durante listagem | Must | Status: "23 itens · 1.4 GB" (diretório atual) + "Quota: 7.2 GB / 15 GB" (remoto); spinner animado durante `lsjson`; se `about` não disponível, omitir quota |
| RF-S02-12 | O sistema deve permitir selecionar múltiplos arquivos/pastas (Ctrl+Clique, Shift+Clique, Ctrl+A) para operações em lote | Should | Seleção múltipla segue convenção padrão de list views; status mostra "5 itens selecionados"; operações de contexto aplicam a toda seleção |
| RF-S02-13 | O sistema deve exibir indicador de carregamento progressivo: skeleton loader para primeira carga, spinner inline para subpastas, e barra de progresso para operações longas (excluir muitos arquivos) | Should | Skeleton: linhas cinza piscando no lugar da lista; spinner: ícone girando sobre o painel durante refresh; progresso: barra modal "Excluindo 45 arquivos..." |

### 6.2 Fluxo Principal (Happy Path) — Navegar e Explorar

1. O usuário abre a GUI, vê os dois painéis (esquerdo = local, direito = vazio)
2. No painel direito, seleciona "Meu Google Drive" no dropdown de remotos
3. O sistema lista o conteúdo da raiz do remoto (pastas e arquivos) com ícones e metadados
4. O usuário clica duas vezes em "Fotos/" — o diretório abre, breadcrumb atualiza para `gdrive: > Fotos`
5. O usuário clica no breadcrumb "gdrive:" para voltar à raiz
6. O usuário digita `gdrive:Projetos/2025` no campo de path e pressiona Enter — navega diretamente

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Criar Pasta:**
1. Usuário pressiona F7 no painel ativo
2. Diálogo "Nova Pasta" aparece com campo de nome
3. Usuário digita "Backup" e clica OK
4. Pasta é criada via `rclone mkdir` e lista é atualizada

**Fluxo Alternativo B — Preview de Imagem:**
1. Usuário clica direito em "foto.jpg" → Preview
2. Sistema faz download temporário para `/tmp/rclone-gui-preview/`
3. Imagem é exibida em diálogo modal redimensionável
4. Ao fechar, arquivo temporário é removido

**Fluxo Alternativo C — Cópia entre painéis (atajo para transferência):**
1. Usuário seleciona arquivos no painel esquerdo (local)
2. Pressiona F5 (Copiar) — o sistema detecta que o painel direito é um remoto
3. Diálogo "Copiar para gdrive:Projetos?" com opções (--checksum, --dry-run)
4. Confirma — inicia transferência (delega para Spec 05)

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-S02-01 | Toda comunicação com rclone é assíncrona (QProcess ou QThread) | UI nunca congela durante operações de listagem ou operações de arquivo | Signals/Slots conectam resultado do subprocess ao update da UI |
| RNF-S02-02 | Cache de listagem com invalidação | TTL 60s padrão, configurável; invalidado automaticamente após operações de escrita (mkdir, delete, rename) | Evita requisições redundantes durante navegação frequente |
| RNF-S02-03 | Lazy loading de árvore de diretórios | Subpastas carregadas sob demanda ao expandir nó; máximo de 2 níveis de prefetch | Evita overhead de listar árvore inteira em backends lentos |
| RNF-S02-04 | Timeout de `lsjson` | 30s por diretório; após timeout, exibir "Tempo limite excedido — o backend pode estar lento" com botão "Tentar novamente" | Essencial para backends com alta latência (FTP, HTTP) |
| RNF-S02-05 | Limite de preview de arquivo | Texto: 1 MB; Imagem: 10 MB; Binário/outro: não suportado | Evita consumo excessivo de memória e largura de banda |
| RNF-S02-06 | Formatação de tamanho de arquivo | Unidades legíveis (KB, MB, GB, TB) seguindo convenção binária (1024); opção de exibir bytes exatos nas preferências | Consistente com o comportamento `--human-readable` do rclone |

---

## 8. Design e Interface

### Componentes afetados
- **TwoPanelBrowser (QWidget):** container principal com dois painéis splitter ajustável
- **FilePanel (QWidget):** seletor de remoto, breadcrumb, campo de path, tree sidebar, list view (QTreeView com QFileSystemModel-like para remotos), barra de status
- **RemoteSelector (QComboBox):** dropdown com remotos configurados + "Arquivos Locais" + ícone de status (online/offline)
- **BreadcrumbBar (QWidget):** segmentos clicáveis do path atual com setas separadoras
- **FilePreviewDialog (QDialog):** modal com QTextEdit (texto) ou QLabel/QScrollArea (imagem)
- **OperationProgressDialog (QDialog):** barra de progresso + log para operações em lote

### Comportamento esperado
- O painel ativo tem borda destacada (cor azul) — clique em qualquer área do painel o torna ativo
- Teclas de atalho operam sobre o painel ativo (F5 copia do painel ativo para o outro)
- Drag de arquivos entre painéis inicia transferência (Spec 05)
- Duplo clique em arquivo: se tipo conhecido (.txt, .jpg, .png, .pdf), abre preview; caso contrário, pergunta se deseja baixar

### Estados da UI
- **Estado vazio (remoto sem arquivos):** ícone de pasta vazia + "Este diretório está vazio"
- **Estado vazio (remoto não configurado):** "Nenhum remoto configurado. Adicione um remoto para começar." + botão que abre wizard da Spec 01
- **Estado de carregamento:** skeleton loader (3-5 linhas cinza com animação de pulso) substituindo a lista
- **Estado de erro (path não encontrado):** "Caminho 'gdrive:inexistente' não encontrado. Verifique o nome e tente novamente."
- **Estado de erro (backend offline):** "O remoto 'gdrive' está offline. Verifique sua conexão." + botão "Tentar novamente"
- **Estado de erro (permissão negada):** "Permissão negada para acessar 'gdrive:restrito'."

---

## 9. Modelo de Dados

### Entidades (em memória + cache SQLite)

```
DirectoryListing {
  path: str                   // Path completo (ex: "gdrive:Projetos/2025")
  items: [FileEntry]          // Lista de entradas
  fetched_at: datetime        // Timestamp do fetch (para cache TTL)
  total_items: int            // Total de itens no diretório
  total_size: int?            // Tamanho total em bytes (se disponível)
}

FileEntry {
  name: str                   // Nome do arquivo/pasta
  path: str                   // Path completo
  is_dir: bool
  size: int?                  // Bytes (None para diretórios)
  mime_type: str?             // MIME type (ex: "image/jpeg")
  mod_time: datetime?         // Data de modificação (RFC 3339)
  icon_name: str              // Nome do ícone Qt (ex: "folder", "image", "text")
  extension: str?             // Extensão (ex: "txt", "jpg")
}

CacheEntry {                  // Tabela SQLite para cache persistente entre sessões
  path: str PRIMARY KEY
  json_data: text             // JSON serializado do DirectoryListing
  fetched_at: datetime
}
```

### Migrações necessárias
Sim — criar tabela `directory_cache` no SQLite na primeira inicialização. Migração simples: CREATE TABLE IF NOT EXISTS.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| `rclone lsjson` | Obrigatória | Listagem de diretórios remotos fica indisponível — navegação local ainda funciona |
| `rclone mkdir` | Obrigatória | Criação de pastas remotas indisponível |
| `rclone deletefile` / `rclone purge` | Obrigatória | Exclusão remota indisponível |
| `rclone moveto` | Obrigatória | Renomeação remota indisponível |
| `rclone cat` | Opcional | Preview de texto remoto indisponível (arquivos locais ainda funcionam) |
| `rclone link` | Opcional | "Copiar Link Público" desabilitado no menu de contexto |
| `rclone about` | Opcional | Quota não exibida na barra de status (apenas contagem de itens) |
| Gerenciamento de Remotos (Spec 01) | Obrigatória | Sem remotos configurados, apenas navegação local disponível |
| SQLite (Cache) | Opcional | Sem cache, cada navegação repete `lsjson` (funcionalidade não quebra, apenas fica mais lenta) |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-S02-01: Diretório com 10.000+ itens | Pasta muito grande | Listar em chunks (500 itens por vez) com scroll infinito; ou exibir aviso "Este diretório contém muitos itens. A listagem pode ser lenta. Deseja continuar?" antes de carregar |
| EC-S02-02: Nome de arquivo com caracteres especiais (:, /, emojis) | Arquivo com nome inválido no sistema local | Exibir nome corretamente na lista (encoding UTF-8); ao copiar para local, sanitizar nome ou alertar "Nome contém caracteres incompatíveis com o sistema de arquivos local" |
| EC-S02-03: Link simbólico em remoto | `lsjson` retorna IsSymlink=true | Exibir ícone de link com overlay de seta; preview mostra conteúdo do alvo |
| EC-S02-04: Arquivo com 0 bytes | Arquivo vazio | Listar normalmente com "0 B"; preview de texto mostra " (arquivo vazio)" |
| EC-S02-05: Falha de conexão durante navegação | Rede cai enquanto lista diretório | Spinner de carregamento permanece; após timeout (30s), exibir "Conexão perdida com o remoto. Verifique sua rede." + botão "Reconectar" |
| EC-S02-06: Conflito de cache — arquivo modificado externamente | Outro cliente alterou o remoto enquanto o cache está ativo | Botão "Atualizar" força invalidação de cache para o diretório atual; indicador visual de "cache pode estar desatualizado" após TTL expirar |
| EC-S02-07: Tentativa de excluir diretório não-vazio | `rclone purge` em pasta com conteúdo | Diálogo: "A pasta 'Projetos' contém 45 itens. Excluir tudo permanentemente?" com contagem de itens e tamanho total. Checkbox "Mover para backup-dir" se configurado |
| EC-S02-08: Preview de arquivo binário corrompido | `rclone cat` retorna dados inválidos | Exibir "Não foi possível gerar preview — o arquivo pode estar corrompido ou é de um tipo não suportado." |
| EC-S02-09: Path muito longo (> 4096 caracteres) | Path excede limite do sistema de arquivos | Truncar exibição do breadcrumb com "..." no meio do path; campo de path mostra ícone de alerta com tooltip "Path muito longo" |

---

## 12. Segurança e Privacidade

- **Autenticação:** Não se aplica — usa os remotos já autenticados via `rclone.conf`.
- **Autorização:** Respeita as permissões dos remotos configurados. Se um backend retornar "permission denied", a GUI exibe o erro e não tenta bypass.
- **Dados sensíveis:** Nomes de arquivos e paths podem conter informações pessoais. O cache SQLite armazena paths em plain text. Em versão futura, considerar criptografia do cache.
- **Auditoria:** Operações destrutivas (excluir, renomear) são logadas com timestamp, usuário do SO, path e operação. Logs são rotacionados (ver Spec 07).
- **Arquivos temporários de preview:** Salvos em `/tmp/rclone-gui-preview/` com permissões restritas (0700). Deletados ao fechar o preview ou ao encerrar a aplicação.

---

## 13. Plano de Rollout

- **Estratégia:** Feature flag interna — navegação local funciona mesmo sem rclone (fallback para QFileSystemModel). Navegação remota requer Spec 01 completa.
- **Como reverter (rollback):** A feature não modifica dados — apenas lê e exibe. Rollback é simplesmente desabilitar os painéis remotos.
- **Monitoramento pós-deploy:** Medir latência de `rclone lsjson` por tipo de backend para identificar backends com performance ruim. Telemetria anônima de comandos mais usados (mkdir vs. delete vs. rename).

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-S02-01 | O `rclone lsjson` com `--recursive` pode ser usado para pré-carregar a árvore? Ou seria muito pesado? | Médio — afeta estratégia de lazy loading | Emerson | Antes da implementação |
| OQ-S02-02 | Como exibir progresso de operações em lote? (excluir 500 arquivos)? O rclone RC suporta tracking de `deletefile` individual? | Médio — UX de operações batch | Emerson | Antes da implementação |
| OQ-S02-03 | O ícone do arquivo deve ser determinado por extensão localmente ou usar o MIME type retornado pelo backend (`lsjson --mimetype`)? | Baixo — preferência estética | Emerson | Implementação |
| OQ-S02-04 | Devemos integrar com o gerenciador de arquivos nativo (Nautilus/Dolphin) via plugin, ou manter navegação apenas dentro da GUI? | Alto — define escopo de integração desktop | Emerson | Decidir antes da Spec 04 (Montagem VFS) |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| Usar cache em memória com TTL em vez de apenas SQLite | (1) SQLite apenas, (2) Sem cache | Cache em memória é rápido para navegação frequente (voltar/avançar entre diretórios). SQLite como fallback frio para sessões posteriores. Evita complexidade de invalidação do SQLite em cada operação |
| `lsjson` em vez de `lsf` ou `lsl` | (1) `lsf` (simples), (2) `lsl` (texto fixo) | `lsjson` retorna dados estruturados (JSON), muito mais fácil e confiável de parsear. Inclui MIME type, IsDir, Size, ModTime em campos tipados |
| Tree sidebar com lazy loading em vez de pré-carregar árvore inteira | (1) Pré-carregar via `rclone tree --json`, (2) Sem tree sidebar | Pré-carregar árvore inteira é inviável para backends com milhares de pastas (pode levar minutos). Lazy loading carrega apenas o necessário |
| Navegação local usa `QFileSystemModel` nativo do Qt em vez de listar via rclone | (1) Usar rclone também para local | QFileSystemModel é nativo, performático, e já integrado com ícones e operações do SO. Usar rclone para local seria redundante e mais lento |
| Renomeação usa `rclone moveto` (server-side move) | (1) `rclone copyto` + delete | `moveto` é atômico e usa server-side copy quando disponível (muito mais rápido). Fallback automático do rclone para copy+delete quando backend não suporta server-side move |
| `threading.Thread` → `QThread` + `moveToThread` worker pattern | (1) `threading.Thread` com signals, (2) `QProcess` assíncrono | PySide6 signals emitidos de `threading.Thread` são **silenciosamente descartados** — a callback `_on_listing_ready` nunca era chamada. `QThread` com event loop Qt garante entrega de signals. Worker `_LsWorker` herda `QObject`, é movido para a thread via `moveToThread()` |
| `dict` → JSON string em `Qt.UserRole + 1` | (1) `dict` direto em `setData()`, (2) `_items_by_row` array paralelo | `QVariant` não converte Python `dict` de forma segura para roles customizadas — causa segfault quando o view ordena itens ou `index.data()` é chamado. JSON serializado (`json.dumps`/`json.loads`) é seguro para `QVariant`. `_items_by_row` array paralelo quebra quando o QTreeView reordena alfabeticamente — `index.data(Qt.UserRole + 1)` é independente da ordem visual |
| `setSortingEnabled(False)` antes de `setModel()` | (1) Apenas `setSortingEnabled(True)` | Evita que o QTreeView re-ordene pelo sort column do modelo *anterior* imediatamente após `setModel()`, o que corrompe a navegação duplo-clique antes que o usuário interaja |

---

## Apêndice

### Referências
- [rclone lsjson docs](https://rclone.org/commands/rclone_lsjson/)
- [rclone lsf docs](https://rclone.org/commands/rclone_lsf/)
- [rclone lsd docs](https://rclone.org/commands/rclone_lsd/)
- [rclone cat docs](https://rclone.org/commands/rclone_cat/)
- [rclone mkdir docs](https://rclone.org/commands/rclone_mkdir/)
- [rclone delete / deletefile docs](https://rclone.org/commands/rclone_delete/)
- [rclone link docs](https://rclone.org/commands/rclone_link/)
- [rclone RC API](https://rclone.org/rc/)
- PRD.md — Seção 3.1, RF-03

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-07-04 | Emerson | Criação inicial |
| 1.1 | 2026-07-04 | Emerson | Implementação completa: two-panel browser, seleção de remotos, navegação local/remota, breadcrumb, operações de arquivo |
| 1.2 | 2026-07-04 | Emerson | Fix: validação 36/36 confirma navegação, path picker, set_remotes populando combos |
| 1.3 | 2026-07-04 | Emerson | Fix crítico: `threading.Thread` → `QThread` + `moveToThread` worker pattern. `dict` em `QVariant` → JSON serializado em `Qt.UserRole + 1`. `_items_by_row` removido. `setSortingEnabled(False)` antes de `setModel()`. `closeEvent` chama `shutdown()` no `RemoteFileModel` para lifecycle seguro do QThread |

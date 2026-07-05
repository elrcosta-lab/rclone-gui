# PRD — Rclone GUI

> **Status:** Implementado (MVP)
> **Versão:** 1.6
> **Última atualização:** 2026-07-05
> **Responsável:** Emerson

---

## 1. Visão Geral

### 1.1 Resumo Executivo

Rclone GUI é uma aplicação desktop Linux (PySide6/Qt) que oferece uma interface gráfica intuitiva para o **rclone**, o gerenciador de arquivos multi-cloud mais poderoso do ecossistema open-source. Inspirada no Google Drive for desktop, a aplicação executa como daemon de background com ícone no system tray, monta remotos como drives virtuais no sistema de arquivos (via FUSE), permite criar e agendar jobs de sincronização (one-way e bidirecional), e oferece um explorador de arquivos gráfico para navegar entre os ~50+ backends suportados pelo rclone.

**Proposta de valor:** trocar a linha de comando por uma experiência visual tipo "cliente de nuvem desktop", eliminando a barreira técnica que impede usuários não-técnicos de aproveitar a potência do rclone.

### 1.2 Problema

O rclone é uma ferramenta CLI extremamente capaz — suporta mais de 50 backends de armazenamento (Google Drive, OneDrive, S3, Dropbox, SFTP, WebDAV, Backblaze B2, Mega, pCloud, etc.), oferece sincronização unidirecional e bidirecional, montagem de filesystem, verificação de integridade, criptografia transparente e dezenas de opções de controle. No entanto, toda essa capacidade está acessível apenas via terminal.

**Dores reais**:
- **Usuários não-técnicos** não conseguem configurar remotos (o wizard `rclone config` é textual e intimidador)
- **Sincronizações recorrentes** exigem scripts manuais + cron, sem visibilidade de progresso ou histórico de falhas
- **Montar remotos como drives** (`rclone mount`) é poderoso, mas requer conhecimento de FUSE, caminhos e flags
- **Explorar arquivos em nuvem** sem baixar exige comandos como `rclone lsf`, `rclone lsjson`, `rclone tree` — nada visual
- **Jobs de bisync** (bidirecional) são complexos de configurar e perigosos sem `--dry-run`/`--backup-dir`
- Não há notificações visuais de falhas, conflitos ou jobs concluídos

### 1.3 Solução Proposta

Uma aplicação desktop com três camadas de interação:

1. **Daemon de background** — inicia com o sistema, gerencia o ciclo de vida do `rclone rcd` (Remote Control API), executa jobs agendados, monitora mounts ativos e reporta status via tray icon
2. **Interface gráfica principal** — janela Qt completa com explorador de arquivos (two-panel), assistente de criação de remotos (wizard visual), gerenciador de jobs (criar/editar/pausar/executar/ver histórico), configurações de montagem e preferências
3. **Tray icon** — acesso rápido a remotos montados, status de syncs em andamento, atalhos para abrir pastas montadas e notificações do sistema

A UX é inspirada no Google Drive for desktop: o usuário monta um remoto, ele aparece como uma pasta no gerenciador de arquivos, e as sincronizações acontecem em background com indicadores visuais de progresso.

### 1.4 Objetivos do Produto

- **Objetivo 1:** Reduzir o tempo de configuração de um novo remoto de ~15 minutos (CLI + documentação) para < 3 minutos (wizard visual com busca de backends e formulários contextualizados)
- **Objetivo 2:** Permitir que 90% das operações comuns do rclone (copiar, sincronizar, mover, listar, verificar) sejam realizadas exclusivamente via GUI, sem abrir o terminal
- **Objetivo 3:** Oferecer montagem de remotos como drives locais com experiência equivalente ao Google Drive for desktop (mount automático no login, indicador de status no tray, cache transparente)
- **Objetivo 4:** Fornecer visibilidade completa de jobs (progresso em tempo real, histórico de execuções, logs de erro, notificações do sistema) que substitua scripts cron manuais

---

## 2. Público-alvo & Personas

### Persona Principal — Ana (usuária pessoal, multi-cloud)

- **Perfil:** 30 anos, designer, usa Google Drive para trabalho, Dropbox para portfólio e Backblaze B2 para backup de fotos. Confortável com interfaces gráficas, não usa terminal.
- **Dores:** Precisa manter arquivos sincronizados entre 3 nuvens diferentes sem pagar assinaturas caras de clientes oficiais. Já perdeu arquivos tentando sincronizar manualmente. Não consegue lembrar comandos CLI.
- **Ganhos esperados:** Uma única aplicação onde ela configura suas 3 contas, monta cada uma como pasta no desktop, agenda syncs semanais e recebe notificação quando tudo está em ordem.
- **Cenário de uso:** Segunda-feira de manhã: abre o explorador de arquivos, arrasta a pasta "Clientes" do Google Drive para o Dropbox, a GUI detecta e oferece criar um job de sync semanal. Aceita. Sexta-feira: recebe notificação "Sync Concluído — 234 arquivos atualizados".

### Persona Secundária — Bruno (sysadmin/dev)

- **Perfil:** 35 anos, DevOps/SRE, gerencia backups de servidores para S3 e SFTP. Usa rclone via CLI há 3 anos, tem ~15 scripts cron. Cansado de debugar falhas silenciosas e editar crontabs.
- **Dores:** Depurar scripts cron que falham sem log visível. Testar flags sem efeitos colaterais exige cuidado extremo. Não tem visão consolidada de múltiplos jobs.
- **Ganhos esperados:** Dashboard com todos os jobs, execução com `--dry-run` via checkbox, logs pesquisáveis, notificações de falha, reverificação pós-sync. Continua usando CLI para operações avançadas — a GUI é a camada de visibilidade e conveniência.
- **Cenário de uso:** Diariamente: abre a GUI para verificar status dos 5 jobs de backup noturnos. Vê que um falhou. Clica no log, identifica erro de quota no S3. Ajusta o bucket, reexecuta o job com um clique. Recebe confirmação visual de sucesso.

### Persona Terciária — Carla (familiar, não-técnica)

- **Perfil:** 45 anos, professora, armazena fotos da família no Google Fotos e backup no pCloud. Usa o computador para tarefas básicas (navegador, e-mail, fotos). Zero conhecimento técnico.
- **Dores:** Precisa de backup automático das fotos do celular (que já estão no Google Fotos) para um segundo local "por segurança". Não quer aprender nada complicado.
- **Ganhos esperados:** Alguém (Bruno, o filho) configura o remoto uma vez. Depois, a GUI simplesmente funciona: ícone no tray, "tudo sincronizado", sem interação necessária. Se algo falhar, o ícone fica vermelho e ela liga para o Bruno.
- **Cenário de uso:** Nunca abre a GUI. O ícone no tray fica verde = backup ok. Um dia fica vermelho, ela clica e vê "Erro de conexão com pCloud". Encaminha screenshot para o Bruno, que resolve remotamente.

---

## 3. Requisitos Funcionais

### 3.1 MVP (Mínimo Produto Viável)

Funcionalidades essenciais para o lançamento inicial:

| ID | Funcionalidade | Descrição | Prioridade |
|----|---------------|-----------|-----------|
| RF-01 | Wizard de Configuração de Remotos | Assistente visual para adicionar/editar/remover backends de armazenamento. Busca textual por nome do backend (~50+), formulário dinâmico por tipo, preview do `rclone.conf`, delegação de OAuth ao `rclone authorize`. | Alta |
| RF-02 | Listagem e Gerenciamento de Remotos | Exibir remotos existentes com nome, tipo, status (online/offline/quota), permitir editar, duplicar e excluir. Suporta `listremotes` e `about` para quota. | Alta |
| RF-03 | Explorador de Arquivos Two-Panel | Interface de dois painéis (origem/destino) com navegação em árvore (local + remoto), exibindo nome, tamanho, data de modificação, tipo. Listagem via `lsjson` com cache. Operações de contexto: renomear, excluir, criar pasta. | Alta |
| RF-04 | Criação e Gerenciamento de Jobs de Sync | Criar jobs de sincronização (`sync`, `copy`, `move`, `bisync`), configurando origem, destino, flags (checksum, dry-run, backup-dir, bwlimit, transfers, checkers, filters), salvos como entidade no SQLite. Suporta execução manual (one-shot) e automática (agendada). | Alta |
| RF-05 | Agendamento de Jobs (Scheduler) | Agendar jobs para execução recorrente com frequência configurável (minutos, horas, diário, semanal, personalizado via cron expression). Exibir próximos horários de execução e permitir pausar/retomar agendamento. | Alta |
| RF-06 | Execução de Jobs com Progresso em Tempo Real | Iniciar job manualmente ou por scheduler, exibindo progresso em tempo real via RC API (`core/stats`): arquivos transferidos, velocidade, ETA, erros. Permitir cancelar execução. | Alta |
| RF-07 | Histórico de Execuções de Jobs | Registrar cada execução de job no SQLite com timestamp, duração, status (sucesso/falha/cancelado), arquivos processados, bytes transferidos, log de erros. Interface de consulta com filtros por job, status e período. | Alta |
| RF-08 | Montagem de Remotos como VFS (FUSE) | Montar/desmontar remotos como drives no sistema de arquivos local via `rclone mount`. Configurar ponto de montagem, modo de cache VFS (off/minimal/writes/full), opções de rede. Mount automático opcional no login. Indicador visual de mount ativo. | Alta |
| RF-09 | Transferências Pontuais (Copy/Move One-Shot) | Interface rápida para copiar ou mover arquivos/pastas entre dois paths (local ou remoto) sem criar job persistente. Com barra de progresso e opção de salvar como job após conclusão. | Média |
| RF-10 | Verificação de Integridade (Check) | Verificar se origem e destino estão idênticos via `rclone check` e `cryptcheck`. Exibir relatório de diferenças (arquivos ausentes, tamanho divergente, checksum diferente) com opção de exportar. | Média |
| RF-11 | Daemon de Background com System Tray | Processo daemon que gerencia o ciclo de vida do `rclone rcd`, executa jobs agendados, mantém mounts ativos. Ícone no tray com status (verde=sync ok, amarelo=em andamento, vermelho=erro), menu de contexto (remotos, jobs, abrir GUI, sair). | Alta |
| RF-12 | Autostart no Login | Opção para iniciar o daemon automaticamente no login do usuário via arquivo `.desktop` em `~/.config/autostart/`. | Média |
| RF-13 | Notificações do Sistema | Enviar notificação nativa do desktop (D-Bus/freedesktop) ao concluir job (sucesso ou falha), ao detectar erro de mount, ou ao atingir limite de quota. | Média |
| RF-14 | Janela de Preferências | Tela de configurações globais: caminho do binário `rclone`, caminho do `rclone.conf`, porta do RC API, limites padrão de transfers/checkers, idioma, comportamento do tray (minimizar para tray vs. fechar). | Alta |
| RF-15 | Suporte a Filtros | Interface para construir regras de filtro (`--include`, `--exclude`, `--filter`, `--files-from`, `--min-size`, `--max-age`, etc.) com preview visual de padrões, usadas em jobs de sync e listagens. | Média |
| RF-16 | Pastas de Sincronização (Sync Folders) | Pastas locais sincronizadas bidirecionalmente com remotos via `rclone bisync`. Detecção de alterações locais por inotify (watchdog), polling remoto periódico (default 5 min), debounce configurável (default 5 s), resolução automática de conflitos (newest wins). Gerenciadas pelo daemon em background com submenu no tray. First-run: cria `~/RcloneSync/`. | Alta |

### 3.2 Pós-MVP (Roadmap Futuro)

Funcionalidades planejadas para versões seguintes:

| ID | Funcionalidade | Fase |
|----|---------------|------|
| RF-20 | Suporte a macOS e Windows | v2.0 |
| RF-21 | `rclone serve` (SMB/WebDAV/HTTP/FTP) | v2.0 |
| RF-22 | Deduplicação de arquivos (`dedupe`) | v2.0 |
| RF-23 | Criptografia (`obscure`) e `cryptcheck` com UI dedicada | v2.0 |
| RF-24 | Bisync avançado com resolução de conflitos interativa | v2.0 |
| RF-25 | Suporte a remotos do tipo `:backend:` on-the-fly (sem config prévia) | v2.0 |
| RF-26 | Sincronização seletiva de pastas por remoto (tipo Google Drive selective sync) | v2.0 |
| RF-27 | Dashboard web opcional via `rclone rc` | v3.0 |
| RF-28 | Importação/exportação de configurações e jobs | v2.0 |
| RF-29 | Suporte a múltiplos perfis de usuário | v3.0 |
| RF-30 | Integração com gerenciadores de senha do sistema (keyring) | v2.0 |

---

## 4. Requisitos Não-Funcionais

| Categoria | Requisito | Critério de Aceitação |
|-----------|-----------|----------------------|
| Performance | Inicialização da GUI | A janela principal deve exibir a lista de remotos em < 2s após o lançamento (assumindo `rclone listremotes` local) |
| Performance | Listagem de diretórios | Primeira listagem de um diretório remoto com até 1000 itens deve concluir em < 5s (dependente de latência do backend) |
| Performance | Impacto em idle | Daemon em idle (sem jobs ativos) deve consumir < 50 MB RAM e < 1% CPU |
| Confiabilidade | Tolerância a falha do rclone | Se o binário `rclone` não for encontrado ou falhar, a GUI deve exibir erro claro sem crash, com instrução de como instalar |
| Confiabilidade | Resiliência de jobs | Jobs interrompidos por shutdown do sistema devem ser marcados como "interrompido" no histórico e não corromper o banco SQLite |
| Segurança | Credenciais | Nunca armazenar tokens, senhas ou secrets fora do `rclone.conf` (que suporta criptografia nativa). OAuth delegado ao `rclone authorize` |
| Segurança | RC API | A porta da RC API (`--rc-addr`) deve ser bound a `localhost` apenas, nunca exposta à rede. Autenticação via `--rc-user`/`--rc-pass` gerados aleatoriamente |
| Segurança | Permissões FUSE | Mounts devem usar `--allow-other=false` por padrão, restritos ao usuário dono do processo |
| Usabilidade | Descoberta de funcionalidades | Todas as operações principais (copiar, sincronizar, montar, verificar) devem estar acessíveis em ≤ 3 cliques a partir da janela principal |
| Usabilidade | Feedback de ações destrutivas | Operações como `purge`, `delete`, `sync` (modificando destino) devem exigir confirmação explícita e, para `sync`, sugerir `--dry-run` |
| Acessibilidade | Navegação por teclado | Todos os elementos interativos devem ser navegáveis via Tab/Shift+Tab e acionáveis via Enter/Space |
| Compatibilidade | Versão do rclone | Suporte a rclone ≥ 1.60.0. Verificação de versão no startup com alerta se inferior |
| Compatibilidade | Dependências de sistema | `FUSE` (libfuse), `D-Bus` (notificações), `Qt 6.5+`. Verificação no startup com mensagens claras de instalação |
| Portabilidade | Linux | Suporte a distribuições com systemd (Ubuntu 22.04+, Fedora 38+, Debian 12+, Arch) e gerenciadores de arquivos populares (Nautilus, Dolphin, Thunar, Nemo) |

---

## 5. Fora do Escopo

O seguinte está explicitamente **fora** do escopo do MVP:

- **Suporte a macOS e Windows** — foco exclusivo em Linux na Fase 1
- **`rclone serve` (SMB/WebDAV/HTTP/FTP)** — cobertura em v2.0
- **`rclone dedupe` com UI interativa** — cobertura em v2.0
- **`rclone obscure` e gerenciamento de criptografia** — cobertura em v2.0
- **`rclone completion` (shell autocomplete)** — não é escopo da GUI
- **Edição manual do `rclone.conf` como texto** — o wizard substitui essa necessidade; edição direta é caso de uso CLI
- **Integração com gerenciadores de senha nativos (keyring)** — v2.0
- **Sincronização de configurações entre múltiplas máquinas** — v3.0
- **Interface web** — v3.0

---

## 6. Critérios de Sucesso & KPIs

| Métrica | Meta | Prazo |
|---------|------|-------|
| Usuários ativos (instalações) | 500 instalações | 6 meses pós-lançamento |
| Taxa de jobs bem-sucedidos | ≥ 95% dos jobs executados concluem sem erro | 3 meses pós-lançamento |
| Tempo médio de configuração de remoto | < 3 minutos (do wizard aberto ao remoto salvo) | Imediato (teste de usabilidade) |
| Net Promoter Score (NPS) | ≥ 40 | 6 meses pós-lançamento |
| Cobertura de funcionalidades rclone | ≥ 70% dos comandos de uso comum expostos na GUI | Lançamento |
| Issues de usabilidade no GitHub | < 10 issues abertas relacionadas a "difícil de usar" ou "confuso" | 3 meses pós-lançamento |

---

## 7. Roadmap de Alto Nível

| Fase | Entregável | Prazo Estimado |
|------|-----------|---------------|
| Fase 1 — MVP (Core) | RF-01 a RF-15: Config remotos, explorador, sync jobs, scheduler, mount VFS, tray/daemon, histórico, verificação, preferências | 16 semanas |
| Fase 2 — Avançado | RF-20 a RF-30: Windows/macOS, serve, dedupe, cryptcheck, bisync interativo, import/export, keyring | +12 semanas |
| Fase 3 — Ecossistema | Dashboard web, multi-perfil, sync seletivo, plugins | +16 semanas |

---

## 8. Riscos e Dependências

| Risco/Dependência | Probabilidade | Impacto | Mitigação |
|-------------------|--------------|---------|-----------|
| FUSE/kernel: permissões e compatibilidade variam entre distros, podem quebrar `rclone mount` | Média | Alto | Testar em 4 distros principais. Documentar troubleshooting de FUSE. Fallback: GUI alerta com link para wiki de troubleshooting |
| OAuth: cada backend tem fluxo de autorização diferente; `rclone authorize` precisa de browser disponível | Média | Médio | Delegar ao `rclone authorize` que já trata todos os backends. Se browser ausente (headless), documentar alternativa manual |
| RC API: `rclone rcd` pode mudar endpoints entre versões do rclone | Baixa | Alto | Fixar versão mínima suportada (≥ v1.60). Test suite com mocking de respostas RC. Monitorar changelog do rclone |
| Performance de listagem: backends lentos (FTP, HTTP) podem congelar a UI durante `lsjson` | Alta | Médio | Toda comunicação com rclone é assíncrona (QThread/Process). Timeout configurável. Cancelamento de operação em andamento |
| Multi-threading: PySide6 + subprocess + FUSE exigem cuidado com bloqueios de UI thread | Média | Alto | Arquitetura baseada em signals/slots. Operações longas em QProcess. Nunca bloquear a event loop principal |
| SQLite: corrupção em caso de shutdown abrupto durante escrita | Baixa | Alto | WAL mode + `PRAGMA synchronous=NORMAL`. Backup automático antes de migrações de schema |
| Dependência de `rclone` no PATH: usuário pode não ter instalado ou versão incompatível | Alta | Médio | Startup check: verificar `rclone version`. Opção de configurar caminho customizado nas preferências. Link para instalação |
| Complexidade da interface: ~50+ backends, ~30+ flags — risco de poluição visual | Alta | Alto | Design progressivo: opções avançadas colapsadas por padrão (Advanced toggle). Wizard com busca textual. Presets de flags por cenário de uso |
| Conflito com instâncias existentes do `rclone rcd`: usuário pode já ter daemon rodando | Baixa | Baixo | Detectar porta ocupada e oferecer usar instância existente ou encerrar a atual |

---

## 9. Glossário

| Termo | Definição |
|-------|-----------|
| **Remote (remoto)** | Configuração de um backend de armazenamento no `rclone.conf`. Ex: `gdrive:` (Google Drive), `s3:` (Amazon S3). Identificado por nome + tipo de backend |
| **Backend** | O tipo de armazenamento (Google Drive, S3, SFTP, etc.). Rclone suporta ~50+ backends. Também chamado de "provider" |
| **VFS (Virtual File System)** | Camada de abstração que permite acessar arquivos remotos como se fossem locais, via FUSE. Controlada por `--vfs-cache-mode` |
| **FUSE (Filesystem in Userspace)** | Mecanismo do kernel Linux que permite implementar sistemas de arquivos em espaço de usuário. Usado por `rclone mount` |
| **Sync (sincronização unidirecional)** | `rclone sync` — torna o destino idêntico à origem. Arquivos no destino que não existem na origem são **deletados** |
| **Copy** | `rclone copy` — copia arquivos da origem para o destino sem deletar nada no destino |
| **Bisync (sincronização bidirecional)** | `rclone bisync` — sincroniza nos dois sentidos, propagando mudanças de ambos os lados. Requer cuidado com conflitos |
| **RC API (Remote Control)** | API HTTP JSON exposta pelo `rclone rcd`. Permite controle programático: listar arquivos, iniciar/parar jobs, consultar progresso, alterar configurações em runtime |
| **Job** | Uma operação de transferência ou sincronização definida pelo usuário, que pode ser executada manualmente ou agendada. Persistida no SQLite |
| **Scheduler** | Componente que agenda e dispara jobs recorrentes com base em frequência configurável (minutos, horas, dias, semanas, cron) |
| **Daemon** | Processo de background que mantém o `rclone rcd` rodando, gerencia o scheduler, monitora mounts e fornece o tray icon |
| **Mount** | Ponto de montagem FUSE onde um remoto é acessível como sistema de arquivos local (ex: `/home/user/mnt/gdrive`) |
| **OAuth** | Fluxo de autorização usado por backends como Google Drive, Dropbox, OneDrive. O `rclone authorize` abre o browser, o usuário concede permissão, e o token é salvo no `rclone.conf` |
| **Two-panel** | Layout de explorador de arquivos com dois painéis lado a lado (origem e destino), comum em gerenciadores de arquivos como Total Commander, Midnight Commander |
| **Checksum** | Verificação de integridade por hash (MD5, SHA1, etc.) em vez de tamanho/data de modificação. Flag `--checksum` ou `-c` |
| **Backup-dir** | Diretório onde arquivos sobrescritos ou deletados são movidos durante um `sync`, preservando versões anteriores. Flag `--backup-dir` |
| **Dry-run** | Simulação de operação sem executar mudanças reais. Flag `--dry-run` ou `-n`. Essencial para validar syncs antes de executar |
| **Quota** | Informação de uso de armazenamento do backend (usado/disponível/total). Obtida via `rclone about` |

---

## 10. Histórico de Revisões

| Versão | Data | Autor | Alterações |
|--------|------|-------|-----------|
| 1.0 | 2026-07-04 | Emerson | Versão inicial — MVP definido com 15 requisitos funcionais Core, stack PySide6/Qt, Linux-only, inspirado Google Drive for desktop |
| 1.1 | 2026-07-04 | Emerson | MVP implementado (RF-01 a RF-15) + 5 níveis de testes (132/132 passando). README, specs e PRD atualizados para refletir estado implementado |
| 1.2 | 2026-07-04 | Emerson | Fix: wizard de OAuth migrado de subprocess.Popen para QProcess com sinais. README expandido com Troubleshooting e Status. Pendente: permissão rclone.conf pode bloquear `rclone authorize` |
| 1.3 | 2026-07-04 | Emerson | Validação completa contra rclone real + Google Drive (36/36 passando). Fix: `about` timeout 15→90s configurável. Fix: DB singleton isolation (closeEvent não mais fecha conn). Fix: rcd endpoint GET→POST. `about()` aceita `timeout` param. `notification.py` adiciona `setup_autostart`/`remove_autostart`. `preferences.py` guard `conn is None`. Build-backend corrigido para `setuptools.build_meta` |
| 1.4 | 2026-07-04 | Emerson | Remoção de todos os placeholders: transferência copy/move real no two-panel (RcloneService.copy/move), execução real de jobs via JobService.execute_job, edição de remotos via config_show/config_update. Fix: QFileSystemModel.refresh() inexistente no Qt6 → setRootPath. Fix: race condition no explorer (blockSignals + guard _is_local). 132/132 testes + 36/36 validação passando |
| 1.5 | 2026-07-04 | Emerson | Fix crítico: Explorer — `threading.Thread` → `QThread` + `moveToThread` worker pattern. Fix: `dict` em `QVariant` (Qt.UserRole+1) → JSON serializado. Fix: `_items_by_row` removido, navegação via `index.data()` independente de sort order. Fix: QThread lifecycle (shutdown/closeEvent) evita crash ao fechar app. 162 testes passando (21 funcionais E2E novos). Teste de copy E2E usa JSON metadata real nos QStandardItems |
| 1.6 | 2026-07-05 | Emerson | RF-16: Pastas de Sincronização (Sync Folders) — model, DB v2, SyncFolderService, watcher (inotify+debounce), poller (QTimer), manager, daemon (QCoreApplication), GUI (SyncFolderList+SyncFolderEditor), tray submenu, first-run, bisync flags em JobEditor. 86+ unit tests passando |

# Spec: Jobs de Sincronização

**Versão:** 1.0
**Status:** Rascunho
**Autor:** Emerson
**Data:** 2026-07-04
**Reviewers:** N/A

---

## 1. Resumo

Sistema de criação, configuração, agendamento e execução de jobs de sincronização (`sync`, `copy`, `move`, `bisync`) entre pares de paths (local/remoto), com monitoramento de progresso em tempo real via RC API, persistência em SQLite, e agendamento recorrente com expressões cron. É o core funcional do produto — a feature que entrega o valor principal de automação de transferências multi-cloud.

---

## 2. Contexto e Motivação

**Problema:**
Sincronizar arquivos entre múltiplas nuvens com rclone hoje requer:
- Escrever scripts shell com comandos `rclone sync` ou `rclone bisync`
- Configurar crontabs manualmente (`crontab -e`) sem feedback visual
- Lembrar dezenas de flags (`--checksum`, `--backup-dir`, `--bwlimit`, `--dry-run`, `--filter`)
- Depurar falhas lendo logs de arquivo sem interface de busca/filtro
- Testar mudanças com `--dry-run` mas sem diff visual do que será alterado
- Sem visão consolidada de múltiplos jobs — cada um roda isoladamente

**Evidências:**
- Scripts cron são a causa #1 de "sync silenciosamente falhou por 3 meses e eu não percebi"
- Usuários pedem "rclone GUI com scheduler" recorrentemente em issues e fóruns
- Ferramentas concorrentes (GoodSync, FreeFileSync) provam a demanda por sync UI com scheduling visual

**Por que agora:**
Jobs de sync são a principal razão para um usuário instalar uma GUI de rclone. As specs 01 (remotos) e 02 (explorador) são pré-requisitos — esta spec entrega a automação.

---

## 3. Goals (Objetivos)

- [ ] G-01: Permitir criar job de sync com seleção visual de origem e destino (usando explorador da Spec 02), configurar flags comuns via checkboxes/dropdowns, e salvar como entidade persistente
- [ ] G-02: Suportar os 4 modos de operação: `sync` (unidirecional, destrutivo no destino), `copy` (unidirecional, não-destrutivo), `move` (copia e remove origem), `bisync` (bidirecional)
- [ ] G-03: Exibir todas as flags relevantes organizadas por categoria (Básico, Filtros, Performance, Backup, Rede) com valores default sensíveis e descrições em PT-BR
- [ ] G-04: Oferecer execução manual (one-shot) com progresso em tempo real via RC API (`core/stats`): velocidade, ETA, arquivos transferidos, bytes, erros
- [ ] G-05: Permitir agendamento recorrente com frequências predefinidas + cron expression customizada, exibindo próximas execuções
- [ ] G-06: Manter histórico completo de execuções com status, duração, arquivos/bytes transferidos e log de erros pesquisável
- [ ] G-07: Suportar dry-run com diff visual (arquivos que seriam criados, atualizados, deletados) antes de executar o job real

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| Tempo para criar e agendar um job de sync | ~20 min (script + crontab) | < 5 min | Lançamento |
| Taxa de jobs concluídos sem erro (bem configurados) | Variável (script-dependente) | ≥ 95% | 3 meses |
| Jobs com dry-run antes da primeira execução real | ~0% (CLI requer flag explícita) | ≥ 80% | Lançamento |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: Resolução automática de conflitos no `bisync` — MVP apenas reporta conflitos no log; resolução interativa é fase 2
- NG-02: Sincronização seletiva de subpastas por remoto (tipo "escolher pastas para sincronizar" do Google Drive) — fase 2
- NG-03: Encadeamento de jobs (Job A → sucesso → Job B) — fase 2
- NG-04: Notificações push (mobile/email) de conclusão de job — fase 3
- NG-05: Comparação visual de diretórios lado a lado (tipo Beyond Compare) — fase 2

---

## 5. Usuários e Personas

**Usuário primário:** Bruno (sysadmin) — gerencia 5+ jobs de backup, precisa de confiabilidade, logs pesquisáveis e dry-run antes de cada mudança. Valoriza cron expressions e flags avançadas.

**Usuário secundário:** Ana (multi-cloud) — quer 2-3 jobs simples (semanal), com agendamento visual (não cron). Valoriza simplicidade, presets e indicações claras do que cada flag faz.

**Jornada atual (sem a feature):**
1. Bruno escreve script: `#!/bin/bash\nrclone sync /data/backups s3:bucket --backup-dir s3:old --bwlimit 10M`
2. Configura cron: `0 2 * * * /scripts/backup.sh >> /var/log/backup.log 2>&1`
3. Semanas depois, percebe que o backup falhou (log mostra erro de autenticação) — sem notificação
4. Para testar flag nova, precisa editar script, rodar manualmente, verificar resultado, reverter

**Jornada futura (com a feature):**
1. Bruno abre "Jobs", clica "Novo Job", seleciona tipo "Sync"
2. Seleciona origem (`/data/backups`) e destino (`s3:bucket`) via explorador two-panel
3. Expande "Opções Avançadas", ativa `--backup-dir`, configura `--bwlimit 10M`
4. Ativa "Dry-run primeiro" e clica "Executar" — vê diff (45 arquivos seriam copiados, 2 deletados)
5. Confirma diff está correto, desativa dry-run, executa — progresso em tempo real na tela
6. Agenda para "Diário às 02:00" — sistema salva job e scheduler assume
7. No dia seguinte, vê no histórico: job executou com sucesso, 47 arquivos, 2.1 GB, 8 min

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-S03-01 | O sistema deve permitir criar job com: nome, tipo (`sync`/`copy`/`move`/`bisync`), origem, destino, flags de configuração | Must | Formulário com validação: nome único, origem e destino obrigatórios, tipo selecionado; flags exibidas em seções expansíveis (Básico, Filtros, Performance, Backup, Rede) |
| RF-S03-02 | O sistema deve exibir seleção de origem e destino usando o explorador two-panel da Spec 02 em modo "seleção de path" (apenas diretórios) | Must | Botão "Selecionar" ao lado de cada campo abre explorador two-panel; ao confirmar, path é preenchido (ex: `/home/user/docs` ou `gdrive:Backup`) |
| RF-S03-03 | O sistema deve exibir flags do rclone como controles de formulário (checkbox, dropdown, spinbox, text input) organizados por categoria, com tooltips descritivos em PT-BR | Must | Todas as flags principais mapeadas: `--checksum` (checkbox), `--bwlimit` (text + unit selector KB/MB), `--transfers` (spinbox 1-64), `--checkers` (spinbox 1-256), `--backup-dir` (text + browse), `--dry-run` (checkbox), `--max-transfer` (text + unit), `--max-duration` (text), `--retries` (spinbox), `--delete-excluded` (checkbox, sync only), `--track-renames` (checkbox) |
| RF-S03-04 | O sistema deve persistir jobs no SQLite com todos os parâmetros: nome, tipo, origem, destino, flags (JSON), agendamento (cron expression), enabled, created_at, updated_at | Must | Tabela `sync_jobs` com colunas tipadas; operações CRUD via repositório dedicado; migração automática na primeira execução |
| RF-S03-05 | O sistema deve permitir agendar job com frequências predefinidas (minutos, horas, diário, semanal) ou cron expression customizada, exibindo próxima(s) execução(ões) | Must | Seletor de frequência com predefinições; campo "Cron Expression" para avançado (ex: `0 2 * * 1,3,5`); preview das próximas 5 execuções em formato legível (ex: "Próxima: Seg 07 Jul 02:00") |
| RF-S03-06 | O sistema deve executar job via subprocess (`rclone <type> source dest <flags>`) com progresso em tempo real obtido via RC API (`core/stats`) do daemon `rclone rcd` | Must | Ao iniciar execução, polling de `core/stats` a cada 1s exibindo: velocidade (up/down), ETA, % concluído (se bytes totais conhecidos), arquivos processados, erros acumulados, elapsed time |
| RF-S03-07 | O sistema deve permitir cancelar execução de job em andamento (via RC API `core/quit` ou signal SIGINT ao subprocess) | Must | Botão "Cancelar" na barra de progresso; ao cancelar, job é marcado como "cancelado" no histórico com estatísticas parciais |
| RF-S03-08 | O sistema deve registrar cada execução no histórico com: job_id, started_at, finished_at, status (running/success/failed/cancelled), files_transferred, bytes_transferred, errors_count, log_output (texto completo do log), trigger (manual/scheduled) | Must | Tabela `job_history` com índice em job_id e started_at; interface de histórico com filtros por job, status e período |
| RF-S03-09 | O sistema deve exibir diff visual no dry-run: lista de arquivos que seriam criados, atualizados, deletados (agrupados por ação) | Should | Após dry-run concluir, parsear output do rclone e exibir em três grupos: "Novos (12)", "Atualizados (3)", "Deletados (2)"; cada item mostra path e tamanho; opção "Exportar Diff" |
| RF-S03-10 | O sistema deve exibir lista de jobs com nome, tipo, status da última execução (ícone verde/amarelo/vermelho), próxima execução agendada, e toggle enable/disable | Must | Lista tipo tabela com colunas: Status, Nome, Tipo, Última Execução, Duração, Próxima Execução; ações: Executar Agora, Editar, Duplicar, Excluir, Enable/Disable |
| RF-S03-11 | O sistema deve permitir editar job existente (alterar parâmetros, flags, agendamento) preservando o histórico de execuções anterior | Must | Mesmo formulário de criação, pré-preenchido; flag de agendamento alterada recalcula próximas execuções; execuções em andamento não são interrompidas |
| RF-S03-12 | O sistema deve fornecer presets de configuração para cenários comuns: "Backup Simples" (sync, checksum, backup-dir), "Espelhamento" (copy, ignore-existing), "Sincronização Bidirecional" (bisync, track-renames, backup-dir), "Migração de Nuvem" (move, checksum) | Could | Dropdown "Preset" no topo do formulário; ao selecionar, flags são pré-configuradas com valores recomendados e tooltip explicando o cenário |
| RF-S03-13 | O sistema deve validar configuração do job antes de salvar/executar: verificar se origem e destino são acessíveis, se flags conflitantes não estão ativas simultaneamente | Should | Validação no submit: `about` na origem/destino para verificar acessibilidade; warning se `--dry-run` desativado para `sync` sem `--backup-dir` ("Sync sem backup-dir pode causar perda de dados. Configurar backup-dir?") |
| RF-S03-14 | O sistema deve gerenciar filtros de arquivo: `--include`, `--exclude`, `--filter`, `--files-from`, `--min-size`, `--max-size`, `--min-age`, `--max-age` | Should | Seção "Filtros" expansível com: textarea para regras de include/exclude (uma por linha), botão "Adicionar Regra" com dropdown de tipo, seletor de tamanho (>=, <=, entre), seletor de idade; preview: "Esta regra afetaria ~120 arquivos" via dry-run rápido |

### 6.2 Fluxo Principal (Happy Path) — Criar e Executar Job

1. O usuário navega para a aba "Jobs" e clica "Novo Job"
2. Seleciona tipo "Sync" do dropdown
3. Insere nome "Backup Diário Projetos"
4. Seleciona origem clicando em "Selecionar" → abre explorador two-panel → seleciona `/home/user/Projetos`
5. Seleciona destino → `gdrive:Backup/Projetos`
6. Expande "Opções de Backup", ativa `--backup-dir` e seleciona `gdrive:Backup/old`
7. Ativa "Executar Dry-run primeiro" (já ativo por padrão)
8. Em "Agendamento", seleciona "Diário" e horário "02:00"
9. Clica "Salvar e Executar Dry-run"
10. Dry-run conclui, diff é exibido: 12 novos, 3 atualizados, 0 deletados
11. Usuário confirma, clica "Executar Agora"
12. Barra de progresso mostra: "Enviando... 45 MB/s ↑ · 12/15 arquivos · ETA 8s"
13. Job conclui com sucesso — notificação "Backup Diário Projetos concluído: 15 arquivos, 234 MB"
14. Próxima execução agendada: "Amanhã 02:00"

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Bisync (Bidirecional):**
1. Usuário seleciona tipo "Bisync"
2. Sistema exibe aviso: "Sincronização bidirecional detecta mudanças em ambos os lados. Recomendamos fortemente configurar --backup-dir para recuperação de conflitos."
3. Flags específicas de bisync aparecem: `--resync` (checkbox), `--conflict-resolve` (dropdown: newer/older/larger/smaller/path1/path2), `--compare` (dropdown: size+modtime/checksum/size)
4. Ausência de `--backup-dir` gera warning vermelho (não bloqueia, mas exige clique extra para confirmar)

**Fluxo Alternativo B — Job com Filtros:**
1. Na seção "Filtros", usuário adiciona regra: "Excluir" → `*.tmp`
2. Adiciona regra: "Incluir" → `*.pdf`
3. Adiciona regra: "Tamanho mínimo" → 1 MB
4. Preview de filtros mostra 45 arquivos que passariam (de 230 no total) — via simulação rápida com `--dry-run --filter` (quando possível) ou estimativa
5. Sistema gera flags: `--exclude *.tmp --include *.pdf --min-size 1M`

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-S03-01 | Polling de progresso (RC API) não deve sobrecarregar o sistema | Polling a cada 1-2s, usando HTTP keep-alive; timeout de 5s por request | Se RC API falhar (daemon offline), fallback para parsing de stdout do subprocess |
| RNF-S03-02 | Execução de job não bloqueia a UI | Subprocess em QProcess com signals assíncronos; RC API polling em QThread separada | UI permanece responsiva durante syncs longos (horas) |
| RNF-S03-03 | Precisão do scheduler | Tolerância de ±5 segundos do horário agendado | Scheduler roda em thread dedicada com sleep granular; verifica a cada 30s por jobs a executar |
| RNF-S03-04 | Histórico de logs com tamanho controlado | Logs > 10 MB por execução são truncados (últimos 10 MB); rotação de histórico: manter últimos 1000 registros por padrão, configurável | Evita crescimento ilimitado do SQLite |
| RNF-S03-05 | Máximo de jobs simultâneos | 3 jobs executando em paralelo (configurável). Excedente fica em fila "Aguardando..." | Múltiplos subprocessos rclone simultâneos competem por banda — limitar por padrão |
| RNF-S03-06 | Timezone-aware scheduling | Jobs agendados usam o timezone do sistema; DST transitions são tratadas corretamente | Usar biblioteca `zoneinfo` (Python 3.9+) para cálculos de próxima execução |

---

## 8. Design e Interface

### Componentes afetados
- **JobListWidget (QWidget):** tabela de jobs com status, ações, toggle enable/disable
- **JobEditorDialog (QDialog):** formulário completo de criação/edição de job
- **FlagEditorWidget (QWidget):** seções expansíveis com controles mapeados para flags rclone
- **FilterEditorWidget (QWidget):** sub-seção de filtros com lista de regras e preview
- **JobProgressWidget (QWidget):** barra de progresso, estatísticas em tempo real, botão cancelar
- **JobHistoryWidget (QWidget):** tabela filtrável de execuções passadas com expand para log completo
- **SchedulePicker (QWidget):** seletor de frequência + cron expression + preview de próximas execuções
- **DryRunDiffWidget (QWidget):** diff visual com grupos de ações (criar/atualizar/deletar)

### Comportamento esperado
- Jobs desabilitados (toggle off) não são executados pelo scheduler mas podem ser executados manualmente
- Ao editar um job que está com execução em andamento, o formulário abre em modo leitura com aviso "Este job está em execução. Alterações só terão efeito na próxima execução."
- Botão "Executar Agora" abre diálogo de confirmação se o job não tem dry-run ativo e é do tipo `sync` ou `move`
- Progresso de múltiplos jobs simultâneos é exibido em abas ou stacked view com indicador de quantos ativos

### Estados da UI
- **Estado vazio (sem jobs):** ilustração central "Nenhum job de sincronização" + botão "Criar Primeiro Job"
- **Estado de carregamento (salvando job):** botão "Salvar" mostra spinner e fica disabled; feedback "Salvando..."
- **Estado de execução:** barra de progresso com gradiente azul, estatísticas atualizando a cada 1s, botão "Cancelar" vermelho visível
- **Estado de erro (job falhou):** badge vermelho no job list; ao expandir, log de erro formatado com destaque na linha do erro; botão "Reexecutar" e "Exportar Log"
- **Estado de sucesso (job concluído):** badge verde no job list; toast notification no canto inferior direito
- **Estado dry-run:** diff visual com fundo amarelo claro (indicando "simulação"); botões "Confirmar e Executar" e "Cancelar"

---

## 9. Modelo de Dados

### Entidades (persistidas no SQLite)

```
SyncJob {
  id: INTEGER PRIMARY KEY AUTOINCREMENT
  name: TEXT NOT NULL UNIQUE
  job_type: TEXT NOT NULL              // 'sync', 'copy', 'move', 'bisync'
  source: TEXT NOT NULL                // Path origem (local ou remote:path)
  destination: TEXT NOT NULL           // Path destino
  flags: TEXT NOT NULL DEFAULT '{}'   // JSON com flags {checksum: true, bwlimit: "10M", ...}
  filters: TEXT DEFAULT '[]'          // JSON array de regras de filtro
  schedule_enabled: INTEGER DEFAULT 0  // 0=apenas manual, 1=agendado
  schedule_cron: TEXT                  // Cron expression (ex: "0 2 * * *")
  schedule_type: TEXT                  // 'manual', 'minutes', 'hourly', 'daily', 'weekly', 'custom'
  schedule_interval: INTEGER           // Intervalo em minutos (para tipos não-cron)
  enabled: INTEGER DEFAULT 1           // 0=desabilitado, 1=habilitado
  dry_run_first: INTEGER DEFAULT 1     // Executar dry-run antes do job real
  created_at: TEXT NOT NULL            // ISO 8601
  updated_at: TEXT NOT NULL
}

JobExecution {
  id: INTEGER PRIMARY KEY AUTOINCREMENT
  job_id: INTEGER NOT NULL REFERENCES SyncJob(id) ON DELETE CASCADE
  status: TEXT NOT NULL                // 'running', 'success', 'failed', 'cancelled'
  trigger: TEXT NOT NULL               // 'manual', 'scheduled'
  started_at: TEXT NOT NULL            // ISO 8601
  finished_at: TEXT                    // ISO 8601 (NULL enquanto running)
  duration_seconds: REAL               // NULL enquanto running
  files_transferred: INTEGER DEFAULT 0
  files_checked: INTEGER DEFAULT 0
  bytes_transferred: INTEGER DEFAULT 0
  errors_count: INTEGER DEFAULT 0
  fatal_error: TEXT                    // Mensagem de erro fatal (se status=failed)
  log_output: TEXT                     // Log completo da execução
  is_dry_run: INTEGER DEFAULT 0
}

SchedulerState {
  id: INTEGER PRIMARY KEY DEFAULT 1    // Singleton row
  last_check_at: TEXT                  // Última verificação do scheduler
  next_job_id: INTEGER                 // ID do próximo job a executar
}

FilterRule {
  // Embutido no JSON filters do SyncJob, mas com estrutura definida:
  type: 'include' | 'exclude' | 'filter' | 'min_size' | 'max_size' | 'min_age' | 'max_age' | 'files_from'
  pattern: str                         // Pattern da regra (ex: "*.tmp", "1M", "7d")
  description: str?                    // Descrição opcional para UI
}
```

### Migrações necessárias
Sim — criar tabelas `sync_jobs`, `job_history`, `scheduler_state` na primeira inicialização. Migrações versionadas no SQLite (coluna `schema_version` na tabela `app_meta`).

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| `rclone` binário (sync/copy/move/bisync) | Obrigatória | Nenhum job pode ser executado |
| RC API (`rclone rcd` — `core/stats`) | Obrigatória (para progresso) | Fallback: parsing de stdout (`--progress -P`) do subprocess para estatísticas básicas. RC API ausente = sem progresso granular |
| Gerenciamento de Remotos (Spec 01) | Obrigatória | Sem remotos, origem/destino ficam limitados a paths locais |
| Explorador de Arquivos (Spec 02) | Obrigatória | Seleção visual de origem/destino usa o explorador two-panel; sem ele, apenas input de texto manual |
| Daemon (Spec 07) | Obrigatória (para scheduler) | Sem daemon, apenas execução manual; scheduler não funciona |
| SQLite | Obrigatória | Sem SQLite, jobs não são persistidos entre sessões |
| Biblioteca de cron parsing (`croniter` Python) | Obrigatória (para scheduler) | Sem croniter, apenas frequências predefinidas; sem suporte a custom cron expression |
| D-Bus (notificações) | Opcional | Notificações de conclusão/falha de job não aparecem; funcionalidade core não afetada |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-S03-01: Job agendado enquanto sistema está desligado | Horário agendado passou durante shutdown | Na inicialização do daemon, verificar jobs com execução perdida (missed); oferecer "Executar agora" ou "Pular esta execução" |
| EC-S03-02: Duas instâncias do mesmo job iniciadas acidentalmente | Usuário clica "Executar" enquanto scheduler também dispara | Lock por job: antes de iniciar, verificar se já existe `JobExecution` com status 'running' para o mesmo job; se sim, ignorar segundo disparo e logar "Job já em execução" |
| EC-S03-03: Origem ou destino offline no momento da execução | Backend retorna erro de conexão | Job falha com status "failed" e mensagem "Origem/Destino offline: [detalhe do erro]"; tentar 3 vezes com intervalo de 30s (se `--retries` configurado) |
| EC-S03-04: Espaço insuficiente no destino durante sync | Backend retorna "quota exceeded" ou "disk full" | Job falha; log inclui espaço usado/disponível no destino; sugestão: "Considere usar --max-transfer para limitar o tamanho da transferência" |
| EC-S03-05: Arquivo bloqueado na origem durante leitura | Arquivo em uso por outro processo | rclone reporta erro; sistema tenta novamente conforme `--retries`; se falha definitiva, log inclui path do arquivo e erro; job continua processando outros arquivos |
| EC-S03-06: Conflito no bisync — arquivo alterado em ambos os lados | Dois usuários editaram o mesmo arquivo entre sincronizações | Bisync reporta conflito; job conclui como "success" com warnings; log lista arquivos em conflito; sugestão de configurar `--conflict-resolve` |
| EC-S03-07: Job muito rápido (< 1s) | Poucos arquivos para sincronizar | Progresso pode piscar — exibir "Concluído em < 1s" sem barra de progresso; histórico registra normalmente |
| EC-S03-08: Job dura várias horas/dias | Grande volume de dados | UI mantém polling de progresso; se usuário fechar a GUI e reabrir, job ainda em execução aparece na lista com barra de progresso retomada |
| EC-S03-09: Migração de schema do SQLite entre versões | Nova versão da aplicação adiciona campos ao SyncJob | Migração automática com backup do banco antes de ALTER TABLE; se falhar, logar erro e manter banco antigo (modo compatibilidade) |
| EC-S03-10: Usuário edita flags manualmente no JSON e quebra a estrutura | Edição manual do arquivo de config ou SQLite | Validação de schema do JSON ao carregar; se inválido, resetar flags para default e logar warning "Flags do job X estavam corrompidas e foram resetadas" |

---

## 12. Segurança e Privacidade

- **Autenticação:** Não se aplica — jobs executam sob o usuário do SO que iniciou a GUI.
- **Autorização:** Operações no destino usam as mesmas permissões do remoto configurado no `rclone.conf`. A GUI não eleva privilégios.
- **Dados sensíveis:** Logs de execução podem conter paths de arquivos que revelam informações pessoais (nomes de projetos, estrutura de diretórios). Logs são armazenados localmente no SQLite com permissões de arquivo restritas ao usuário (0600). Exportação de log é opcional e advertida.
- **Auditoria:** Toda execução de job é registrada com timestamp, trigger e status. Logs são imutáveis no histórico.

---

## 13. Plano de Rollout

- **Estratégia:** Feature flag — `enable_scheduler` (padrão false no primeiro release), liberado quando Daemon (Spec 07) estiver estável. Inicialmente apenas execução manual de jobs.
- **Como reverter (rollback):** Desabilitar scheduler via flag. Jobs manuais continuam funcionando. Desinstalar o scheduler não apaga jobs salvos.
- **Monitoramento pós-deploy:** Métricas de jobs: taxa de sucesso, duração média, erros mais comuns. Telemetria anônima de flags mais usadas para guiar presets futuros.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-S03-01 | O `rclone rcd` expõe endpoint para iniciar job e acompanhar progresso (`core/stats`), mas `core/stats` não é isolado por job — como diferenciar progresso de múltiplos jobs simultâneos? | Alto — arquitetura de progresso paralelo | Emerson | Validar com experimento antes da implementação |
| OQ-S03-02 | O que acontece quando o job falha parcialmente (alguns arquivos ok, outros com erro)? O rclone reporta isso como exit code ≠ 0? O job deve ser marcado como "failed" ou "partial"? | Médio — UX de status de job | Emerson | Especificar antes da implementação |
| OQ-S03-03 | Devemos usar `rclone sync` diretamente para cada job ou passar pelo RC API `sync/copy` e `sync/move`? Qual a diferença de progress reporting? | Alto — afeta toda a implementação de execução | Emerson | Validar com a documentação da RC API antes da implementação |
| OQ-S03-04 | Como exibir progresso quando ETA é desconhecido (bytes totais não são conhecidos — ex: sync sem `--max-transfer` e com backend que não reporta total)? | Médio — UX da barra de progresso | Emerson | Especificar antes da implementação |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| Polling de progresso via RC API (`core/stats`) em vez de parsing de stdout | (1) Stdout com `--progress -P`, (2) `--use-json-log` + parsing | RC API retorna JSON estruturado e permite consulta sob demanda. Stdout parsing é frágil (mudanças de formato, escape sequences). JSON log é arquivo — polling de arquivo não é melhor que HTTP |
| Flags armazenadas como JSON no SQLite em vez de colunas individuais | (1) Coluna por flag (~30 colunas), (2) Tabela de flags separada | JSON é flexível — novas flags não exigem migração de schema. A maioria das queries é "carregar job completo" (não filtrar por flag específica) |
| Cron expression via `croniter` em vez de implementar parser próprio | (1) Parser próprio, (2) systemd timer units | `croniter` é maduro, testado e compatível com cron padrão. Systemd timers são específicos do Linux e limitam portabilidade futura |
| Limite de 3 jobs simultâneos por padrão | (1) Ilimitado, (2) 1 por vez | Múltiplos subprocessos rclone competem por banda e recursos. 3 é um trade-off razoável entre paralelismo e saturação. Configurável nas preferências |
| Salvamento de flag `--dry-run` como checkbox persistente no job | (1) Dry-run apenas como botão separado, (2) Dry-run forçado para todo primeiro sync | Checkbox permite fluxo "dry-run primeiro" automático e o usuário pode desabilitar quando confiante. Flexível e explícito |

---

## Apêndice

### Referências
- [rclone sync docs](https://rclone.org/commands/rclone_sync/)
- [rclone copy docs](https://rclone.org/commands/rclone_copy/)
- [rclone move docs](https://rclone.org/commands/rclone_move/)
- [rclone bisync docs](https://rclone.org/commands/rclone_bisync/)
- [rclone RC API docs](https://rclone.org/rc/)
- [rclone flags reference](https://rclone.org/flags/)
- PRD.md — Seção 3.1, RF-04, RF-05, RF-06, RF-07, RF-15

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-07-04 | Emerson | Criação inicial |

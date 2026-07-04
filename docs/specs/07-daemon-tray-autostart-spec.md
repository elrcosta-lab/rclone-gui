# Spec: Daemon, System Tray e Autostart

**Versão:** 1.2
**Status:** Implementado
**Autor:** Emerson
**Data:** 2026-07-04
**Reviewers:** N/A

---

## 1. Resumo

Processo daemon de background que gerencia o ciclo de vida do `rclone rcd` (Remote Control API), executa jobs agendados (Spec 03), mantém mounts ativos (Spec 04), provê ícone no system tray com status e atalhos, e inicia automaticamente no login do usuário. É a camada de integração desktop que orquestra todas as demais specs, permitindo que a aplicação funcione como um serviço contínuo estilo Google Drive for desktop.

---

## 2. Contexto e Motivação

**Problema:**
- Jobs agendados (Spec 03) precisam de um processo rodando continuamente para disparar execuções — não dependem da GUI estar aberta
- Montagens automáticas no login (Spec 04) precisam de um processo que inicie com o sistema
- O `rclone rcd` (RC API) precisa estar rodando como serviço para fornecer progresso em tempo real e controle remoto
- Sem um daemon unificado, cada funcionalidade precisaria de seu próprio mecanismo de persistência (cron, systemd units, scripts de init)

**Evidências:**
- Google Drive for desktop, Dropbox, OneDrive — todos usam um daemon de background com tray icon
- Usuários esperam que aplicações de sincronização "simplesmente funcionem" sem abrir a janela principal
- `rclone rcd` é a peça central de automação recomendada pela documentação

**Por que agora:**
O daemon é a última spec — ele orquestra todas as anteriores. Sem ele, a aplicação é apenas uma GUI efêmera que perde o estado ao fechar. Com ele, é um serviço contínuo de sincronização multi-cloud.

---

## 3. Goals (Objetivos)

- [ ] G-01: Executar como processo de background que inicia com o sistema (autostart) e continua rodando independentemente da GUI
- [ ] G-02: Gerenciar ciclo de vida do `rclone rcd`: iniciar, monitorar saúde, reiniciar se necessário
- [ ] G-03: Prover ícone no system tray com status visual (verde/amarelo/vermelho) e menu de contexto com atalhos
- [ ] G-04: Executar jobs agendados (Spec 03) nos horários configurados, com tolerância a missed executions
- [ ] G-05: Auto-montar remotos configurados (Spec 04) na inicialização
- [ ] G-06: Enviar notificações do sistema (D-Bus) sobre eventos relevantes: job concluído, mount falhou, erro de conexão
- [ ] G-07: Permitir que a GUI se conecte ao daemon para recuperar estado (jobs ativos, mounts, progresso) ao ser aberta

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| Jobs agendados executados no horário | 0 (não existe) | ≥ 99% de pontualidade (±30s) | Lançamento |
| Autostart funcional em Linux (systemd ou XDG autostart) | N/A | 100% das distros alvo | Lançamento |
| Consumo de recursos em idle | N/A | < 50 MB RAM, < 1% CPU | Lançamento |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: Daemon como serviço system-wide (systemd system unit) — MVP usa systemd user unit ou XDG autostart (.desktop). Serviço system-wide é fase 2 para cenários multi-usuário
- NG-02: Dashboard web via `rclone rcd` — fase 3
- NG-03: Gerenciamento remoto (controlar daemon de outra máquina) — fase 3
- NG-04: Tray icon com animações complexas (gráficos de velocidade, etc.) — MVP apenas ícone de status simples

---

## 5. Usuários e Personas

**Usuário primário:** Ana — quer que o ícone no tray fique verde e ela não precise pensar nisso. Quer notificações quando algo der errado. Não quer abrir a janela principal no dia a dia.

**Usuário secundário:** Bruno — quer controle fino: logs do daemon, verificar status de jobs via tray, abrir a GUI rapidamente quando precisar configurar algo novo. Valoriza baixo consumo de recursos.

**Usuário terciário:** Carla — nunca interage diretamente. O daemon foi configurado uma vez e deve simplesmente funcionar. Se algo falhar, o ícone muda de cor e ela pede ajuda.

**Jornada atual (sem a feature):**
1. Bruno configura scripts cron manualmente
2. Não há feedback visual de status
3. Precisa abrir terminal para ver logs
4. Precisa lembrar de iniciar `rclone rcd` manualmente se quiser usar RC API

**Jornada futura (com a feature):**
1. Instala a aplicação, configura remotos e jobs
2. Ativa "Iniciar com o sistema" nas preferências
3. Reinicia o computador — o daemon inicia automaticamente
4. Ícone no tray aparece verde: "Rclone GUI — 3 remotos, 2 jobs ativos"
5. Trabalha normalmente — syncs acontecem em background
6. Recebe notificação: "Backup Diário concluído — 234 arquivos"
7. Ao clicar no ícone do tray, menu rápido: "Abrir Rclone GUI", "Montagens (2 ativas)", "Jobs (1 executando)"
8. Se algo falha, ícone fica vermelho e notificação explica o erro

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-S07-01 | O sistema deve prover dois modos de execução: GUI standalone (para desenvolvimento/ debug) e Daemon + GUI (produção), onde o daemon gerencia rclone rcd, scheduler e mounts | Must | Flag `--daemon` inicia apenas o daemon (sem GUI); sem flag, inicia a GUI que detecta e conecta-se ao daemon ou o inicia sob demanda |
| RF-S07-02 | O daemon deve iniciar, monitorar e reiniciar (se necessário) o processo `rclone rcd` com porta e credenciais configuráveis | Must | Inicia `rclone rcd --rc-addr localhost:5572 --rc-user rgui --rc-pass <random>`; health check a cada 30s via `rc/noop`; se falhar 3x consecutivas, reinicia o processo |
| RF-S07-03 | O daemon deve carregar jobs agendados do SQLite e executá-los nos horários configurados via scheduler interno (croniter) | Must | Scheduler verifica jobs a cada 30s; ao detectar job devido, executa via subprocess (Spec 03); lock por job previne execução duplicada; missed executions são detectadas na inicialização |
| RF-S07-04 | O daemon deve montar automaticamente remotos com `auto_mount=1` (Spec 04) ao iniciar, com retry em caso de falha por rede | Must | Ao iniciar, itera `mount_configs` com auto_mount=1; executa montagem sequencial (para evitar sobrecarga); se falhar por rede, agenda retry a cada 60s até sucesso ou timeout de 10 min |
| RF-S07-05 | O sistema deve exibir ícone no system tray (QSystemTrayIcon) com: ícone de status (verde/amarelo/vermelho), tooltip informativo, menu de contexto com atalhos | Must | Verificação de disponibilidade de tray no startup; se não disponível (ex: Wayland sem XWayland), loga warning e continua sem tray |
| RF-S07-06 | O menu de contexto do tray deve conter: "Abrir Rclone GUI", "Montagens" (submenu com remotos montados + ação Abrir Pasta / Desmontar), "Jobs" (submenu com último status de cada job), "Pausar Sincronizações", "Sair" | Must | Menu dinâmico atualizado quando montagens/jobs mudam de estado; separador entre ações e informações de status |
| RF-S07-07 | O sistema deve enviar notificações nativas do desktop (D-Bus/freedesktop Notification) para: job concluído (sucesso/falha), mount caiu, erro de conexão com remoto, atualização disponível | Must | Notificações usam `org.freedesktop.Notifications` via D-Bus; categorizadas com ícones; não repetir mesma notificação em < 5 min (dedup) |
| RF-S07-08 | O sistema deve configurar autostart via arquivo `.desktop` em `~/.config/autostart/rclone-gui-daemon.desktop` quando usuário ativar "Iniciar com o sistema" | Must | Preferência "Iniciar com o sistema" toggla o autostart; `.desktop` file é criado/removido; comando executa o binário com `--daemon` |
| RF-S07-09 | A GUI deve detectar se o daemon está rodando ao ser aberta e conectar-se a ele para recuperar estado (jobs ativos, mounts, progresso). Se não estiver, oferecer iniciá-lo | Must | Comunicação GUI↔Daemon via socket Unix (`/tmp/rclone-gui.sock`) com mensagens JSON simples; se daemon offline, diálogo "O daemon não está rodando. Iniciar agora?" |
| RF-S07-10 | O sistema deve expor status resumido via tray: tooltip "Rclone GUI — 3 remotos, 2 montados, 1 job executando" e ícone de status composto (verde=tudo ok, amarelo=job em andamento ou mount pendente, vermelho=erro) | Must | Status consolidado: prioridade de exibição = vermelho > amarelo > verde; tooltip atualizado a cada evento de mudança de estado |
| RF-S07-11 | O sistema deve oferecer "Pausar Todas as Sincronizações" no menu do tray, que pausa o scheduler (não inicia novos jobs) e opcionalmente pausa jobs em andamento via RC API (`core/bwlimit rate=off` como aproximação) | Could | Toggle "Pausar/Retomar" no menu; quando pausado, ícone do tray mostra overlay de pause; jobs em andamento continuam mas novos não iniciam |
| RF-S07-12 | O sistema deve manter log rotativo do daemon (inicialização, scheduler events, erros do rcd, montagens) em arquivo `~/.local/share/rclone-gui/daemon.log` | Must | Log rotativo: máximo 5 arquivos de 1 MB cada; nível configurável (DEBUG/INFO/WARNING/ERROR) nas preferências; logs disponíveis via "Ver Logs" no menu do tray |

### 6.2 Fluxo Principal (Happy Path) — Ciclo de Vida do Daemon

1. Usuário faz login no sistema → `~/.config/autostart/rclone-gui-daemon.desktop` é executado
2. Processo daemon inicia: carrega configurações do SQLite, verifica dependências (rclone, FUSE)
3. Inicia `rclone rcd` em subprocess com porta e credenciais aleatórias
4. Aguarda RC API responder (`rc/noop`)
5. Carrega mounts configurados e monta remotos com auto_mount=1
6. Inicia scheduler: verifica jobs agendados, calcula próxima execução
7. Cria socket Unix para comunicação GUI↔Daemon
8. Exibe tray icon com status verde: "Rclone GUI — Tudo sincronizado"
9. Scheduler detecta job devido → executa via QProcess → polling de progresso → ao concluir, notificação
10. Usuário abre GUI → conecta ao daemon via socket → recupera estado atual (jobs, mounts, progresso)
11. Usuário fecha GUI → daemon continua rodando com tray icon

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Daemon iniciado pela GUI (sob demanda):**
1. Usuário abre GUI sem daemon rodando
2. GUI detecta socket ausente → diálogo "O daemon não está rodando. Iniciar?"
3. Confirma → GUI inicia daemon como subprocess → aguarda socket → conecta

**Fluxo Alternativo B — Recuperação de crash do rclone rcd:**
1. Daemon detecta que `rclone rcd` não responde a 3 health checks consecutivos
2. Tenta reiniciar o processo (kill + start)
3. Se 3 tentativas de restart falham: notificação "Erro no serviço rclone — verifique os logs" + ícone vermelho + log detalhado
4. Scheduler e mounts continuam funcionando (não dependem do RC API para operação básica)

**Fluxo Alternativo C — Tray não disponível (headless/Wayland sem XWayland):**
1. Daemon inicia normalmente
2. Detecta que QSystemTrayIcon não é suportado
3. Loga "System tray não disponível neste ambiente. O daemon continuará rodando em background."
4. Toda funcionalidade core (scheduler, mounts, rcd) funciona normalmente via socket/GUI

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-S07-01 | Consumo de memória em idle (daemon + rclone rcd) | < 50 MB | Medido após 5 min de idle, sem jobs ou mounts ativos |
| RNF-S07-02 | Consumo de CPU em idle | < 1% (de um core) | Timer de scheduler a cada 30s, health check a cada 30s |
| RNF-S07-03 | Tempo de inicialização do daemon | < 5s até tray icon visível e RC API respondendo | Inclui startup do rclone rcd (tipicamente < 2s) |
| RNF-S07-04 | Sobrevivência a sleep/hibernate | Daemon deve sobreviver a suspend/resume; reconectar RC API se necessário | Verificar saúde do rcd após resume; reconectar mounts se caíram |
| RNF-S07-05 | Comunicação GUI↔Daemon | Socket Unix (`/tmp/rclone-gui.sock`) com timeout de 5s; mensagens JSON < 64 KB | Se socket falhar, GUI pode iniciar daemon próprio ou executar em modo standalone |
| RNF-S07-06 | Robustez do scheduler | Clock skew do sistema não deve causar execuções duplicadas ou perdidas | Usar monotonic clock para timers internos (QElapsedTimer); comparar com wall clock a cada verificação |
| RNF-S07-07 | Arquivo de autostart | `.desktop` file válido conforme especificação XDG | Verificado com `desktop-file-validate` |

---

## 8. Design e Interface

### Componentes afetados
- **DaemonApplication (QApplication ou QCoreApplication):** entry point do daemon, sem GUI, com event loop para timers/sockets
- **TrayManager (QSystemTrayIcon):** gerenciamento do ícone e menu de contexto
- **RcdManager:** ciclo de vida do `rclone rcd` (start, health check, restart)
- **SchedulerService:** carrega jobs do SQLite, gerencia timers de execução
- **MountService:** auto-mount de remotos no boot, health check de mounts
- **NotificationService:** envio de notificações via D-Bus com dedup
- **GuiDaemonBridge:** socket Unix para comunicação bidirecional GUI ↔ Daemon
- **AutostartManager:** criação/remoção do arquivo `.desktop` em `~/.config/autostart/`

### Comportamento esperado
- O daemon usa `QCoreApplication` (não `QApplication`) para minimizar overhead — apenas o tray precisa de `QApplication`
- Se o daemon rodar com tray, inicializa `QApplication`; se rodar em modo headless, `QCoreApplication`
- A GUI, ao iniciar, tenta conectar ao socket do daemon; se conectado, exibe estado atual; se não, oferece iniciar daemon
- Ao fechar a GUI, o comportamento padrão é "minimizar para tray" (se daemon com tray) ou "fechar" (se daemon headless)
- O tray icon é um recurso do daemon — não da GUI

### Estados da UI (Tray)
- **Ícone verde:** todos os sistemas operacionais, sem jobs ativos, sem erros. Tooltip: "Rclone GUI — Tudo sincronizado"
- **Ícone amarelo:** job em andamento ou mount pendente. Tooltip: "Rclone GUI — 1 job em andamento"
- **Ícone amarelo com pause overlay:** sincronizações pausadas. Tooltip: "Rclone GUI — Sincronizações pausadas"
- **Ícone vermelho:** erro (rcd offline, mount falhou, job falhou). Tooltip: "Rclone GUI — 1 erro detectado"
- **Menu de contexto:** dinâmico, reagindo a eventos de mudança de estado (signals do SchedulerService, MountService, RcdManager)

---

## 9. Modelo de Dados

### Entidades (SQLite — complementam as tabelas das specs anteriores)

```
AppConfig {
  id: INTEGER PRIMARY KEY DEFAULT 1    // Singleton row
  autostart_enabled: INTEGER DEFAULT 0
  tray_enabled: INTEGER DEFAULT 1
  minimize_to_tray: INTEGER DEFAULT 1
  close_to_tray: INTEGER DEFAULT 1
  rcd_port: INTEGER DEFAULT 5572
  rcd_user: TEXT DEFAULT 'rgui'
  rcd_pass_hash: TEXT                  // Hash da senha aleatória do rcd
  daemon_log_level: TEXT DEFAULT 'INFO'
  notifications_enabled: INTEGER DEFAULT 1
  notifications_job_success: INTEGER DEFAULT 1
  notifications_job_failure: INTEGER DEFAULT 1
  notifications_mount_error: INTEGER DEFAULT 1
  first_run_completed: INTEGER DEFAULT 0
  created_at: TEXT NOT NULL
  updated_at: TEXT NOT NULL
}

DaemonState {                          // Em memória + sincronizado via socket
  rcd_online: bool
  rcd_port: int
  active_jobs: [job_id, ...]           // IDs de jobs em execução
  active_mounts: [remote_name, ...]    // Remotos montados
  paused: bool
  uptime_seconds: int
}
```

### Migrações necessárias
Sim — criar tabela `app_config` na primeira inicialização.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| `rclone rcd` | Obrigatória (para daemon) | Progresso em tempo real e controle via RC API indisponíveis; scheduler ainda funciona via subprocess direto |
| System tray (Qt + ambiente desktop) | Opcional | Daemon funciona sem tray; status acessível apenas via GUI ou socket |
| D-Bus (notificações) | Opcional | Notificações silenciosamente desabilitadas; funcionalidade core não afetada |
| XDG Autostart (`~/.config/autostart/`) | Opcional | Autostart não funciona — usuário precisa iniciar manualmente |
| Socket Unix (`/tmp/rclone-gui.sock`) | Obrigatória (para GUI↔Daemon) | GUI não consegue se conectar ao daemon; pode iniciar daemon próprio ou rodar standalone |
| SQLite | Obrigatória | Configurações, jobs e mounts não são carregados |
| Spec 03 (Jobs de Sync) | Obrigatória | Scheduler não tem jobs para executar |
| Spec 04 (Montagem VFS) | Obrigatória | Auto-mount não tem configurações para montar |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-S07-01: Daemon já rodando ao tentar iniciar outro | Segundo processo detecta socket já em uso | Segundo processo exibe notificação "Rclone GUI já está em execução" e abre a GUI conectada ao daemon existente (ou traz a GUI existente para frente) |
| EC-S07-02: Porta RC API ocupada | Outro processo usando a porta 5572 | Tentar porta seguinte (5573, 5574...) até achar livre; atualizar `app_config.rcd_port`; logar aviso |
| EC-S07-03: Falha ao criar socket Unix | Permissão negada em `/tmp/` | Tentar socket em `$XDG_RUNTIME_DIR/rclone-gui.sock` como fallback |
| EC-S07-04: rclone rcd morre durante job em andamento | Crash do rclone | Job continua rodando via subprocess direto (não depende do RC API); progresso para de atualizar até rcd reiniciar; ao reiniciar rcd, polling de progresso retorna |
| EC-S07-05: Sistema vai dormir com job agendado | Suspend durante janela de execução | Ao acordar, scheduler detecta missed executions e oferece executar jobs perdidos (ou marcar como missed) |
| EC-S07-06: Múltiplas notificações em curto intervalo | Vários jobs concluem ao mesmo tempo | Dedup: mesma categoria de notificação não é enviada em < 5 min; agrupar: "3 jobs concluídos" em vez de 3 notificações separadas |
| EC-S07-07: `.desktop` file de autostart corrompido ou removido externamente | Usuário ou outro programa deleta o arquivo | Na próxima inicialização da GUI, detectar que `autostart_enabled=1` mas arquivo não existe → recriar ou perguntar ao usuário |
| EC-S07-08: Daemon inicia antes do ambiente gráfico (tray não disponível ainda) | Login automático ou script de init precoce | Daemon espera até 30s pelo tray ficar disponível (polling `QSystemTrayIcon.isSystemTrayAvailable()`); se timeout, continua sem tray |

---

## 12. Segurança e Privacidade

- **Autenticação RC API:** Senha aleatória gerada na primeira execução e armazenada com hash no SQLite. Acesso apenas via localhost. Nunca exposta à rede.
- **Socket Unix:** Permissões restritas (0600), acessível apenas ao usuário dono do processo. Localizado em `/tmp/` ou `$XDG_RUNTIME_DIR`.
- **Autostart:** Arquivo `.desktop` em diretório do usuário — sem privilégios de root. Pode ser removido pelo usuário a qualquer momento.
- **Dados sensíveis em logs:** Logs do daemon podem conter paths de arquivos. Arquivo de log com permissões 0600. Nível DEBUG desabilitado por padrão.
- **Dados sensíveis via socket:** Metadados de jobs e mounts trafegam no socket Unix local. Nunca são transmitidos secrets ou tokens (estes ficam no `rclone.conf`).

---

## 13. Plano de Rollout

- **Estratégia:** Feature flag `mode: standalone | daemon`. Inicialmente, modo standalone (GUI inicia rcd internamente). Daemon + tray habilitado quando Spec 03 e Spec 04 estiverem estáveis.
- **Como reverter (rollback):** Remover arquivo de autostart e encerrar daemon. GUI volta a funcionar em modo standalone.
- **Monitoramento pós-deploy:** Health metrics do daemon (uptime, crashes, memory); taxa de sucesso de jobs agendados vs. manuais; tempo de resposta do socket.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-S07-01 | Qual abordagem para autostart: XDG autostart (.desktop) ou systemd user unit? Ou ambos com detecção automática? | Alto — compatibilidade entre distros | Emerson | Validar em Ubuntu, Fedora, Arch, Debian |
| OQ-S07-02 | O tray icon funciona em Wayland puro (sem XWayland)? Qt6 com `QT_QPA_PLATFORM=wayland` suporta QSystemTrayIcon? | Alto — crescente adoção de Wayland | Emerson | Testar em GNOME Wayland, KDE Wayland |
| OQ-S07-03 | Como lidar com atualização do binário rclone enquanto o daemon está rodando? `rclone rcd` usa o binário substituído em disco? | Médio — experiência de atualização | Emerson | Documentar: "Reinicie o daemon após atualizar o rclone" |
| OQ-S07-04 | Deve haver um watchdog externo (systemd timer) para garantir que o daemon sempre esteja rodando, ou o autostart é suficiente? | Médio — confiabilidade | Emerson | Decidir com base em testes de estabilidade |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| Daemon como processo separado (não thread dentro da GUI) | (1) Thread na GUI, (2) Subprocesso gerenciado | Processo separado permite que a GUI seja fechada sem interromper scheduler e mounts. Thread morreria com o processo pai. Subprocesso gerenciado (QProcess) é ok, mas daemon como processo independente é mais robusto |
| Socket Unix para comunicação GUI↔Daemon em vez de HTTP/RC API ou DBus | (1) HTTP (localhost com porta), (2) D-Bus session bus | Socket Unix é simples, não consome porta TCP, não requer bibliotecas D-Bus complexas. JSON sobre socket é suficiente para as mensagens de estado |
| XDG autostart (.desktop) como padrão em vez de systemd user unit | (1) systemd user unit, (2) Ambos | .desktop funciona em todos os DEs (GNOME, KDE, XFCE, etc.) que seguem spec XDG. systemd user units são específicas de distros com systemd. .desktop é mais portável e mais simples de criar programaticamente |
| Senha do RC API aleatória e armazenada com hash, não fixa | (1) Senha fixa "rgui", (2) Sem autenticação | Segurança: RC API sem autenticação exporia controle total do rclone para qualquer processo local. Senha aleatória + hash protege contra leitura acidental do SQLite |
| `QCoreApplication` para daemon headless, `QApplication` para daemon com tray | (1) Sempre QApplication, (2) Processo separado para tray | `QCoreApplication` é mais leve (não inicializa subsistemas gráficos). Daemon escolhe no startup com base na disponibilidade de display e configuração |
| Tooltip do tray consolidado (resumo) em vez de lista completa de status | (1) Lista detalhada de cada remoto/job | Tooltip tem espaço limitado; resumo é mais escaneável (tipo Dropbox: "Dropbox — Up to date"). Detalhes disponíveis no menu de contexto e na GUI |

---

## Apêndice

### Referências
- [rclone RC API docs](https://rclone.org/rc/)
- [rclone rcd docs](https://rclone.org/commands/rclone_rcd/)
- [XDG Autostart Specification](https://specifications.freedesktop.org/autostart-spec/autostart-spec-latest.html)
- [D-Bus Notifications Specification](https://specifications.freedesktop.org/notification-spec/notification-spec-latest.html)
- [Qt QSystemTrayIcon docs](https://doc.qt.io/qt-6/qsystemtrayicon.html)
- [Qt QLocalServer/QLocalSocket docs](https://doc.qt.io/qt-6/qlocalserver.html)
- PRD.md — Seção 3.1, RF-11, RF-12, RF-13

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-07-04 | Emerson | Criação inicial |
| 1.1 | 2026-07-04 | Emerson | Implementação completa: tray manager, autostart .desktop, rcd subprocess, notificações D-Bus |
| 1.2 | 2026-07-04 | Emerson | Fix: `setup_autostart`/`remove_autostart` adicionadas em `notification.py`. rcd test corrigido GET→POST. Validação 36/36 confirma tray, autostart e rcd |

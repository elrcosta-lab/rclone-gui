# Spec: Montagem VFS (Virtual File System)

**Versão:** 1.1
**Status:** Implementado
**Autor:** Emerson
**Data:** 2026-07-04
**Reviewers:** N/A

---

## 1. Resumo

Feature que permite montar remotos configurados como drives no sistema de arquivos local via FUSE (`rclone mount`), oferecendo experiência equivalente ao Google Drive for desktop: o remoto aparece como uma pasta normal no gerenciador de arquivos (Nautilus, Dolphin, etc.), com cache VFS configurável, montagem automática opcional no login, e indicadores visuais de status de montagem no tray icon.

---

## 2. Contexto e Motivação

**Problema:**
- `rclone mount` é um comando CLI que exige conhecimento de FUSE, paths e flags
- Montar manualmente no terminal é impraticável para usuários não-técnicos
- Configurar opções de cache (`--vfs-cache-mode`, `--vfs-cache-max-age`, etc.) requer consulta à documentação
- Gerenciar múltiplos mounts (desmontar quando não está em uso, remontar após reboot) é trabalhoso
- O Google Drive for desktop popularizou a expectativa de "acesso a nuvem como pasta local" — usuários esperam isso

**Evidências:**
- `rclone mount` é um dos comandos mais populares do rclone (amplamente documentado em tutoriais e fóruns)
- Ferramentas como `rclone-browser` (descontinuada) focavam primariamente em browse + mount
- Usuários frequentemente criam scripts de init para montar remotos no boot — indicando demanda por automação

**Por que agora:**
A montagem VFS é a feature diferenciadora que torna a GUI uma alternativa real ao Google Drive for desktop e outros clientes proprietários. Junto com o daemon (Spec 07), fecha o ciclo de integração desktop.

---

## 3. Goals (Objetivos)

- [ ] G-01: Montar qualquer remoto configurado como filesystem local via `rclone mount` com um clique
- [ ] G-02: Oferecer configuração visual das opções de cache VFS (mode, max-age, max-size, cache-dir)
- [ ] G-03: Exibir status de montagem (montado/desmontado/erro) com ponto de montagem acessível via botão "Abrir no Gerenciador de Arquivos"
- [ ] G-04: Permitir montagem automática de remotos selecionados no login do usuário
- [ ] G-05: Gerenciar múltiplos mounts simultâneos com opções individuais por remoto

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| Tempo para montar um remoto pela primeira vez | ~5 min (CLI + docs + FUSE setup) | < 30s (assumindo FUSE instalado) | Lançamento |
| Mounts sobrevivendo a reboot | 0 (CLI não persiste) | 100% dos mounts configurados como automáticos | Lançamento |
| Uso de cache VFS configurado | ~20% (usuários CLI que conhecem as flags) | ≥ 80% (via presets visuais) | Lançamento |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: Montagem NFS (`rclone nfsmount`) — apenas FUSE (`rclone mount`) no MVP
- NG-02: Mount de subpastas específicas (selective mount) — montagem sempre da raiz do remoto no MVP; navegação dentro da pasta montada é feita pelo gerenciador de arquivos
- NG-03: Virtual filesystem com placeholders (tipo OneDrive "Files on Demand") — arquivos são baixados sob demanda pelo FUSE, mas sem indicadores visuais de "arquivo apenas online"
- NG-04: Compartilhamento de mounts com outros usuários do sistema (`--allow-other`) — fase 2
- NG-05: Suporte a macOS (FUSE for macOS) e Windows (WinFsp) — fase 2

---

## 5. Usuários e Personas

**Usuário primário:** Ana — quer acessar Google Drive e Dropbox como pastas normais no seu gerenciador de arquivos, igual ao Google Drive for desktop que usava no Windows. Não sabe o que é FUSE. Valoriza "simplesmente funcionar".

**Usuário secundário:** Bruno — quer montar buckets S3 como filesystem para debug e acesso rápido a logs, com cache agressivo para performance. Valoriza controle sobre cache mode e mount flags. Pode querer desmontar e remontar com flags diferentes.

**Jornada atual (sem a feature):**
1. Instala FUSE (`sudo apt install fuse3`)
2. Adiciona-se ao grupo `fuse` (`sudo usermod -aG fuse $USER`)
3. Cria ponto de montagem (`mkdir ~/mnt/gdrive`)
4. Executa: `rclone mount gdrive: ~/mnt/gdrive --vfs-cache-mode writes --daemon`
5. Para desmontar: `fusermount -u ~/mnt/gdrive`
6. Para automontar: edita `/etc/fstab` ou cria script systemd user unit

**Jornada futura (com a feature):**
1. Abre a GUI, vê lista de remotos
2. Clica no botão "Montar" ao lado de "Meu Google Drive"
3. Diálogo de configuração de montagem com presets e opções de cache
4. Confirma — remoto é montado em `~/Rclone/Montagens/Meu Google Drive`
5. Clica "Abrir Pasta" — o gerenciador de arquivos nativo abre no ponto de montagem
6. Ativa "Montar ao iniciar" — nas próximas sessões, o daemon monta automaticamente
7. Ícone no tray mostra indicador verde "1 remoto montado"

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-S04-01 | O sistema deve montar um remoto via `rclone mount <remote>: <mountpoint> [flags]` executado como subprocess em background | Must | `rclone mount` é executado com flags configuradas; ponto de montagem padrão: `~/Rclone/Montagens/<nome-do-remoto>`; diretório criado automaticamente se não existir |
| RF-S04-02 | O sistema deve exibir diálogo de configuração de montagem com: ponto de montagem (browse), modo de cache VFS, e flags avançadas (opcionais) | Must | Modal com: campo de mountpoint (default preenchido, browse button), dropdown de cache mode (off/minimal/writes/full), spinbox max-age, campo max-size, checkbox "Montar ao iniciar o sistema" |
| RF-S04-03 | O sistema deve oferecer presets de configuração de cache: "Streaming" (off, sem disco), "Escritório" (writes, 1h cache), "Uso Intenso" (full, 24h cache) | Should | Ao selecionar preset, campos são preenchidos com valores recomendados e tooltip explicando o cenário |
| RF-S04-04 | O sistema deve desmontar remoto via `fusermount -u <mountpoint>` com verificação de que não está em uso | Must | Antes de desmontar, verificar se há processos usando o mountpoint (`lsof` ou similar); se houver, alertar: "O remoto está em uso por [N] processos. Forçar desmontagem?" |
| RF-S04-05 | O sistema deve exibir indicador de status de montagem para cada remoto na lista principal: ícone verde (montado), cinza (desmontado), amarelo (montando/desmontando), vermelho (erro) | Must | Status é atualizado em tempo real via signals; tooltip mostra ponto de montagem e tempo de atividade (ex: "Montado em ~/Rclone/Montagens/gdrive há 3 horas") |
| RF-S04-06 | O sistema deve permitir abrir o ponto de montagem no gerenciador de arquivos nativo via `xdg-open <mountpoint>` | Should | Botão "Abrir Pasta" visível quando remoto está montado; ícone de pasta ao lado do status |
| RF-S04-07 | O sistema deve persistir configurações de montagem por remoto (mountpoint, cache mode, flags, auto_mount) no SQLite | Must | Tabela `mount_configs` com chave estrangeira para remote_name; carregada na inicialização e usada pelo daemon para auto-mount |
| RF-S04-08 | O sistema deve suportar montagem automática no login via daemon (Spec 07), respeitando a flag `auto_mount` de cada remoto | Must | Daemon, ao iniciar, lê `mount_configs` e executa `rclone mount` para cada remoto com auto_mount=1; se mount falhar, loga erro e notifica usuário |
| RF-S04-09 | O sistema deve verificar dependências (FUSE, fusermount, permissões de grupo) antes de tentar montar e exibir instruções de instalação se ausentes | Must | Startup check: `which fusermount` + verificação de `/dev/fuse` legível; se falhar, exibir diálogo "FUSE não está instalado ou configurado. Deseja ver instruções de instalação?" com link para wiki |
| RF-S04-10 | O sistema deve monitorar a saúde do mount (processo `rclone mount` ainda rodando? mountpoint ainda acessível?) e reportar ao tray | Should | Health check a cada 60s: verificar se PID do subprocess ainda existe e se mountpoint está na tabela de mounts (`/proc/mounts` ou `mount`); se caiu, tentar remontar automaticamente (se auto_mount) e notificar |
| RF-S04-11 | O sistema deve configurar flags de rede no mount: `--timeout`, `--contimeout`, `--low-level-retries`, `--bwlimit` | Could | Aba "Rede" no diálogo de configuração com campos de timeout, retries e bwlimit específicos para o mount |

### 6.2 Fluxo Principal (Happy Path) — Montar Remoto

1. O usuário seleciona "Meu Google Drive" na lista de remotos
2. Clica no botão "Montar"
3. Diálogo de configuração abre com valores default:
   - Ponto de montagem: `~/Rclone/Montagens/Meu Google Drive`
   - Cache mode: "writes" (preset Escritório)
   - Montar ao iniciar: desmarcado
4. Usuário aceita os defaults e clica "Montar"
5. Sistema cria diretório `~/Rclone/Montagens/Meu Google Drive`
6. Executa: `rclone mount "Meu Google Drive:" "/home/ana/Rclone/Montagens/Meu Google Drive" --vfs-cache-mode writes --daemon`
7. Aguarda ~2s e verifica se mountpoint aparece em `/proc/mounts`
8. Status do remoto muda para verde "Montado"
9. Toast: "Meu Google Drive montado com sucesso"

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Montar com Preset "Uso Intenso":**
1. Usuário seleciona preset "Uso Intenso" no diálogo
2. Campos são preenchidos: cache mode = full, max-age = 24h, max-size = 10G
3. Subprocess: `rclone mount remote: mountpoint --vfs-cache-mode full --vfs-cache-max-age 24h --vfs-cache-max-size 10G --daemon`

**Fluxo Alternativo B — Desmontar Remoto:**
1. Usuário clica em "Desmontar" ao lado do remoto montado
2. Sistema verifica processos usando o mountpoint
3. Executa: `fusermount -u mountpoint`
4. Se sucesso: status muda para cinza, diretório de mountpoint não é removido (pode conter cache)
5. Se falha: exibe diálogo de erro com opção "Forçar desmontagem" (`fusermount -uz mountpoint`)

**Fluxo Alternativo C — Mountpoint já em uso por outro processo:**
1. Usuário tenta montar no path `/mnt/gdrive` que já tem outro mount
2. Sistema detecta mount existente (via `/proc/mounts`)
3. Exibe aviso: "O diretório /mnt/gdrive já está montado. Deseja montar em um diretório alternativo?" e sugere path alternativo

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-S04-01 | Tempo de montagem | < 5s para montar (assumindo backend já autenticado e FUSE já inicializado) | O subprocess `rclone mount --daemon` retorna em < 2s; verificação de mountpoint em /proc/mounts completa em < 1s |
| RNF-S04-02 | Sobrevivência do mount | Mount deve sobreviver a: sleep/wake do sistema, desconexão temporária de rede (com retry), o próprio processo `rclone mount` é um daemon separado | rclone mount com `--daemon` roda como processo filho independente |
| RNF-S04-03 | Cache VFS não deve consumir todo o disco | Respeitar `--vfs-cache-max-size`; se não configurado, usar default 1G para full mode | Avisar usuário se cache-dir está com pouco espaço |
| RNF-S04-04 | Mount não bloqueia a UI | A operação de mount é assíncrona; polling de verificação de mountpoint a cada 500ms até 10s, depois reporta sucesso/erro | QProcess com signal `finished` conectado ao callback de verificação |
| RNF-S04-05 | Compatibilidade FUSE | Suporte a libfuse3 (recomendado) e libfuse2 (fallback); verificação de versão no startup | `rclone mount` usa libfuse automaticamente; verificar com `fusermount -V` |
| RNF-S04-06 | Permissões de mountpoint | Diretório criado com permissões 0755; mount acessível apenas ao usuário dono (`--allow-other=false` por padrão) | Segurança: não expor arquivos em nuvem para outros usuários do sistema |

---

## 8. Design e Interface

### Componentes afetados
- **MountDialog (QDialog):** configuração de mount com presets, campos de cache e flags avançadas
- **MountStatusIndicator (QWidget):** badge de status no card do remoto (verde/cinza/amarelo/vermelho)
- **MountHealthMonitor (QObject):** timer que verifica saúde dos mounts periodicamente (sinaliza erros)
- **TrayIcon (Spec 07):** indicador de mounts ativos no menu do tray e ícone de status

### Comportamento esperado
- A operação de montar/desmontar é assíncrona — o botão mostra spinner enquanto processa
- Ao fechar a GUI, mounts ativos permanecem rodando (processo `rclone mount --daemon` é independente)
- Auto-mount é gerenciado pelo daemon (Spec 07), não pela GUI
- Ponto de montagem padrão usa nome do remoto sanitizado (substituir espaços e caracteres problemáticos)

### Estados da UI
- **Estado desmontado:** ícone cinza, botão "Montar", sem ponto de montagem ativo
- **Estado montando:** ícone amarelo com spinner, botão "Montando..." disabled, mensagem "Iniciando montagem..."
- **Estado montado:** ícone verde, botão "Desmontar", link "Abrir Pasta", info "Montado há X min"
- **Estado desmontando:** ícone amarelo com spinner, botão "Desmontando..." disabled
- **Estado de erro:** ícone vermelho, mensagem do erro, botão "Tentar Novamente" e "Ver Detalhes"
- **Estado sem FUSE:** banner no topo "FUSE não encontrado. Instale o fuse3 para usar montagem de remotos." com link

---

## 9. Modelo de Dados

### Entidades (SQLite)

```
MountConfig {
  id: INTEGER PRIMARY KEY AUTOINCREMENT
  remote_name: TEXT NOT NULL UNIQUE    // Nome do remoto no rclone.conf
  mountpoint: TEXT NOT NULL            // Path absoluto (ex: /home/user/Rclone/gdrive)
  cache_mode: TEXT DEFAULT 'writes'    // 'off', 'minimal', 'writes', 'full'
  cache_max_age: TEXT DEFAULT '1h'     // Duração (ex: '1h', '24h', '168h')
  cache_max_size: TEXT DEFAULT '1G'    // Tamanho (ex: '1G', '10G')
  cache_dir: TEXT                      // Diretório de cache customizado (NULL = default do rclone)
  auto_mount: INTEGER DEFAULT 0        // 0=manual, 1=automático no login
  network_timeout: TEXT DEFAULT '10m'  // --timeout
  network_low_level_retries: INTEGER DEFAULT 10
  bwlimit: TEXT                        // --bwlimit específico do mount (NULL = sem limite)
  extra_flags: TEXT                    // Flags adicionais em JSON (para opções não cobertas pelos campos)
  created_at: TEXT NOT NULL
  updated_at: TEXT NOT NULL
}

MountState {                           // Em memória (não persistido diretamente, mas inferido)
  remote_name: str
  is_mounted: bool
  mountpoint: str?
  pid: int?                            // PID do processo rclone mount
  mounted_at: datetime?
  last_health_check: datetime?
  health_status: 'ok' | 'error' | 'unknown'
}
```

### Migrações necessárias
Sim — criar tabela `mount_configs` na primeira inicialização.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| `rclone mount` | Obrigatória | Nenhum remoto pode ser montado |
| FUSE (libfuse + kernel module) | Obrigatória | Montagem indisponível; exibir instruções de instalação |
| `fusermount` | Obrigatória | Impossível desmontar via GUI; usuário precisaria usar `umount` no terminal |
| `xdg-open` | Opcional | Botão "Abrir Pasta" não funciona — usuário precisa navegar manualmente até o mountpoint |
| Gerenciamento de Remotos (Spec 01) | Obrigatória | Sem remotos configurados, nada para montar |
| Daemon (Spec 07) | Obrigatória (para auto-mount) | Auto-mount no login não funciona; montagem manual ainda disponível |
| SQLite | Obrigatória | Configurações de montagem não persistem entre sessões; defaults são usados toda vez |
| `/proc/mounts` (ou comando `mount`) | Obrigatória | Impossível verificar estado de montagem; alternativa: verificar PID do processo |
| D-Bus (notificações) | Opcional | Sem notificação de mount bem-sucedido ou falha |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-S04-01: Usuário não está no grupo `fuse` | Permissão negada ao executar `rclone mount` | Verificar grupo antes de tentar montar; se ausente, exibir: "Você precisa estar no grupo 'fuse' para montar remotos. Executar: sudo usermod -aG fuse $USER e reiniciar a sessão" |
| EC-S04-02: Mountpoint já existe e não está vazio | Diretório contém arquivos de uma montagem anterior que falhou | Verificar se diretório está vazio; se não, alertar: "O diretório de montagem contém arquivos. Recomenda-se esvaziar antes de montar." com opção "Montar mesmo assim" |
| EC-S04-03: Processo `rclone mount` morre silenciosamente | Crash do rclone, OOM killer, sinal externo | Health check detecta PID ausente e mountpoint não listado; tentar remontar se auto_mount=true; notificar usuário com erro |
| EC-S04-04: Montagem sobrevive a logout mas não a reboot | Mount foi feito com `--daemon` mas sem persistência systemd | Auto-mount via daemon (Spec 07) resolve isso — mounts são recriados no boot pelo daemon |
| EC-S04-05: Conflito de cache entre múltiplos mounts | Dois remotos configurados com mesmo cache-dir | Validar unicidade de cache-dir no formulário; se conflito, alertar e sugerir paths separados |
| EC-S04-06: `rclone mount` compila FUSE module em runtime e demora | Primeiro mount após instalação pode levar 10-30s | Diálogo de montagem mostra spinner com mensagem "Preparando sistema de arquivos... (isso pode levar alguns segundos na primeira vez)" |
| EC-S04-07: Desmontagem forçada pode causar perda de cache não-escrito | Usuário força desmontagem enquanto arquivos estão sendo escritos | Alertar: "Forçar desmontagem pode causar perda de dados não salvos. Deseja continuar?" + sugestão de esperar sync terminar |
| EC-S04-08: Mountpoint contém caracteres especiais no nome do remoto | Remoto chamado "Backup:Diário" contém `:` | Sanitizar nome para mountpoint: substituir `:` e `/` por `-`; alertar usuário sobre a sanitização |
| EC-S04-09: Backend offline no momento do auto-mount | Login ocorre sem internet | Daemon tenta montar, falha, agenda retry para quando conexão for detectada; notifica usuário "Não foi possível montar 'gdrive' — sem conexão. Tentando novamente quando a rede estiver disponível" |

---

## 12. Segurança e Privacidade

- **Autenticação:** O mount usa as credenciais já configuradas no `rclone.conf`. Não há elevação de privilégios.
- **Autorização:** Mount é acessível apenas ao usuário que o criou (`--allow-other=false` por padrão). O ponto de montagem tem permissões 0700.
- **Dados sensíveis:** Arquivos acessados via mount passam pelo cache VFS local. Se o cache estiver em disco, os dados são acessíveis a quem tiver acesso ao filesystem. Recomendar que cache-dir esteja em filesystem criptografado (documentado, não forçado).
- **Auditoria:** Log de operações de mount/desmontar com timestamp é mantido. Não audita acesso a arquivos individuais dentro do mount (isso é responsabilidade do kernel/filesystem).

---

## 13. Plano de Rollout

- **Estratégia:** Feature com verificação de FUSE no startup. Se FUSE ausente, botão "Montar" aparece desabilitado com tooltip explicativo e link de instalação.
- **Como reverter (rollback):** Desabilitar auto-mount para todos os remotos. Mounts existentes podem ser desmontados manualmente.
- **Monitoramento pós-deploy:** Métricas de mounts: taxa de sucesso, tempo médio de montagem, erros mais comuns. Verificar compatibilidade com diferentes versões de libfuse e kernels.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-S04-01 | O `rclone mount` com `--daemon` no Linux (FUSE) é estável o suficiente para uso diário como filesystem primário? Ou o mount deve ser recriado periodicamente? | Alto — confiabilidade do produto | Emerson | Validar com testes de longa duração |
| OQ-S04-02 | Como lidar com hibernate/suspend? Mounts FUSE sobrevivem a suspend/resume? | Médio — UX | Emerson | Testar em diferentes distros |
| OQ-S04-03 | O cache-dir deve ter um tamanho máximo gerenciado pelo rclone ou precisamos de lógica adicional de cleanup? O `--vfs-cache-max-size` cobre todos os cenários? | Médio — gerenciamento de disco | Emerson | Validar documentação do rclone |
| OQ-S04-04 | Como integrar melhor com gerenciadores de arquivos (Nautilus, Dolphin) para mostrar indicadores visuais de sync status nos arquivos (emblemas/overlays como Dropbox e Google Drive)? | Baixo — feature avançada | Emerson | Investigar para fase 2 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| Usar `rclone mount --daemon` (processo independente) em vez de manter como subprocess filho da GUI | (1) Subprocess filho, (2) systemd mount unit | `--daemon` é o modo recomendado pelo rclone — o processo se desacopla da GUI, sobrevive ao fechamento dela e é gerenciado pelo kernel. Subprocess filho morreria com a GUI. Systemd units seriam o ideal mas são específicas do Linux e complexas de gerenciar programaticamente |
| Ponto de montagem padrão em `~/Rclone/Montagens/` em vez de `/mnt/` ou diretório oculto | (1) `/mnt/rclone/`, (2) `~/.rclone/mounts/` | Diretório visível no home é mais amigável e navegável pelo gerenciador de arquivos. `/mnt/` requer root. Diretório oculto (`.rclone`) confunde usuários que não encontram a pasta |
| Cache VFS "writes" como default em vez de "off" | (1) off (streaming), (2) full (máximo cache) | "writes" é o melhor trade-off: leituras são diretas do backend (economiza disco), escritas são cacheadas e sincronizadas em background (performance e confiabilidade). Recomendado pela documentação do rclone para uso geral |
| Verificação de FUSE no startup da GUI, não no momento do mount | (1) Verificar apenas no momento do mount, (2) Não verificar | Verificação antecipada permite mostrar instruções de instalação antes do usuário tentar montar, melhorando a primeira experiência |
| Saúde do mount via polling de `/proc/mounts` + PID, não via RC API | (1) RC API `vfs/stats`, (2) Apenas verificar PID | `/proc/mounts` é universal no Linux, não depende do RC API estar rodando, e indica se o filesystem está realmente montado. PID sozinho é frágil (processo zumbi) |

---

## Apêndice

### Referências
- [rclone mount docs](https://rclone.org/commands/rclone_mount/)
- [rclone VFS caching](https://rclone.org/commands/rclone_mount/#vfs-file-caching)
- [FUSE wiki](https://github.com/libfuse/libfuse)
- [rclone RC API vfs/*](https://rclone.org/rc/#vfs)
- PRD.md — Seção 3.1, RF-08

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-07-04 | Emerson | Criação inicial |

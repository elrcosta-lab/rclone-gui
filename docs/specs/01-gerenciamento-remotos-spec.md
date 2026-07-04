# Spec: Gerenciamento de Remotos (Config de Backends)

**Versão:** 1.0
**Status:** Rascunho
**Autor:** Emerson
**Data:** 2026-07-04
**Reviewers:** N/A

---

## 1. Resumo

Feature que permite ao usuário configurar, visualizar, editar e remover backends de armazenamento (remotos) via assistente visual, substituindo o `rclone config` interativo por uma wizard GUI com busca textual de backends, formulários dinâmicos por tipo, preview do arquivo de configuração e delegação de OAuth ao `rclone authorize`. É a feature fundacional — sem remotos configurados, nenhuma outra funcionalidade da aplicação está disponível.

---

## 2. Contexto e Motivação

**Problema:**
O `rclone config` é um wizard textual (CLI) que exige que o usuário: (a) saiba o nome exato do tipo de backend (~50+ opções), (b) navegue por prompts sequenciais sem visão geral do que será preenchido, (c) lide com mensagens de erro pouco amigáveis, (d) execute `rclone authorize` separadamente em outro terminal para backends OAuth. Para um usuário não-técnico, isso é uma barreira intransponível. Para usuários técnicos, é lento e propenso a erros de digitação.

**Evidências:**
- Issues frequentes no GitHub do rclone sobre dificuldade de configurar backends específicos
- Primeiro contato com rclone é o `rclone config` — uma má experiência aqui afasta o usuário permanentemente
- Aplicações concorrentes (clientes nativos de Google Drive, Dropbox) resolvem configuração com 2-3 cliques + login OAuth

**Por que agora:**
Sem esta feature, a GUI não tem propósito — o usuário precisa de remotos configurados para qualquer operação subsequente. É o requisito #1 do MVP.

---

## 3. Goals (Objetivos)

- [ ] G-01: Permitir que um usuário configure qualquer backend suportado pelo rclone em ≤ 3 minutos sem usar o terminal
- [ ] G-02: Oferecer busca textual com autocomplete para os ~50+ tipos de backend, com descrições em linguagem natural
- [ ] G-03: Exibir formulário dinâmico por tipo de backend, com campos obrigatórios sinalizados e validação em tempo real
- [ ] G-04: Delegar fluxos OAuth ao `rclone authorize` com feedback visual (browser aberto → aguardando autorização → token recebido)
- [ ] G-05: Permitir editar e excluir remotos existentes, com preview das alterações antes de salvar
- [ ] G-06: Exibir informações de quota (`rclone about`) para remotos configurados que suportam o comando

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| Tempo de configuração de um novo remoto | ~15 min (CLI) | < 3 min | Lançamento |
| Taxa de sucesso na configuração (sem abandono) | Desconhecida | ≥ 90% | Teste de usabilidade |
| Cobertura de tipos de backend no wizard | ~50 (todos CLI) | ≥ 45 backends | Lançamento |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: Edição manual do arquivo `rclone.conf` como texto raw — o wizard substitui essa necessidade
- NG-02: Criação de remotos on-the-fly via `:backend:` (connection strings) — fase 2
- NG-03: Gerenciamento de criptografia de configuração (`rclone config encrypt/password`) — fase 2
- NG-04: Importação/exportação de remotos entre máquinas — fase 2
- NG-05: Sincronização de configuração entre instâncias da GUI — fase 3

---

## 5. Usuários e Personas

**Usuário primário:** Ana (usuária multi-cloud não-técnica) — precisa configurar 3 backends (Google Drive, Dropbox, Backblaze B2) sem ajuda externa. Valoriza clareza, labels descritivos e indicações visuais de progresso.

**Usuário secundário:** Bruno (sysadmin) — precisa configurar rapidamente backends SFTP e S3 para scripts de backup. Valoriza eficiência: busca rápida, preenchimento com valores default sensíveis, e opção de pular telas não relevantes.

**Jornada atual (sem a feature):**
1. Abre o terminal e digita `rclone config`
2. Lê lista textual de ~50 backends (ex: "s3 / Amazon S3 Compliant Storage Provider")
3. Digita o nome do backend (pode errar — sem autocomplete)
4. Responde prompts sequenciais (às vezes 10+ perguntas) sem ver o que vem depois
5. Para backends OAuth: sai do fluxo, executa `rclone authorize "drive"` em outro terminal, copia token manualmente
6. Se erra um valor, precisa refazer todo o fluxo ou editar o arquivo manualmente

**Jornada futura (com a feature):**
1. Abre a GUI, clica em "Adicionar Remoto"
2. Digita "Google Drive" na busca — o backend aparece como primeiro resultado com ícone
3. Vê formulário com 3 campos (client_id, client_secret, scope) — todos com descrições e placeholders
4. Clica em "Autorizar" — o browser abre, faz login no Google, volta para a GUI
5. Clica em "Salvar" — o remoto aparece na lista com status "Online" e quota (7.2 GB / 15 GB)

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-S01-01 | O sistema deve exibir lista de remotos configurados com nome, tipo de backend, status (online/offline) e quota (quando disponível) | Must | A lista é populada via `rclone listremotes` e `rclone about` ao abrir a tela; remotos sem resposta em 10s são marcados como offline |
| RF-S01-02 | O sistema deve permitir busca textual de tipo de backend com autocomplete entre todos os tipos suportados pelo rclone | Must | O usuário digita "goo" e vê "Google Drive", "Google Cloud Storage", "Google Photos" como sugestões; cada item exibe ícone e descrição |
| RF-S01-03 | O sistema deve exibir formulário dinâmico de configuração baseado no tipo de backend selecionado, com campos organizados em seções lógicas (Autenticação, Avançado) | Must | Para Google Drive: campos client_id, client_secret, scope, root_folder_id; campos obrigatórios marcados com asterisco; campos avançados colapsados |
| RF-S01-04 | O sistema deve delegar fluxo OAuth ao `rclone authorize`, exibindo estado do processo (iniciando → aguardando browser → autorização concluída) | Must | Ao clicar "Autorizar", `rclone authorize "drive"` é executado; output do comando é parseado para extrair token; token é preenchido automaticamente no formulário |
| RF-S01-05 | O sistema deve validar campos do formulário em tempo real (tipos, formatos, obrigatoriedade) e exibir mensagens de erro inline | Should | Campo numérico rejeita texto; campo obrigatório vazio mostra borda vermelha + mensagem "Campo obrigatório"; validação ocorre no blur do campo |
| RF-S01-06 | O sistema deve salvar nova configuração no `rclone.conf` via `rclone config create`, preservando a formatação existente do arquivo | Must | Após submit, `rclone config create <nome> <tipo> <param1=valor1> <param2=valor2>` é executado; em caso de erro, exibe mensagem e mantém formulário aberto |
| RF-S01-07 | O sistema deve permitir editar remoto existente: abrir formulário pré-preenchido com valores atuais, alterar campos, salvar via `rclone config update` | Must | Ao clicar "Editar" em um remoto, o formulário carrega valores do `rclone config show <nome>`; campos sensíveis (token, password) são mascarados com placeholder "••••••••" |
| RF-S01-08 | O sistema deve permitir excluir remoto com confirmação explícita e opção de remover também as seções de configuração associadas | Must | Ao clicar "Excluir", diálogo de confirmação: "Tem certeza que deseja remover o remoto 'gdrive'? Esta ação não pode ser desfeita." Executa `rclone config delete <nome>` |
| RF-S01-09 | O sistema deve permitir duplicar remoto (criar cópia com novo nome) preservando todas as configurações exceto campos OAuth/token | Should | "Duplicar" abre formulário com mesmo tipo e valores, nome sufixado com "_copia"; campos de autenticação OAuth são limpos para reautorização |
| RF-S01-10 | O sistema deve exibir informações de quota do remoto (usado, livre, total) via `rclone about` quando suportado pelo backend | Should | Ao selecionar um remoto, painel lateral exibe barra de progresso de uso (ex: 7.2 GB de 15 GB); se `about` falhar (backend não suporta), exibe "Quota não disponível para este backend" |
| RF-S01-11 | O sistema deve exibir preview da configuração (como aparecerá no `rclone.conf`) antes de salvar, com opção de editar como texto raw | Could | Aba "Preview" no wizard mostra conteúdo INI formatado; campos editáveis diretamente (textarea) para usuários avançados |
| RF-S01-12 | O sistema deve detectar e alertar sobre nomes de remotos duplicados antes de salvar | Must | Ao submeter formulário com nome já existente, exibe erro: "Já existe um remoto com o nome 'backup'. Escolha outro nome." |

### 6.2 Fluxo Principal (Happy Path) — Adicionar Remoto

1. O usuário clica em "Adicionar Remoto" na tela de gerenciamento de remotos
2. O sistema abre o wizard: tela 1 — busca de tipo de backend
3. O usuário digita "Drive" — o sistema sugere "Google Drive", "Huawei Drive", "OpenDrive", etc.
4. O usuário seleciona "Google Drive" — o sistema avança para tela 2: formulário de configuração
5. O usuário insere nome: "Meu Google Drive" (o sistema sugere "gdrive" automaticamente a partir do nome)
6. O usuário preenche campos obrigatórios ou clica em "Autorizar com Google"
7. O sistema executa `rclone authorize "drive"` — abre browser, usuário faz login, token é recebido e preenchido automaticamente
8. O usuário revisa o preview da configuração e clica em "Salvar"
9. O sistema executa `rclone config create` — remoto aparece na lista com status "Online" e quota

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Editar Remoto Existente:**
1. O usuário seleciona um remoto na lista e clica em "Editar"
2. O sistema carrega formulário pré-preenchido com `rclone config show <nome>`
3. O usuário altera campos desejados
4. O sistema salva via `rclone config update <nome> <param=valor>`

**Fluxo Alternativo B — Backend sem OAuth (ex: SFTP):**
1. O usuário seleciona "SFTP" no wizard
2. O formulário exibe campos: host, port, user, key_file. Sem botão "Autorizar"
3. O usuário preenche manualmente e salva

**Fluxo Alternativo C — OAuth com falha de browser (headless):**
1. O usuário clica em "Autorizar" mas não há browser disponível
2. O sistema exibe URL de autorização para copiar manualmente e campo para colar o token de volta
3. O usuário completa o fluxo manualmente

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-S01-01 | Tempo de resposta da busca de backends | < 200ms para filtrar ~50 itens | Lista estática carregada no startup, busca é local (filtro em memória) |
| RNF-S01-02 | Parsing de `rclone config show` | < 500ms para remotos com até 50 parâmetros | Output é INI — espera-se parse rápido |
| RNF-S01-03 | Timeout de `rclone authorize` | 120s | Após timeout, exibir mensagem "Autorização demorou mais que o esperado. Verifique o browser." |
| RNF-S01-04 | Atomicidade de escrita no `rclone.conf` | Operações de create/update/delete não devem corromper o arquivo | Usar backup automático: copiar `rclone.conf` para `rclone.conf.bak` antes de qualquer escrita |
| RNF-S01-05 | Validação de nome de remoto | Conforme regras do rclone: números, letras, `_`, `-`, `.`, `+`, `@`, espaço; não começar com `-` ou espaço; não terminar com espaço; case sensitive | Validação client-side + mensagem clara de regra violada |

---

## 8. Design e Interface

### Componentes afetados
- **Tela principal de Remotos:** lista de remotos com ações (Adicionar, Editar, Duplicar, Excluir)
- **Wizard de Configuração (QDialog/QWizard):** fluxo de 2-3 telas: seleção de backend → formulário de configuração → preview + salvar
- **Painel de Detalhes do Remoto:** informações de quota, tipo, data de criação (quando disponível)
- **Diálogo de Confirmação de Exclusão:** modal com aviso de irreversibilidade

### Comportamento esperado
- A tela de remotos é a primeira tela exibida ao abrir a aplicação pela primeira vez (se nenhum remoto configurado)
- O wizard usa `QStackedWidget` com navegação "Voltar" / "Próximo" — o usuário pode voltar e alterar escolhas
- Campos de senha/token são mascarados com bullet points e possuem toggle de visibilidade (ícone de olho)
- Lista de backends inclui barra de busca no topo e scroll com categorias visuais (Cloud Storage, File Transfer, Object Storage)

### Estados da UI
- **Estado vazio (sem remotos configurados):** mensagem central "Nenhum remoto configurado" + botão "Adicionar Remoto" em destaque + link "O que é um remoto?" explicando o conceito
- **Estado de carregamento (consultando quota):** skeleton/spinner em cada card de remoto enquanto `rclone about` não retorna
- **Estado de erro (rclone não encontrado):** banner no topo da tela: "rclone não encontrado no PATH. Instale o rclone para continuar." com link para https://rclone.org/install/
- **Estado de erro (rclone.conf corrompido):** mensagem "Não foi possível ler o arquivo de configuração. Deseja restaurar o backup ou criar um novo?"
- **Estado de erro (backend offline):** badge "Offline" no card do remoto com tooltip explicando o erro de conexão
- **Estado de sucesso (remoto salvo):** notificação toast "Remoto 'Meu Google Drive' configurado com sucesso" + card aparece na lista com animação sutil

---

## 9. Modelo de Dados

### Entidades (em memória, não persistidas — os dados vivem no `rclone.conf`)

```
RemoteConfig {
  name: str              // Nome do remoto (ex: "gdrive")
  type: str              // Tipo de backend (ex: "drive")
  parameters: dict       // {key: value, ...} — parâmetros de configuração
  is_encrypted: bool     // Se a config está criptografada no rclone.conf
}

BackendMeta {
  type: str              // Identificador (ex: "drive", "s3")
  display_name: str      // Nome legível (ex: "Google Drive", "Amazon S3")
  description: str       // Descrição curta em PT-BR
  category: str          // Categoria: "cloud", "file_transfer", "object_storage", "crypt", "utility"
  requires_oauth: bool   // Se requer OAuth
  oauth_provider: str?   // Nome do provider p/ authorize (ex: "drive")
  fields: [BackendField] // Campos de configuração
}

BackendField {
  name: str              // Nome do parâmetro (ex: "client_id")
  label: str             // Label em PT-BR
  description: str       // Help text
  required: bool
  advanced: bool         // Se deve ficar colapsado por padrão
  type: FieldType        // string, int, bool, choice, password, filepath
  choices: [str]?        // Se type=choice, lista de valores possíveis
  default: str?          // Valor padrão
  placeholder: str?      // Placeholder no campo
}

RemoteStatus {
  name: str
  online: bool
  quota_used: int?       // Bytes usados (None se não disponível)
  quota_free: int?       // Bytes livres
  quota_total: int?      // Total
  error_message: str?    // Mensagem de erro se offline
}
```

### Migrações necessárias
Não se aplica — os dados vivem no `rclone.conf`, que é gerenciado pelo próprio rclone.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| `rclone` binário no PATH (≥ v1.60) | Obrigatória | A feature inteira fica indisponível. Exibir tela de erro com instruções de instalação |
| `rclone config` (create/update/delete/show) | Obrigatória | Impossível gerenciar remotos. Exibir erro específico com output do comando |
| `rclone authorize` | Obrigatória (para backends OAuth) | Backends OAuth não podem ser configurados. Exibir opção de config manual com instruções |
| `rclone listremotes` | Obrigatória | Lista de remotos vazia. Pode ser cacheada localmente |
| `rclone about` | Opcional | Sem quota exibida — exibir "Quota não disponível" no card do remoto |
| Browser padrão do sistema (`xdg-open`) | Obrigatória (para OAuth) | Fallback: exibir URL para copiar manualmente |
| `rclone.conf` padrão (`~/.config/rclone/rclone.conf`) | Obrigatória | Sem arquivo de config, wizard inicia do zero com opção de criar novo arquivo |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-S01-01: rclone.conf não existe | Primeiro uso, arquivo nunca foi criado | Wizard cria novo `rclone.conf` ao salvar o primeiro remoto, sem erro |
| EC-S01-02: rclone.conf com sintaxe inválida | Arquivo corrompido manualmente | Exibir erro "Arquivo de configuração corrompido na linha X. Deseja restaurar backup ou editar manualmente?" |
| EC-S01-03: Nome de remoto inválido | Nome começa com `-`, contém `/`, etc. | Validação client-side bloqueia submit com mensagem: "Nome inválido. Use apenas letras, números, _, -, ., +, @ e espaço." |
| EC-S01-04: Timeout no `rclone authorize` | Browser não abriu, conexão lenta | Após 120s, exibir "O processo de autorização excedeu o tempo limite. Verifique se o browser abriu e tente novamente." |
| EC-S01-05: Token OAuth inválido ou expirado | Token colado manualmente com erro | `rclone config create` falha — exibir erro retornado pelo rclone e permitir tentar novamente |
| EC-S01-06: Backend exige parâmetros obrigatórios não preenchidos | Usuário tenta salvar sem preencher campos required | Validação client-side marca campos em vermelho e exibe tooltip "Campo obrigatório". Submit bloqueado |
| EC-S01-07: Edição de remoto com campos sensíveis | Usuário edita remoto com token OAuth ou senha | Campos são mascarados com "••••••••" (8 bullets fixos, sem revelar tamanho). Valor original só é preservado se o campo não for alterado |
| EC-S01-08: Exclusão de remoto com mounts ativos | Usuário tenta excluir remoto que está montado | Diálogo alerta: "O remoto 'gdrive' está atualmente montado em /mnt/gdrive. A exclusão não desmonta automaticamente. Desmontar e excluir?" |
| EC-S01-09: Conflito de nome de remoto | Usuário tenta criar remoto com nome de um já existente | Validação client-side: erro inline "Já existe um remoto com este nome" antes do submit |
| EC-S01-10: `rclone config` falha sem mensagem clara | Erro interno do rclone ou backend | Exibir output bruto do comando em área expansível "Detalhes do erro" + sugestão de verificar documentação do backend |

---

## 12. Segurança e Privacidade

- **Autenticação:** Não se aplica — a GUI não tem sistema de login próprio.
- **Autorização:** Backends OAuth delegam ao `rclone authorize`, que armazena tokens no `rclone.conf`. A GUI nunca persiste tokens ou senhas em seu próprio banco.
- **Dados sensíveis:** Os campos de tipo "password" e "token" no formulário usam `QLineEdit.EchoMode.Password`, com toggle de visibilidade. Valores nunca são logados. No SQLite, apenas referências ao nome do remoto são armazenadas, nunca parâmetros de configuração.
- **Auditoria:** Log de operações de config (create/update/delete) com timestamp e nome do remoto é mantido em arquivo de log local e rotate (ver Spec 07).

---

## 13. Plano de Rollout

- **Estratégia:** Big bang — é a primeira feature a ser implementada, sem a qual a aplicação não funciona.
- **Como reverter (rollback):** O backup automático do `rclone.conf` antes de cada escrita garante que qualquer operação possa ser desfeita manualmente.
- **Monitoramento pós-deploy:** Verificar taxa de sucesso na criação de remotos (jobs bem-sucedidos vs. falhas de `rclone config create`). Reportar erros por tipo de backend para identificar backends problemáticos.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-S01-01 | Como obter a lista de campos por tipo de backend? O rclone expõe isso via RC API (`config/providers`)? Ou precisamos manter catálogo manual? | Alto — determina esforço de manutenção | Emerson | Antes da implementação |
| OQ-S01-02 | O `rclone config create` aceita todos os parâmetros via CLI como `--key=value`? Ou alguns fluxos exigem stdin interativo? | Alto — impacto direto na implementação | Emerson | Antes da implementação |
| OQ-S01-03 | Como lidar com backends que exigem configuração de criptografia aninhada (ex: `crypt` sobre `drive`)? | Médio — caso de uso comum | Emerson | Especificar antes da implementação |
| OQ-S01-04 | A lista de backends e seus campos deve ser hardcoded no código ou carregada dinamicamente de um arquivo de metadados (JSON/YAML)? | Médio — manutenibilidade | Emerson | Decidir na spec de arquitetura |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| Delegar OAuth ao `rclone authorize` em vez de implementar fluxo OAuth próprio | (1) OAuth próprio com biblioteca Python, (2) WebView embutido | (1) Exigiria gerenciar client_id/client_secret por backend — inviável para ~50 backends. (2) WebView é complexo em Linux (depende de Qt WebEngine, que é pesado). `rclone authorize` é testado, mantido pelo time do rclone e funciona com todos os backends |
| Manter metadados de backends em catálogo estático (JSON no código) em vez de extrair do rclone em runtime | (1) RC API `config/providers`, (2) Shell completion scripts | `config/providers` não existe em todas as versões e pode não incluir descrições/help text. Catálogo estático garante consistência da UI, pode ter labels em PT-BR, e é atualizado junto com novos releases do rclone. Ainda vamos verificar `config/providers` (OQ-S01-01) para possível geração automática |
| Usar `rclone config` como CLI (subprocess) em vez de manipular `rclone.conf` diretamente | (1) Escrever no arquivo INI manualmente, (2) RC API `config/*` | Manipular o arquivo diretamente é frágil — mudanças de formato podem corromper. RC API `config/*` existe mas a CLI é mais estável e bem documentada. Subprocess é seguro se usarmos backup antes de cada escrita |
| Formulário dinâmico por backend via template JSON, não código hardcoded | (1) QT Designer `.ui` por backend (~50 arquivos), (2) Código Python por backend | ~50 arquivos `.ui` seria pesado e difícil de manter. Código Python por backend seria verboso e duplicaria lógica. Um único motor de formulário dinâmico que lê JSON de metadados é mais enxuto e permite atualizar campos sem recompilar |

---

## Apêndice

### Referências
- [rclone config docs](https://rclone.org/docs/#configure)
- [rclone authorize docs](https://rclone.org/commands/rclone_authorize/)
- [rclone config create docs](https://rclone.org/commands/rclone_config_create/)
- [rclone about docs](https://rclone.org/commands/rclone_about/)
- [rclone RC API docs](https://rclone.org/rc/)
- PRD.md — Seção 3.1, RF-01, RF-02

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-07-04 | Emerson | Criação inicial |

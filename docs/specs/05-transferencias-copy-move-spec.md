# Spec: Transferências Pontuais (Copy/Move One-Shot)

**Versão:** 1.0
**Status:** Rascunho
**Autor:** Emerson
**Data:** 2026-07-04
**Reviewers:** N/A

---

## 1. Resumo

Interface para transferências rápidas de arquivos/pastas entre dois paths (local ou remoto) sem a necessidade de criar um job persistente. Atende ao caso de uso "copiar isso aqui para lá agora" com barra de progresso e opção de salvar a operação como job recorrente após a conclusão. Reutiliza o explorador two-panel (Spec 02) para seleção de paths e a infraestrutura de progresso (Spec 03) para monitoramento.

---

## 2. Contexto e Motivação

**Problema:**
Criar um job formal para uma transferência única (ex: "mover esta pasta de fotos do Drive para o Dropbox uma única vez") é burocrático demais. O usuário quer selecionar origem e destino, clicar "Copiar" e ver o progresso — sem preencher nome, flags, agendamento.

**Evidências:**
- Ferramentas como FileZilla e Cyberduck baseiam-se inteiramente nesse modelo de transferência ad-hoc
- O explorador two-panel (Spec 02) naturalmente sugere a ação "copiar do painel esquerdo para o direito"
- Jobs (Spec 03) resolvem automação, mas são overkill para operações pontuais

**Por que agora:**
Transferências pontuais são o terceiro pilar de uso do rclone (junto com sync agendado e montagem VFS). É uma das primeiras ações que um novo usuário tenta após configurar remotos e explorar arquivos.

---

## 3. Goals (Objetivos)

- [ ] G-01: Permitir copiar ou mover arquivos/pastas entre dois paths (local ou remoto) com diálogo de confirmação e barra de progresso
- [ ] G-02: Exibir preview do que será transferido (lista de arquivos + tamanho total) antes de confirmar
- [ ] G-03: Oferecer opção de salvar a transferência como job recorrente após conclusão bem-sucedida

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| Tempo para iniciar uma transferência | ~2 min (CLI: digitar path, flags, confirmar) | < 15s | Lançamento |
| Conversão de transferência → job | 0 (não existe) | ≥ 30% das transferências concluídas geram jobs | 3 meses |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: Transferências agendadas ou recorrentes — isso é o escopo da Spec 03 (Jobs)
- NG-02: Fila de transferências em background — MVP suporta uma transferência por vez; múltiplas transferências são enfileiradas sequencialmente
- NG-03: Transferências via drag-and-drop a partir do gerenciador de arquivos nativo — fase 2
- NG-04: `rclone copyurl` — fase 2

---

## 5. Usuários e Personas

**Usuário primário:** Ana — está organizando arquivos entre nuvens e quer copiar a pasta "Férias 2025" do Drive para o Dropbox, só desta vez. Não quer aprender sobre jobs.

**Usuário secundário:** Bruno — quer mover rapidamente um dump de banco de dados do servidor para S3, com dry-run primeiro para confirmar os arquivos. Pode salvar como job se a operação for bem-sucedida.

**Jornada atual (sem a feature):**
1. Abre terminal, digita `rclone copy gdrive:"Férias 2025" dropbox:"Férias 2025" --progress`
2. Sem dry-run prévio, torce para não sobrescrever nada errado
3. Se quiser repetir depois: precisa lembrar o comando ou criar script

**Jornada futura (com a feature):**
1. No explorador two-panel, seleciona "Férias 2025" no Drive (painel esquerdo)
2. Seleciona Dropbox (painel direito), clica "Copiar →" (ou F5)
3. Diálogo "Transferência Rápida" mostra: 45 arquivos, 2.3 GB
4. Opções: dry-run (recomendado para primeira vez), checksum, mover ao invés de copiar
5. Confirma — barra de progresso aparece
6. Concluído: toast "45 arquivos copiados com sucesso!" + botão "Salvar como Job Recorrente"

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-S05-01 | O sistema deve iniciar transferência a partir do explorador two-panel: selecionar itens no painel ativo e executar Copy (F5) ou Move (F6) para o path do outro painel | Must | Ao pressionar F5, diálogo de transferência abre com origem (path do painel ativo + itens selecionados) e destino (path do outro painel) pré-preenchidos |
| RF-S05-02 | O sistema deve exibir diálogo de configuração da transferência com: preview (lista de arquivos + tamanho total), flags básicas (checksum, dry-run, mover vs. copiar), e botão confirmar | Must | Preview é obtido via dry-run rápido do rclone ou parsing do `rclone lsf --recursive`; tamanho total obtido via `rclone size` |
| RF-S05-03 | O sistema deve executar transferência via `rclone copy` (ou `rclone move`) e exibir progresso em tempo real reutilizando o componente de progresso da Spec 03 | Must | Subprocess com `--progress -P` ou RC API polling; mesma UI de progresso dos jobs: velocidade, ETA, arquivos processados, erros |
| RF-S05-04 | O sistema deve permitir cancelar transferência em andamento | Must | Botão "Cancelar" interrompe o subprocess; arquivos já transferidos permanecem no destino (comportamento padrão do rclone) |
| RF-S05-05 | O sistema deve oferecer, após conclusão bem-sucedida, a opção "Salvar como Job Recorrente" que redireciona para o formulário de criação de job (Spec 03) pré-preenchido | Could | Botão no toast de sucesso; ao clicar, abre JobEditorDialog com origem, destino e flags já preenchidos |
| RF-S05-06 | O sistema deve suportar copy com `--create-empty-src-dirs` (checkbox "Criar diretórios vazios na origem") quando relevante | Should | Flag disponível no diálogo de transferência, desabilitada por padrão |
| RF-S05-07 | O sistema deve validar que a operação não é destrutiva sem confirmação: `move` deleta origem — exige confirmação explícita; `copy` para destino que já contém os arquivos alerta sobre possível sobrescrita | Must | Para `move`: diálogo "Mover arquivos deletará a origem após a cópia. Continuar?"; Para `copy` com destino populado: "O destino já contém alguns dos arquivos selecionados. Arquivos existentes serão sobrescritos se diferentes." (baseado em dry-run) |

### 6.2 Fluxo Principal (Happy Path)

1. No explorador two-panel, usuário seleciona 3 arquivos no painel esquerdo (local)
2. Painel direito mostra `gdrive:Backup` (destino)
3. Usuário pressiona F5 (Copiar)
4. Diálogo abre: "Copiar 3 arquivos (145 MB) de /home/user/docs para gdrive:Backup"
5. Lista de arquivos com checkboxes (todos marcados por padrão)
6. Checkbox "Verificar integridade após cópia (--checksum)" — usuário ativa
7. Clica "Copiar"
8. Progresso: "Enviando... 12 MB/s ↑ · 2/3 arquivos · ETA 11s"
9. Concluído: toast com botão "Salvar como Job"

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Mover ao invés de copiar (F6):**
1. Mesmo fluxo, mas com F6 (Mover)
2. Diálogo exibe aviso em destaque (fundo amarelo): "Os arquivos serão removidos da origem após a transferência."
3. Checkbox extra: "Mover apenas se a cópia for bem-sucedida (--delete-after)" — ativado por padrão para segurança

**Fluxo Alternativo B — Transferência entre painéis com paths não definidos:**
1. Usuário seleciona "gdrive:Projetos" no painel esquerdo
2. Painel direito está vazio (sem remoto selecionado)
3. Pressiona F5 — sistema solicita "Selecione o destino primeiro" com destaque no seletor de remoto do painel direito

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-S05-01 | Preview de arquivos (dry-run) | < 10s para diretórios com até 1000 arquivos | Executar `rclone lsjson --recursive` ou `rclone size` com timeout de 15s; se exceder, exibir contagem sem preview detalhado |
| RNF-S05-02 | Execução assíncrona | UI permanece responsiva durante transferências longas | QProcess com signals; mesmo padrão da Spec 03 |
| RNF-S05-03 | Operações atômicas | Uma transferência por vez (sequencial). Tentar iniciar segunda transf. enquanto uma está em andamento mostra: "Já existe uma transferência em andamento. Aguardar ou cancelar?" | Previne conflitos de subprocess rclone simultâneos na mesma UI |

---

## 8. Design e Interface

### Componentes afetados
- **TransferDialog (QDialog):** preview, flags, confirmação
- **TransferProgressWidget:** reutilizado da Spec 03 (componente compartilhado)
- **TwoPanelBrowser:** botões "Copiar →" / "← Copiar" / "Mover →" na barra entre painéis; atalhos de teclado globais

### Estados da UI
- **Estado de carregamento (preview):** spinner + "Calculando tamanho..."
- **Estado de execução:** barra de progresso com estatísticas
- **Estado de sucesso:** toast com resumo + botão "Salvar como Job"
- **Estado de erro:** diálogo com erro detalhado + botão "Tentar Novamente" + "Salvar Configuração como Job"

---

## 9. Modelo de Dados

Não há novas entidades persistentes. Transferências one-shot não são armazenadas — se o usuário quiser persistência, salva como Job (Spec 03). O histórico pode opcionalmente registrar transferências one-shot na tabela `job_history` com `job_id=NULL` para auditoria.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| Explorador de Arquivos (Spec 02) | Obrigatória | Sem explorador, não há seleção visual de paths — fallback para input de texto manual |
| Jobs de Sync (Spec 03) — componente de progresso | Obrigatória | Reutiliza o mesmo QProcess wrapper e progress widget |
| `rclone copy` / `rclone move` | Obrigatória | Transferência indisponível |
| `rclone size` / `rclone lsjson` (preview) | Opcional | Preview de tamanho/arquivos não disponível; transferência pode prosseguir sem preview (apenas paths) |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-S05-01: Destino sem espaço suficiente | Backend retorna "quota exceeded" | Transferência falha com erro claro: "Espaço insuficiente em [destino]. Necessário: 2.3 GB, Disponível: 1.1 GB" |
| EC-S05-02: Alguns arquivos falham, outros sucedem | Erro em subconjunto de arquivos | rclone continua processando arquivos restantes; resumo final: "12/15 arquivos transferidos. 3 falhas." com lista dos que falharam |
| EC-S05-03: Origem e destino são o mesmo path | Usuário seleciona mesmo path nos dois painéis | Bloquear transferência com aviso "Origem e destino são idênticos" |
| EC-S05-04: Transferência de pasta para arquivo (ou vice-versa) | Origem é pasta, destino é arquivo | rclone reporta erro; repassar mensagem: "Não é possível copiar uma pasta para um arquivo" |
| EC-S05-05: Conexão perdida durante transferência | Rede cai | rclone tenta reconectar conforme `--retries`; se falha definitiva, transferência marcada como falha com log de erros |

---

## 12. Segurança e Privacidade

- Mesmo modelo da Spec 03: operações usam credenciais do `rclone.conf`, sem elevação de privilégios.
- Para `move` (deleta origem), confirmação explícita é obrigatória e irreversível.

---

## 13. Plano de Rollout

- **Estratégia:** Feature disponível assim que Spec 02 (Explorador) estiver funcional. Não depende de scheduler ou daemon.
- **Como reverter (rollback):** Desabilitar atalhos F5/F6 e botões "Copiar"/"Mover" — navegação no explorador continua funcionando.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-S05-01 | Devemos permitir múltiplas transferências simultâneas? Se sim, como lidar com recursos compartilhados (banda, conexões)? | Baixo — pode ser postergado | Emerson | v2.0 |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| Transferências one-shot não são persistidas automaticamente | (1) Salvar como job implícito, (2) Sempre salvar no histórico | One-shot é intencionalmente efêmero. Persistir como job implícito geraria poluição na lista de jobs. Oferecer "Salvar como Job" após conclusão é o melhor dos dois mundos |
| Usar `rclone copy`/`rclone move` em vez de `rclone sync` | (1) `rclone sync` para ter diff completo | `sync` deleta arquivos no destino que não existem na origem — comportamento perigoso para transferência pontual. `copy`/`move` são mais seguros como padrão |
| Reutilizar componente de progresso da Spec 03 | (1) Componente separado, (2) Código duplicado | Compartilhar QProcess wrapper e progress widget reduz duplicação e garante consistência de comportamento entre jobs e transferências |

---

## Apêndice

### Referências
- [rclone copy docs](https://rclone.org/commands/rclone_copy/)
- [rclone move docs](https://rclone.org/commands/rclone_move/)
- [rclone copyto docs](https://rclone.org/commands/rclone_copyto/)
- PRD.md — Seção 3.1, RF-09

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-07-04 | Emerson | Criação inicial |

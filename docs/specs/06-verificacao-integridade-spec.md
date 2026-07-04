# Spec: Verificação e Integridade

**Versão:** 1.2
**Status:** Implementado
**Autor:** Emerson
**Data:** 2026-07-04
**Reviewers:** N/A

---

## 1. Resumo

Utilitários de verificação de integridade de arquivos entre dois paths (local/remoto), permitindo checar se origem e destino são idênticos via `rclone check` (comparação de tamanho/modtime ou checksum), gerar hashes de arquivos (`md5sum`, `sha1sum`, `hashsum`), e verificar integridade de remotos criptografados (`cryptcheck`). Foco em validação pós-sync e auditoria de consistência.

---

## 2. Contexto e Motivação

**Problema:**
Após sincronizações, especialmente de grandes volumes, usuários precisam confirmar que a transferência foi íntegra — nenhum arquivo corrompido, nenhum arquivo ausente, nenhum arquivo com tamanho diferente. O `rclone check` resolve isso, mas via CLI exige digitar paths completos e interpretar output textual de diferenças.

**Evidências:**
- `rclone check` é a ferramenta recomendada na documentação para validar syncs
- Em ambientes corporativos, auditoria de integridade é requisito de compliance
- Hashes (MD5, SHA1) são úteis para verificação manual e comparação com fontes externas

**Por que agora:**
Verificação é o passo final do ciclo de confiança: configurar remoto → explorar → transferir/sincronizar → **verificar**. Sem verificação, o usuário nunca tem certeza de que seus dados estão seguros.

---

## 3. Goals (Objetivos)

- [ ] G-01: Verificar se dois paths são idênticos via `rclone check` e exibir relatório de diferenças
- [ ] G-02: Gerar hashes (MD5, SHA1, ou hash nativo do backend) para arquivos em um path
- [ ] G-03: Exibir relatórios exportáveis (CSV) das diferenças encontradas
- [ ] G-04: Suportar verificação por checksum (não apenas tamanho/modtime) para máxima confiabilidade

**Métricas de sucesso:**
| Métrica | Baseline atual | Target | Prazo |
|---------|---------------|--------|-------|
| Tempo para verificar integridade de 10.000 arquivos | ~5 min CLI | < 5 min GUI (com progresso visível) | Lançamento |
| Uso de checksum (vs. size-only) | ~50% | ≥ 80% (via destaque visual da opção) | Lançamento |

---

## 4. Non-Goals (Fora do Escopo)

- NG-01: `cryptcheck` com UI dedicada — MVP apenas suporta o comando com input manual de paths; UI específica para criptografia é fase 2
- NG-02: `dedupe` (deduplicação) — fase 2
- NG-03: Agendamento de verificações automáticas — fase 2
- NG-04: Comparação visual de conteúdo de arquivos (tipo diff binário) — fase 3

---

## 5. Usuários e Personas

**Usuário primário:** Bruno — após sync de backup semanal, roda `rclone check` para garantir que 50.000 arquivos de banco de dados estão íntegros no S3. Precisa de relatório exportável para auditoria.

**Usuário secundário:** Ana — quer verificar se a migração de 500 fotos do Google Drive para o Dropbox foi completa, sem perder nenhuma imagem.

**Jornada atual (sem a feature):**
1. Bruno: `rclone check /data/backups s3:backups --checksum --one-way 2>&1 | tee check-report.log`
2. Lê output linha por linha procurando por "differences found"
3. Para hash: `rclone md5sum s3:backups > hashes.md5`
4. Para exportar: faz grep manual no output

**Jornada futura (com a feature):**
1. Abre a GUI, navega para "Verificação" (atalho na barra lateral ou aba)
2. Seleciona origem (`/data/backups`) e destino (`s3:backups`)
3. Ativa "Usar checksum (mais preciso, mais lento)" — recomendado
4. Clica "Verificar" — progresso: "Verificando... 12.450/50.000 arquivos · 3 diferenças encontradas"
5. Relatório interativo: "3 diferenças" expansível — 2 arquivos ausentes no destino, 1 com tamanho divergente
6. Exporta como CSV para compliance

---

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-S06-01 | O sistema deve executar `rclone check` entre dois paths e exibir relatório de diferenças categorizado (ausentes na origem, ausentes no destino, tamanho divergente, checksum divergente, data divergente) | Must | Formulário com origem, destino e flags (checksum, one-way, size-only, download); progresso durante verificação; relatório final com grupos expansíveis |
| RF-S06-02 | O sistema deve gerar lista de hashes via `rclone md5sum`, `sha1sum` ou `hashsum` (seletor de algoritmo) para arquivos em um path, com opção de salvar arquivo | Should | Input: path + algoritmo; output: lista exibida em tabela (arquivo, hash) com botão "Exportar" (txt/csv); progresso durante geração |
| RF-S06-03 | O sistema deve exibir progresso durante verificação (arquivos verificados/total, velocidade, diferenças encontradas) | Must | Polling de stdout (`--progress`) do `rclone check`; atualização a cada 1s |
| RF-S06-04 | O sistema deve permitir exportar relatório de diferenças em CSV com colunas: path, tipo de diferença (missing_src/missing_dst/size/mtime/checksum), tamanho origem, tamanho destino | Should | Botão "Exportar CSV" no relatório final; arquivo salvo com diálogo nativo |
| RF-S06-05 | O sistema deve exibir informação de espaço (`rclone about`) para os paths verificados (quando disponível) | Could | Painel lateral ou barra de status mostrando uso de cada lado: "Origem: 234 GB · Destino: 233.8 GB · Diferença: 0.2 GB" |
| RF-S06-06 | O sistema deve suportar verificação one-way (`--one-way`): apenas checa se arquivos da origem existem no destino (ignora extras no destino) | Must | Checkbox "One-way (apenas verificar se origem está no destino)" no formulário de check |
| RF-S06-07 | O sistema deve permitir cancelar verificação em andamento | Must | Botão "Cancelar" durante execução; resultados parciais são exibidos |
| RF-S06-08 | O sistema deve integrar com jobs: após execução de um job de sync, oferecer opção "Verificar integridade" como passo seguinte | Should | No toast de conclusão do job, botão "Verificar Integridade" que abre a ferramenta de check com paths pré-preenchidos do job |

### 6.2 Fluxo Principal (Happy Path) — Verificar Sincronização

1. O usuário abre "Verificação" no menu lateral
2. Seleciona origem: `/home/user/docs` e destino: `gdrive:Backup/docs`
3. Marca checkbox "Usar checksum" e "One-way"
4. Clica "Verificar"
5. Barra de progresso: "Verificando... 234/500 arquivos · 0 diferenças encontradas · 45s decorridos"
6. Conclusão: relatório "500 arquivos verificados · 0 diferenças · Origem e destino são idênticos" com ícone verde de check
7. Opção de exportar relatório (mesmo sem diferenças, para registro)

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Gerar Hashes:**
1. Na aba "Hashes", usuário seleciona `gdrive:Projetos` e algoritmo "SHA1"
2. Clica "Gerar Hashes"
3. Progresso: "Calculando... 67/230 arquivos"
4. Tabela preenchida: arquivo, SHA1; botão "Exportar" salva `hashes.sha1`

**Fluxo Alternativo B — Verificação com Diferenças:**
1. Check entre `/local` e `gdrive:Backup` com checksum
2. Resultado: "3 diferenças encontradas"
3. Grupo "Ausentes no destino (2)": lista expandida com paths
4. Grupo "Checksum divergente (1)": `foto.jpg` — origem MD5: abc123, destino MD5: def456
5. Sugestão: "Re-sincronizar estes arquivos?" com botão que abre transferência pontual (Spec 05)

---

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|----|-----------|-----------|------------|
| RNF-S06-01 | Verificação de 10.000 arquivos (checksum) | < 10 min (assumindo backend com latência média) | Depende do backend; a UI não adiciona overhead significativo |
| RNF-S06-02 | Relatório de diferenças renderizado | < 2s para 10.000 diferenças (virtualização de lista) | QTableView com modelo virtual para evitar alocação de widgets |
| RNF-S06-03 | Arquivo CSV exportado | < 5s para 10.000 linhas | Escrita síncrona em QThread separada se necessário |

---

## 8. Design e Interface

### Componentes afetados
- **CheckToolWidget (QWidget):** formulário de verificação + relatório de diferenças
- **HashToolWidget (QWidget):** formulário de geração de hashes + tabela de resultados
- **DiffReportWidget (QWidget):** relatório categorizado com grupos expansíveis
- Botão "Verificação" na sidebar ou aba de navegação principal

### Estados da UI
- **Estado inicial:** formulário com origem, destino e flags
- **Estado de execução (verificando):** barra de progresso, estatísticas em tempo real, botão cancelar
- **Estado de sucesso (sem diferenças):** banner verde "Origem e destino são idênticos" + resumo
- **Estado de sucesso (com diferenças):** banner amarelo "N diferenças encontradas" + relatório agrupado
- **Estado de erro:** mensagem de erro com detalhes do rclone

---

## 9. Modelo de Dados

Não há persistência dedicada. Relatórios de verificação podem ser salvos como arquivos CSV pelo usuário (não no banco). Opcionalmente, associar uma verificação a uma execução de job (`job_history`) com flag `has_check_result` e path para o CSV exportado.

---

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|-------------|------|------------------------|
| `rclone check` | Obrigatória | Verificação entre paths indisponível |
| `rclone md5sum` / `sha1sum` / `hashsum` | Opcional | Geração de hashes indisponível |
| Explorador de Arquivos (Spec 02) — seleção de paths | Opcional | Paths precisam ser digitados manualmente |
| Jobs de Sync (Spec 03) — integração pós-job | Opcional | Sem botão "Verificar Integridade" no toast de job |
| `rclone about` | Opcional | Sem informação de espaço usado |

---

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---------|---------|----------------------|
| EC-S06-01: Backend não suporta checksum | `rclone check --checksum` falha com "hash not supported" | Exibir aviso antes de iniciar: "Este backend não suporta verificação por checksum. Usar comparação por tamanho e data?" |
| EC-S06-02: Arquivos com data de modificação idêntica mas conteúdo diferente | Sync sem `--checksum` pode resultar em arquivos corrompidos não detectados por size/modtime | Destaque visual na UI recomendando checksum: "A verificação por tamanho+data é rápida mas pode não detectar corrupção silenciosa. Recomendamos usar checksum." |
| EC-S06-03: Path com 0 arquivos | Ambos os lados vazios | Relatório: "0 arquivos verificados. Ambos os paths estão vazios." |
| EC-S06-04: Origem não encontrada | Path inválido ou remoto offline | Erro antes de iniciar: "Origem não encontrada ou offline" |

---

## 12. Segurança e Privacidade

- Hashes de arquivos podem revelar conteúdo de arquivos conhecidos (ataque de dicionário de hash). Relatórios exportados contêm paths e hashes — advertir usuário no momento da exportação.
- Mesmo modelo de credenciais das demais specs (usa `rclone.conf`, sem armazenamento próprio).

---

## 13. Plano de Rollout

- **Estratégia:** Feature independente — pode ser liberada assim que Spec 01 (Remotos) estiver pronta. Botão na sidebar.
- **Como reverter (rollback):** Esconder aba/botão "Verificação". Nenhum dado é perdido.

---

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---------|---------|------|-------|
| OQ-S06-01 | O `rclone check` suporta `--progress` para feedback em tempo real? Se não, como obter progresso granular? | Alto — UX de progresso | Emerson | Validar antes da implementação |
| OQ-S06-02 | Para `cryptcheck`, é necessário que ambos os paths sejam remotos criptografados? Ou funciona com um path criptografado e um plain? | Médio — escopo da feature | Emerson | Documentar antes da implementação |

---

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---------|--------------------------|---------|
| Checksum como opção destacada (não padrão) em vez de forçado | (1) Sempre usar checksum, (2) Nunca oferecer | Checksum é mais lento e alguns backends não suportam. Destacar a opção educa o usuário sobre sua importância sem forçar. UX: checkbox "Usar checksum (recomendado)" com tooltip explicativo |
| Relatório interativo (expansível na UI) em vez de apenas CSV | (1) Apenas CSV exportado, (2) Apenas tabela na UI | Relatório interativo permite análise rápida; CSV cobre casos de compliance e compartilhamento. Ambos são oferecidos |
| `--one-way` como opção no formulário em vez de modo separado | (1) Ferramenta separada "Verificação One-Way" | É apenas uma flag do `rclone check` — checkbox é suficiente e mantém a ferramenta unificada |

---

## Apêndice

### Referências
- [rclone check docs](https://rclone.org/commands/rclone_check/)
- [rclone cryptcheck docs](https://rclone.org/commands/rclone_cryptcheck/)
- [rclone md5sum docs](https://rclone.org/commands/rclone_md5sum/)
- [rclone sha1sum docs](https://rclone.org/commands/rclone_sha1sum/)
- [rclone hashsum docs](https://rclone.org/commands/rclone_hashsum/)
- PRD.md — Seção 3.1, RF-10

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-07-04 | Emerson | Criação inicial |
| 1.1 | 2026-07-04 | Emerson | Implementação completa: check tool com origem/destino, checksum toggle, export CSV |
| 1.2 | 2026-07-04 | Emerson | Fix: validação 36/36 confirma check tool UI fields presentes |

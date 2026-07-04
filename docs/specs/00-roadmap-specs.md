# Roadmap de Specs — Rclone GUI

> Ordem de implementação SDD para as specs do projeto.
> Cada spec segue o template RFC Pragmático (sdd-spec) e referencia o PRD como fonte de requisitos.

---

## Ordem de Implementação

As specs estão ordenadas por dependência técnica e prioridade de produto. A ordem sugerida de implementação é:

| # | Spec | Depende de | Comandos rclone cobertos | Por que esta ordem |
|---|------|-----------|-------------------------|-------------------|
| 01 | **Gerenciamento de Remotos** | Nenhuma | `config create/update/delete/show`, `listremotes`, `authorize`, `about` | Fundação — sem remotos configurados, nada mais funciona. É a primeira feature que o usuário vê |
| 02 | **Explorador de Arquivos** | Spec 01 | `lsf`, `lsd`, `lsjson`, `tree`, `cat`, `mkdir`, `rmdir`, `delete`, `deletefile`, `link`, `size`, `about` | Segunda fundação — explorar arquivos é pré-requisito para selecionar paths em jobs e transferências |
| 03 | **Jobs de Sync** | Spec 01, 02 | `sync`, `bisync`, `copy`, `move`, `--backup-dir`, `--bwlimit`, `--dry-run`, `--filter`, `--metadata`, `--checksum` | Core do produto — syncs agendados são o principal valor entregue. Depende de remotos configurados e seleção de paths |
| 04 | **Montagem VFS** | Spec 01 | `mount`, `cmount`, `--vfs-cache-mode`, `--vfs-cache-max-age`, `--vfs-cache-max-size` | Feature diferenciadora estilo Google Drive — montagem de remotos como drives locais. Pode ser implementada em paralelo com a Spec 03 |
| 05 | **Transferências Copy/Move** | Spec 01, 02 | `copy`, `copyto`, `move`, `moveto`, `copyurl` | Conveniência — operações pontuais sem criar job. Reutiliza o explorador de arquivos da Spec 02 |
| 06 | **Verificação e Integridade** | Spec 01, 02 | `check`, `cryptcheck`, `md5sum`, `sha1sum`, `hashsum`, `size`, `about` | Utilitário — verificar se syncs estão corretos. Menor prioridade que transfers e jobs |
| 07 | **Daemon, Tray e Autostart** | Spec 03, 04 | `rcd`, `rc core/*`, `rc job/*`, `rc vfs/*` | Integração final — o daemon unifica scheduler, tray, mounts e notificações. Deve ser construído por último, pois orquestra as specs anteriores |

## Diagrama de Dependências

```
Spec 01 (Remotos) ──┬── Spec 02 (Explorador) ──┬── Spec 03 (Jobs Sync)
                    │                          ├── Spec 05 (Transferências)
                    │                          └── Spec 06 (Verificação)
                    └── Spec 04 (Montagem VFS) ──┬── Spec 07 (Daemon/Tray/Autostart)
                                                  │
                           Spec 03 (Jobs Sync) ───┘
```

## Convenções das Specs

Cada spec segue o template `sdd-spec` com as 15 seções:
1. Resumo
2. Contexto e Motivação
3. Goals (Objetivos)
4. Non-Goals (Fora do Escopo)
5. Usuários e Personas
6. Requisitos Funcionais (com ID, Prioridade, Critério de Aceite)
7. Requisitos Não-Funcionais
8. Design e Interface (comportamento, estados da UI)
9. Modelo de Dados
10. Integrações e Dependências
11. Edge Cases e Tratamento de Erros
12. Segurança e Privacidade
13. Plano de Rollout
14. Open Questions
15. Decisões Tomadas (Decision Log)

### Convenções de IDs
- **RF-XX:** Requisito Funcional (global, referenciado do PRD)
- **RF-S{NN}-XX:** Requisito Funcional específico da Spec NN (ex: RF-S01-01 é o primeiro RF da Spec 01)
- **RNF-XX:** Requisito Não-Funcional (global)
- **EC-XX:** Edge Case
- **OQ-XX:** Open Question

### Escala de Prioridade
| Nível | Significado |
|-------|------------|
| **Must** | Obrigatório no MVP — a feature não funciona sem isso |
| **Should** | Importante, mas o MVP pode ser entregue sem (planejar para a mesma fase) |
| **Could** | Nice-to-have — pode ser postergado para fase seguinte sem quebrar a feature |

---

## Status das Specs

| Spec | Status | Última atualização |
|------|--------|-------------------|-------------------|
| 01 — Gerenciamento de Remotos | Implementado | 2026-07-04 |
| 02 — Explorador de Arquivos | Implementado | 2026-07-04 |
| 03 — Jobs de Sync | Implementado | 2026-07-04 |
| 04 — Montagem VFS | Implementado | 2026-07-04 |
| 05 — Transferências Copy/Move | Implementado | 2026-07-04 |
| 06 — Verificação e Integridade | Implementado | 2026-07-04 |
| 07 — Daemon, Tray e Autostart | Implementado | 2026-07-04 |

---

## Histórico de Revisões

| Versão | Data | Autor | Mudanças |
|--------|------|-------|---------|
| 1.0 | 2026-07-04 | Emerson | Criação inicial — 7 specs definidas, ordem de implementação e dependências mapeadas |
| 1.1 | 2026-07-04 | Emerson | Todas as specs implementadas e testadas (132/132 testes) — atualização de status para Implementado |

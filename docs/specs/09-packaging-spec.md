# Spec 09 — Empacotamento .deb

> **Funcionalidade:** Geração de pacote .deb para distribuições Debian/Ubuntu
> **Responsável:** Emerson
> **Status:** Implementado v0.3.0
> **Dependências:** fpm, Python 3.9+, rclone

---

## 1. Visão Geral

O projeto é empacotado como um `.deb` que instala o Rclone GUI em `/opt/rclone-gui/` com virtualenv isolado, entry point global, autostart no login, e entrada no menu de aplicativos.

---

## 2. Estrutura do .deb

```
/opt/rclone-gui/
├── venv/
│   ├── bin/
│   │   ├── python3        # Virtualenv Python
│   │   ├── rclone-gui     # Entry point (symlink em /usr/local/bin/)
│   │   └── ...            # Dependências pip instaladas
│   └── lib/
│       └── python3.*/
│           └── site-packages/
│               └── rclone_gui/   # Código da aplicação
├── etc/
│   └── xdg/
│       └── autostart/
│           └── rclone-gui-autostart.desktop   (permissão de execução)
└── usr/
    ├── share/
    │   ├── applications/
    │   │   └── rclone-gui.desktop
    │   └── icons/
    │       └── hicolor/scalable/apps/
    │           └── rclone-gui.svg
    └── local/
        └── bin/
            └── rclone-gui -> /opt/rclone-gui/venv/bin/rclone-gui
```

---

## 3. Ciclo de Vida

### 3.1 Build

```bash
./scripts/build-deb.sh [versão]
```

O script:
1. Cria virtualenv em `/opt/rclone-gui/venv/`
2. Instala o pacote Python com pip
3. Gera entry point
4. Copia desktop files, ícone, autostart
5. Executa `fpm` para criar o .deb

**Pré-requisitos:** `gem install fpm` (Ruby), `python3-venv`, `python3-pip`

### 3.2 Instalação

```bash
sudo dpkg -i rclone-gui_0.3.0_all.deb
sudo apt install -f   # Resolve dependências
```

### 3.3 Pós-instalação (postinst.sh)

- `chmod +x` no entry point
- `ln -sf` em `/usr/local/bin/rclone-gui`
- `chmod +x` no autostart desktop file

### 3.4 Remoção (prerm.sh)

- Remove `/usr/local/bin/rclone-gui`
- Remove `/etc/xdg/autostart/rclone-gui-autostart.desktop`

---

## 4. Dependências

### Hard (Depends)
- `python3 >= 3.9`
- `python3-pip`
- `python3-venv`

### Soft (Recommends)
- `rclone` — se ausente, apt pergunta se deseja instalar; fallback via diálogo na GUI
- `fuse3` — necessário para montagens VFS

---

## 5. Verificação de rclone

### Abordagem 1 — .deb (Recommends)
O APT pergunta ao usuário se deseja instalar as dependências recomendadas.

### Abordagem 2 — GUI (fallback)
`MainWindow._check_rclone()` detecta rclone ausente e pergunta:

```
"Deseja instalar o rclone agora?
curl https://rclone.org/install.sh | sudo bash"
```

Se o usuário aceitar, executa via `QProcess` com feedback de sucesso/falha.

---

## 6. Critérios de Aceitação

1. [x] `scripts/build-deb.sh` gera .deb sem erros
2. [x] `postinst.sh` cria symlink e aplica permissões de execução
3. [x] `prerm.sh` limpa symlink e autostart
4. [x] Desktop file aparece no menu de aplicativos
5. [x] Autostart inicia o app no login do usuário
6. [x] Rclone ausente → prompt de instalação na GUI
7. [x] Todos os scripts têm `chmod +x`
8. [x] Nenhuma dependência quebra em Debian 12+ / Ubuntu 22.04+

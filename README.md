# Pi Usage — Omarchy bar widget / Widget de barra do Omarchy

Standalone Omarchy shell plugin (`ess.pi-usage`): only the `π` symbol on the bar
with a token budget timeline, like the OpenCode widget.

---

Plugin de barra do Omarchy (`ess.pi-usage`): só o símbolo `π` na barra com uma linha do tempo do orçamento em tokens, como o widget do OpenCode.

---

## English

### Description

- **Green full** = has tokens to use (free model = unlimited)
- **Red zeroed** = tokens exhausted
- **Normal color** = no data (no key / offline)

The panel shows the token budget (used of available, e.g. "82K used of 0") + local tokens: today, last 7 days and all-time, with model breakdown (input / output / cache split).

Since the OpenRouter balance comes in USD, it is converted to tokens by the price of the most used model (`/models`, 24h cache) — it is an estimate and marked with `~`. Model `:free` = price 0 = unlimited.

Sources: `~/.pi/agent/sessions/**/*.jsonl` (+ `~/.omp/...` fork) and `https://openrouter.ai/api/v1/credits` with the key from `~/.pi/agent/auth.json` (or `OPENROUTER_API_KEY`). Balance cached locally for 15 min in `~/.cache/omarchy/pi-usage/openrouter.json` (mode 600). The key is never printed or saved anywhere else.

### Structure

- `manifest.json` — id `ess.pi-usage`, kind `bar-widget`, entry `Panel.qml`
- `Panel.qml` — chip `π 12.3K` + panel (totals, per day, per model)
- `PiBackend.qml` — runs `scripts/pi-usage.py` via `Process`, keeps last good result
- `scripts/pi-usage.py` — stdlib-only, reads JSONL, emits JSON `{id:"pi", todayTotalTokens, recentDays, modelUsage, ...}`
- `assets/pi.svg` — widget icon
- `tests/` — fixtures + quick test

### Test backend

```bash
python3 scripts/pi-usage.py | jq .
python3 tests/test_pi_usage.py
```

With fake session:

```bash
mkdir -p ~/.pi/agent/sessions
cat tests/fixture.jsonl >> ~/.pi/agent/sessions/test.jsonl
python3 scripts/pi-usage.py | jq '{today: .todayTotalTokens, total: .totalPrompts, models: .modelUsage}'
```

### Install / Uninstall

**Install:**
```bash
omarchy plugin validate ~/Documents/piuser
cp -r ~/Documents/piuser ~/.config/omarchy/plugins/ess.pi-usage
omarchy plugin enable ess.pi-usage
# add {"id":"ess.pi-usage"} to bar.layout.right in ~/.config/omarchy/shell.json
omarchy restart shell
```

**Uninstall:**
```bash
omarchy plugin disable ess.pi-usage
rm -rf ~/.config/omarchy/plugins/ess.pi-usage
omarchy restart shell
```

Panel keys: `r` refresh, `Esc` close. Right-click on chip forces refresh. `omarchy-shell ess.pi-usage refresh` via IPC.

---

## Português

### Descrição

- **Verde cheio** = tem tokens para usar (modelo free = ilimitado)
- **Vermelho zerado** = tokens esgotados
- **Cor normal** = sem dados (sem chave / offline)

O painel mostra o orçamento em tokens (usado de disponível, ex. "82K used of 0") + tokens locais: hoje, últimos 7 dias e all-time, com breakdown por modelo (input / output / cache split).

Como o saldo OpenRouter vem em USD, ele é convertido em tokens pelo preço do modelo mais usado (`/models`, cache de 24h) — é estimativa e vai marcada com `~`. Modelo `:free` = preço 0 = ilimitado.

Fontes: `~/.pi/agent/sessions/**/*.jsonl` (+ `~/.omp/...` fork) e `https://openrouter.ai/api/v1/credits` com a chave de `~/.pi/agent/auth.json` (ou `OPENROUTER_API_KEY`). Saldo com cache local de 15 min em `~/.cache/omarchy/pi-usage/openrouter.json` (modo 600). A chave nunca é impressa nem salva em outro lugar.

### Estrutura

- `manifest.json` — id `ess.pi-usage`, kind `bar-widget`, entry `Panel.qml`
- `Panel.qml` — chip `π 12.3K` + painel (totais, por dia, por modelo)
- `PiBackend.qml` — roda `scripts/pi-usage.py` via `Process`, guarda último bom resultado
- `scripts/pi-usage.py` — stdlib-only, lê JSONL, emite JSON `{id:"pi", todayTotalTokens, recentDays, modelUsage, ...}`
- `assets/pi.svg` — marca do widget
- `tests/` — fixture + teste rápido

### Testar backend

```bash
python3 scripts/pi-usage.py | jq .
python3 tests/test_pi_usage.py
```

Com sessão fake:

```bash
mkdir -p ~/.pi/agent/sessions
cat tests/fixture.jsonl >> ~/.pi/agent/sessions/test.jsonl
python3 scripts/pi-usage.py | jq '{today: .todayTotalTokens, total: .totalPrompts, models: .modelUsage}'
```

### Validar / instalar

```bash
omarchy plugin validate ~/Documents/piuser
cp -r ~/Documents/piuser ~/.config/omarchy/plugins/ess.pi-usage
omarchy plugin enable ess.pi-usage
# adicionar {"id":"ess.pi-usage"} em bar.layout.right no ~/.config/omarchy/shell.json
omarchy restart shell
```

### Remover

```bash
omarchy plugin disable ess.pi-usage
rm -rf ~/.config/omarchy/plugins/ess.pi-usage
omarchy restart shell
```

Teclas no painel: `r` refresh, `Esc` fecha. Botão direito no chip força refresh. `omarchy-shell ess.pi-usage refresh` via IPC.

---

☕ **Gostou?** Me apoie no [Ko-fi](https://ko-fi.com/eds4d5)

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/eds4d5)

---

# Plugin info / Informações do plugin

- **Author / Autor**: ess (https://github.com/eds-4d5)
- **License / Licença**: MIT
- **Repository / Repositório**: https://github.com/eds-4d5/pi-usage
- **Marketplace / Marketplace**: https://github.com/omacom/omarchy-plugin-marketplace/issues/8592
- **Release / Versão**: https://github.com/eds-4d5/pi-usage/releases/tag/v0.1.0
- **Contributors / Contribuintes**: [CONTRIBUTORS.md](CONTRIBUTORS.md)

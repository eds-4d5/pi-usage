# Pi Usage — Omarchy bar widget / Widget de barra do Omarchy

Standalone Omarchy shell plugin (`ess.pi-usage`): only the `π` symbol on the bar
with a token budget timeline, like the OpenCode widget.

Plugin de barra do Omarchy (`ess.pi-usage`): só o símbolo `π` na barra
com uma linha do tempo do orçamento em tokens, como o widget do OpenCode.

- **Verde cheio** = tem tokens para usar (modelo free = ilimitado)
- **Vermelho zerado** = tokens esgotados
- **Cor normal** = sem dados (sem chave / offline)

O painel mostra o orçamento em tokens (usado de disponível, ex. "82K
used of 0") + tokens locais: hoje, últimos 7 dias e all-time, com
breakdown por modelo (input / output / cache read / cache write).

Como o saldo OpenRouter vem em USD, ele é convertido em tokens pelo
preço do modelo mais usado (`/models`, cache de 24 h) — é estimativa e
vai marcada com `~`. Modelo `:free` = preço 0 = ilimitado.

Fontes: `~/.pi/agent/sessions/**/*.jsonl` (+ `~/.omp/...` fork) e
`https://openrouter.ai/api/v1/credits` com a chave de
`~/.pi/agent/auth.json` (ou `OPENROUTER_API_KEY`). Saldo com cache
local de 15 min em `~/.cache/omarchy/pi-usage/openrouter.json` (modo
600). A chave nunca é impressa nem salva em outro lugar.

## Dev aqui, instala ali

Esta pasta `~/Documents/piuser` é o código-fonte. O shell só carrega de `~/.config/omarchy/plugins/`.

## Estrutura

- `manifest.json` — id `ess.pi-usage`, kind `bar-widget`, entry `Panel.qml`
- `Panel.qml` — chip `π 12.3K` + painel (totais, por dia, por modelo)
- `PiBackend.qml` — roda `scripts/pi-usage.py` via `Process`, guarda último bom resultado
- `scripts/pi-usage.py` — stdlib-only, lê JSONL, emite JSON `{id:"pi", todayTotalTokens, recentDays, modelUsage, ...}`
- `assets/pi.svg` — marca do widget
- `tests/` — fixture + teste rápido

## Testar backend

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

## Validar / instalar

```bash
omarchy plugin validate ~/Documents/piuser
cp -r ~/Documents/piuser ~/.config/omarchy/plugins/ess.pi-usage
omarchy plugin enable ess.pi-usage
# adicionar {"id":"ess.pi-usage"} em bar.layout.right no ~/.config/omarchy/shell.json
omarchy restart shell
```

Teclas no painel: `r` refresh, `Esc` fecha. Botão direito no chip força refresh.
`omarchy-shell ess.pi-usage refresh` via IPC.

---

## Instalação / Installation

```bash
omarchy plugin validate ~/Documents/piuser
cp -r ~/Documents/piuser ~/.config/omarchy/plugins/ess.pi-usage
omarchy plugin enable ess.pi-usage
omarchy restart shell
```

## Remoção / Uninstall

```bash
omarchy plugin disable ess.pi-usage
rm -rf ~/.config/omarchy/plugins/ess.pi-usage
omarchy restart shell
```

---

☕ **Gostou?** Me apoie no [Ko-fi](https://ko-fi.com/eds4d5)

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/eds4d5)

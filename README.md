# sk_files — SKAI file assistant

A terminal assistant of [Skorpion OS](https://github.com/Endrx2008/skorpion_os): you say in plain words
what to do with your files and **SKAI** does it, inside one folder on your desktop. It can also look
things up on the web. *Italiano: [README.it.md](README.it.md).*

## In Skorpion OS

Already installed, in a hidden folder of your home: nothing to download, and there is no release. Open a
terminal and type:

```sh
skai
```

(`skai` is an alias for `python3 main.py` in that folder.)

It works only inside **`sk_files_home`**, a folder on your desktop (the real one, whatever its name in
your language: `Desktop`, `Scrivania`, `Bureau`…). Check where with `python3 config.py`.

## What you can ask

- **Files:** create, read, edit, rename, move into a subfolder, delete one or all (up to 100 files).
  Before deleting anything sk_files asks `[y/N]`; Enter alone means no.
- **Folders** (only inside `sk_files_home`): create, rename, move, delete, list.
- **Web:** questions about current facts are searched on DuckDuckGo and answered in plain text.

In the prompt: `files` lists the files, `exit` quits; start a line with `!` to force a file action or
with `?` to force a plain answer.

## SKAI

sk_files talks to the local Ollama (`http://localhost:11434`) and uses the installed model with the most parameters. If
Ollama is off or has no model, it explains that the AI is disabled and exits. Models are managed with
SKAI Manager (Alt + F9).

Memory: facts worth keeping are stored in `.sk_files_memory.json` next to the script. When SKAI_ Memory is
installed (it comes with the `sk-notes` package) sk_files also reads what the other SKAI apps know and
records each exchange in its own notes (`plugins/sk_files`).

## Files

| File | What it is |
|---|---|
| `main.py` | the assistant: model choice, chat loop, tool calls |
| `config.py` | Ollama address, desktop detection, system prompt, tool names |
| `fs_*.py` | one module per file or folder action |
| `memory.py` | the assistant's own long-term memory |
| `web_access.py` | DuckDuckGo search |

Needs Python 3 and `requests`, part of Skorpion OS.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE). © 2026 Enrico Miot (EndrX), founder and maintainer of Skorpion OS.

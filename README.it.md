# sk_files — assistente SKAI per i file

Un assistente da terminale di [Skorpion OS](https://github.com/Endrx2008/skorpion_os): dici a parole cosa
fare con i tuoi file e **SKAI** lo fa, dentro una cartella sulla scrivania. Può anche cercare sul web.
*English: [README.md](README.md).*

## In Skorpion OS

È già installato, in una cartella nascosta della tua home: non c'è nulla da scaricare e non esiste una
release. Apri un terminale e scrivi:

```sh
skai
```

(`skai` è un alias di `python3 main.py` in quella cartella.)

Lavora solo dentro **`sk_files_home`**, una cartella sulla scrivania (quella vera, qualunque sia il suo
nome nella tua lingua: `Scrivania`, `Desktop`, `Bureau`…). Per vedere dove: `python3 config.py`.

## Cosa puoi chiedere

- **File:** creare, leggere, modificare, rinominare, spostare in una sottocartella, eliminarne uno o tutti
  (fino a 100 file). Prima di eliminare qualcosa sk_files chiede `[y/N]`; solo Invio vuol dire no.
- **Cartelle** (solo dentro `sk_files_home`): creare, rinominare, spostare, eliminare, elencare.
- **Web:** le domande su fatti attuali vengono cercate su DuckDuckGo e la risposta è in testo semplice.

Nel prompt: `files` elenca i file, `exit` esce; inizia una riga con `!` per forzare un'azione sui file o
con `?` per forzare una risposta semplice.

## SKAI

sk_files parla con Ollama in locale (`http://localhost:11434`) e usa il modello installato con più parametri. Se
Ollama è spento o non ha modelli, spiega che l'IA è disattivata ed esce. I modelli si gestiscono con SKAI
Manager (Alt + F9).

Memoria: i fatti da ricordare sono salvati in `.sk_files_memory.json` accanto allo script. Se SKAI_ Memory è
installata (arriva con il pacchetto `sk-notes`) sk_files legge anche cosa sanno le altre app SKAI e
registra ogni scambio nelle sue note (`plugins/sk_files`).

## File

| File | Cos'è |
|---|---|
| `main.py` | l'assistente: scelta del modello, conversazione, chiamate agli strumenti |
| `config.py` | indirizzo di Ollama, ricerca della scrivania, prompt di sistema, nomi degli strumenti |
| `fs_*.py` | un modulo per ogni azione su file o cartelle |
| `memory.py` | la memoria a lungo termine dell'assistente |
| `web_access.py` | ricerca su DuckDuckGo |

Servono Python 3 e `requests`, già presenti in Skorpion OS.

## Licenza

GPL-3.0-or-later, vedi [LICENSE](LICENSE). © 2026 Enrico Miot (EndrX), fondatore e manutentore di Skorpion OS.

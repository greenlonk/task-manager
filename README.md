# Task‑Manager ⏰

A **one‑file FastAPI + APScheduler** app that sends ntfy push notifications at cron‑like times.  
Perfect for personal reminders (laundry, trash‑day, …) without running a full task‑queue stack.

---

## ✨ Features

* CRUD your tasks from a tiny web UI (Tailwind + HTMX).
* Cron expressions with human‑readable preview.
* SQLite job‑store.
* Sends to **any** ntfy server you point it at.

---

## 🚀 Quick start

```bash
# 1. clone & enter
$ git clone https://github.com/greenlonk/task‑manager.git
$ cd task‑manager

# 2. create and activate virtual env (uv makes it fast!)
$ uv venv .venv
$ source .venv/bin/activate  # fish/zsh users: adjust path

# 3. install dependencies from `pyproject.toml`
$ uv sync

# 4. configure your ntfy endpoint (default is ntfy.sh)
$ export NTFY_URL="https://ntfy.example.com"

# 5. run the app
$ uvicorn app:app --reload
```

Navigate to <http://localhost:8000> and add your first task.

---

## 🔧 Configuration

| Variable     | Default                         | Purpose                          |
|--------------|---------------------------------|----------------------------------|
| `NTFY_URL`   | `https://ntfy.sh`               | Base URL of your ntfy server     |
| `TZ`         | `Europe/Berlin`                 | Scheduler timezone               |

Set variables in your shell (`export VAR=value`) or in a `.env` file if you use a dotenv loader.

---

## 🗃️ Project layout

```
.
├── app.py                # main FastAPI + scheduler file
├── templates/
│   ├── index.html        # page skeleton + form
│   └── tasks_fragment.html  # "sticker" swapped by HTMX
├── tasks.db              # SQLite database (auto‑created)
└── pyproject.toml        # deps managed by `uv`
```



---

## 📜 License

MIT — free for personal & commercial use.  

---

### 🙏 Credits

* **[ntfy](https://github.com/binwiederhier/ntfy)** 
* **[FastAPI](https://fastapi.tiangolo.com/)** & **[APScheduler](https://github.com/agronholm/apscheduler)**
* **TailwindCSS** & **HTMX** 



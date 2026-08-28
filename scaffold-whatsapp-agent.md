# Scaffold — WhatsApp Agent

Setup instructions for a new Python project. **Scaffolding only — do not write any application code yet.**

---

## 1. Initialize git

```bash
git init
```

## 2. Create the virtual environment

```bash
python3 -m venv ./venv
```

## 3. Create `.gitignore` FIRST

Before any other file. Contents:

```gitignore
.env
venv/
__pycache__/
*.pyc
.DS_Store
*.log
credentials.json
credentials.txt
```

## 4. Create `.env.example`

Containing **only** these two lines and nothing else:

```dotenv
# Supabase
SUPABASE_URL=
```

Rules:

- Do not add any other environment variables.
- As the build progresses and a new variable is needed, add it to `.env.example` at that point, grouped under a comment heading, and tell me what value to put in it.
- Do not create `.env` itself.
- Never ask me for a secret value.

## 5. Create `requirements.txt`

Only:

```text
python-dotenv
pytest
```

Add other dependencies as the build actually requires them.

## 6. Create empty directories

- `app/`
- `tests/`

## 7. Create `README.md`

With the project name and one line describing it as a *(project name)*.

## 8. Verify the work

Run and show the output of:

```bash
ls -la
cat .gitignore
```

Confirm both `.env` and `credentials.json` are listed in `.gitignore` before finishing.

## 9. Create the GitHub repo

- Private repo named *(name)* using the `gh` CLI
- Commit everything with the message: `Initial project scaffold`
- Push

Report what was created and paste the verification output.

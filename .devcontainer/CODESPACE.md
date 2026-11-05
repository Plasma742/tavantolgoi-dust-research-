# Running the site in this Codespace

This Codespace runs the **whole** research site in GitHub's cloud: the FastAPI backend and the dashboard. It is a **private** research prototype, not a public website.

## Start

1. Open a terminal (**Terminal → New Terminal**) and run:
   ```bash
   bash .devcontainer/start.sh
   ```
2. The first time, it asks for your **Earth Engine project ID**. Then it shows a Google sign-in link: open it, sign in, and paste the code back into the terminal. If you just press Enter at the project-ID prompt, the site starts in `NOT_CONFIGURED` mode and shows no data.
3. The dashboard opens in a new tab. If it doesn't, open the **PORTS** tab and click the globe icon next to **Dashboard (keep PRIVATE)**.

## Keep it private

- Forwarded ports are **private** by default: only your GitHub account can open them. **Never change port visibility to Public.** That would create a public URL before scientific review, which the project does not allow (see `docs/DEPLOYMENT_CHECKLIST.md`).
- Do not forward port 8000. The dashboard reaches the API through its own proxy.
- Earth Engine credentials live in this Codespace's home folder (`~/.config/earthengine/`). They are not in git, and they are deleted when the Codespace is deleted.

## Stop

Press **Ctrl+C** in the terminal. Stop the Codespace when you finish (GitHub → Codespaces → ⋯ → Stop) so it doesn't use your monthly Codespaces allowance.

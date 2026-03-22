# Deploy to Streamlit Community Cloud

Follow these steps to deploy the Campaign Optimizer so it runs in the cloud.

## 1. Push your code to GitHub

Make sure this repo is pushed to GitHub (e.g. `https://github.com/davidhundia-boop/AdOps`).

## 2. Go to Streamlit Community Cloud

1. Open **https://share.streamlit.io**
2. Sign in with your GitHub account.
3. Click **"New app"**.

## 3. Configure the app

Use these settings:

| Field | Value |
|-------|--------|
| **Repository** | `davidhundia-boop/AdOps` (or your fork) |
| **Branch** | `main` |
| **Main file path** | `campaign-optimizer/app_streamlit.py` |
| **App URL** | (optional) e.g. `campaign-optimizer` |

- **Requirements file**: leave blank so Streamlit uses the **root** `requirements.txt` (recommended), or set **Advanced settings → Requirements file** to `requirements.txt` (root).
- Do **not** set the working directory to `campaign-optimizer`; the app is written to run from the repo root.

## 4. Deploy

Click **"Deploy!"**. The first run may take a few minutes while dependencies install.

## 5. If it still fails

- **Build logs**: In the app page, open **"Manage app"** → **"Logs"** to see errors.
- **Import errors**: The app adds `campaign-optimizer` to `sys.path` so `optimizer` is found when run from the repo root. If you see `ModuleNotFoundError: No module named 'optimizer'`, confirm the main file path is exactly `campaign-optimizer/app_streamlit.py`.
- **Requirements**: The root `requirements.txt` lists `streamlit`, `pandas`, `openpyxl`, `xlrd`, `numpy`. If the build fails on a missing package, add it there and push.

## Optional: run from subfolder only

If you prefer the app to run with working directory inside `campaign-optimizer`, you would need to move or duplicate `requirements.txt` into `campaign-optimizer/` and point Streamlit at that folder. The current setup is designed for **main file path** `campaign-optimizer/app_streamlit.py` and **requirements** at repo root.

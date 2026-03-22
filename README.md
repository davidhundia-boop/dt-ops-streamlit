# DT Ops Streamlit

Streamlit UI apps for Digital Turbine internal tools.
Agent/CLI entry points are in the [`dt-ops-tools`](https://github.com/davidhundia-boop/dt-ops-tools) repo.

## Apps

| App | Folder | Run Command |
|-----|--------|-------------|
| AdOps Optimizer | `/adops_optimizer` | `streamlit run adops_optimizer/app.py` |
| App QA | `/app_qa` | `streamlit run app_qa/app.py` |
| Tracking Link Builder | `/tracking_link_builder` | `streamlit run tracking_link_builder/app.py` |

## Local run

```bash
cd dt-ops-streamlit
pip install -r requirements.txt
streamlit run adops_optimizer/app.py
```

See `DEPLOY.md` for Streamlit Community Cloud.

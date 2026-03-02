# 🚀 MoodPulse — Sistema de Análise de Sentimentos em Tempo Real

Implementação em Python (FastAPI) com foco em determinismo, performance (<200ms para 1000 mensagens) e arquitetura limpa.

## ⚙️ Executar
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
````

API disponível em: [http://localhost:8000](http://localhost:8000)

## 🧪 Testes
```bash
pytest -q
```
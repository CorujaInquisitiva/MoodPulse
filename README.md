# 🚀 MoodPulse — Sistema de Análise de Sentimentos em Tempo Real

MoodPulse é uma aplicação em **Python** utilizando **FastAPI**, projetada para ser rápida, determinística e de fácil manutenção. Processa até **1000 mensagens em menos de 200ms**, seguindo princípios de **arquitetura limpa**.

## ⚙️ Executar

1. **Criar o ambiente virtual**

```bash
py -m venv .venv
```

Cria um ambiente isolado para a aplicação, evitando conflitos de dependências com outros projetos Python.

2. **Ativar o ambiente virtual**

```bash
.venv/Scripts/activate
```

Ativa o ambiente criado, garantindo que os pacotes instalados sejam usados apenas aqui.

3. **Instalar dependências**

```bash
pip install -r requirements.txt
```

Instala todas as bibliotecas necessárias listadas no `requirements.txt`.

4. **Rodar a aplicação**

```bash
uvicorn main:app --reload
```

Inicia o servidor FastAPI em modo de desenvolvimento, com **hot reload**, permitindo acessar a API em: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 🧪 Testes

```bash
pytest -q
```

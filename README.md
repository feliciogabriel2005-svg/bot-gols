# ⚽ Live Betting Opportunity Scanner — Bot de Análise de Gols (Produção)

Sistema profissional de monitoramento e análise de partidas de futebol ao vivo em tempo real para identificação de oportunidades no mercado de gols (Over 0.5 Gols) utilizando Índices de Pressão Ofensiva, Modelo Estocástico de Poisson, Apuração de Edge e EV, Notificações via Telegram e Validação por Paper Trading.

---

## 🛠️ 1. Instalação das Dependências

Certifique-se de utilizar o **Python 3.10+**.

No servidor ou ambiente local, execute:

```bash
pip install -r requirements.txt
```

---

## 🔑 2. Configuração do Arquivo `.env`

Crie um arquivo `.env` na raiz do projeto (ou dentro da pasta `bot_gols/`) com base no `.env.example`:

```env
APP_ENV=PRODUCTION
MODE=PAPER_TRADING
POLL_INTERVAL_SECONDS=30
DB_PATH=production_live.db

PAPER_STAKE=100
PAPER_BANKROLL=1000

API_FOOTBALL_KEY=sua_chave_api_aqui
API_FOOTBALL_HOST=v3.football.api-sports.io

TELEGRAM_BOT_TOKEN=seu_bot_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui

ENABLE_REAL_BETTING=FALSE
```

---

## 🚀 3. Como Executar o Bot

### A. Iniciar o Scanner Backend
```bash
python bot_gols/src/scripts/run_bot.py
```

### B. Iniciar o Dashboard (Acesso local e Mobile)
```bash
streamlit run bot_gols/src/dashboard/main_app.py --server.address 0.0.0.0
```

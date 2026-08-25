import requests
import logging
from config import SystemConfig
from models.signal import Signal

class TelegramNotifier:
    def __init__(self):
        self.config = SystemConfig()
        self.token = self.config.TELEGRAM_BOT_TOKEN
        self.chat_id = self.config.TELEGRAM_CHAT_ID

    def send_opportunity_alert(self, signal: Signal) -> bool:
        if not self.token or not self.chat_id:
            logging.info("[TELEGRAM] Notificação omitida: Token ou Chat ID não configurados")
            return False

        message = (
            f"🔥 *NOVA OPORTUNIDADE DETECTADA* [{signal.confidence_grade}]\n"
            f"-----------------------------------\n"
            f"⚽ *Jogo:* {signal.match_name}\n"
            f"⏱️ *Minuto:* {signal.minute}' | *Placar:* {signal.score}\n"
            f"📊 *Mercado:* {signal.market}\n"
            f"📈 *Odd Ao Vivo:* {signal.odd}\n"
            f"🎯 *Prob. Calibrada:* {signal.estimated_prob}%\n"
            f"📉 *Prob. Implícita:* {signal.implied_prob}%\n"
            f"⚡ *Edge Estimado:* +{signal.edge} pp\n"
            f"💰 *EV Esperado:* +{signal.ev}%\n"
            f"💪 *Índice de Pressão:* {signal.pressure_score}/100\n"
            f"⭐️ *Score de Confiança:* {signal.confidence_score}/100\n\n"
            f"*MOTIVOS DO SINAL:*\n"
        )
        for reason in signal.reasons:
            message += f"• {reason}\n"

        message += f"\n_Modo: PAPER TRADING (Aposta Virtual)_"

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code == 200:
                logging.info(f"[TELEGRAM] Alerta enviado para Chat ID {self.chat_id}")
                return True
            else:
                logging.error(f"[TELEGRAM] Erro no envio HTTP {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logging.error(f"[TELEGRAM] Exceção no envio: {e}")
            return False

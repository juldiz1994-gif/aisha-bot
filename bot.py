import os
import asyncio
import logging
import aiohttp
import edge_tts
import tempfile
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]

VOICES = {
    "kk": "kk-KZ-AigulNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "en": "en-US-JennyNeural",
}

WELCOME_TEXT = (
    "\U0001f44b Сәлем! Мен — *Айша Бот* \U0001f916\n\n"
    "Тегін мүмкіндіктер:\n"
    "\U0001f3b5 Кез келген мәтінді аудиоға айналдырамын\n"
    "\U0001f5bc Сипаттама бойынша сурет жасаймын\n\n"
    "Не жасайық?"
)


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f3b5 Аудио жасау", callback_data="mode:audio")],
        [InlineKeyboardButton("\U0001f5bc Сурет жасау", callback_data="mode:image")],
        [InlineKeyboardButton("❓ Көмек", callback_data="help")],
    ])


def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f519 Басты мәзір", callback_data="back")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "audio"
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *Пайдалану нұсқаулығы*\n\n"
        "1️⃣ *\U0001f3b5 Аудио:* Режимді таңдап, мәтін жіберіңіз\n"
        "   • Қазақша, орысша, ағылшынша қолдайды\n"
        "   • Тіл автоматты анықталады\n\n"
        "2️⃣ *\U0001f5bc Сурет:* Режимді таңдап, ағылшынша сипаттама жіберіңіз\n"
        "   • Мысалы: `beautiful Kazakh woman, traditional dress, sunset`\n"
        "   • 30-60 секунд күтіңіз\n\n"
        "Барлығы *тегін!* \U0001f389",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("mode:"):
        mode = query.data.split(":")[1]
        context.user_data["mode"] = mode

        if mode == "audio":
            await query.edit_message_text(
                "\U0001f3b5 *Аудио жасау режимі қосылды*\n\n"
                "Аудиоға айналдырғыңыз келетін мәтінді жіберіңіз.\n"
                "Қазақша, орысша немесе ағылшынша болуы мүмкін.\n\n"
                "_Мысалы: Сәлем! Бүгін күн жылы._",
                parse_mode="Markdown",
                reply_markup=back_button()
            )
        elif mode == "image":
            await query.edit_message_text(
                "\U0001f5bc *Сурет жасау режимі қосылды*\n\n"
                "Суреттің сипаттамасын ағылшынша жіберіңіз.\n\n"
                "_Мысалы: beautiful Kazakh girl in traditional dress, mountains, golden hour, realistic_",
                parse_mode="Markdown",
                reply_markup=back_button()
            )

    elif query.data == "help":
        await query.edit_message_text(
            "❓ *Пайдалану нұсқаулығы*\n\n"
            "1️⃣ *Аудио:* Кез келген мәтін жіберіңіз\n"
            "   • Қазақша, орысша, ағылшынша\n"
            "   • Бот тілді автоматты анықтайды\n\n"
            "2️⃣ *Сурет:* Ағылшынша сипаттама жіберіңіз\n"
            "   • Нақты сипаттама жақсы нәтиже береді\n"
            "   • 30-60 секунд күтіңіз\n\n"
            "Барлығы *тегін!* \U0001f389",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("\U0001f519 Басты мәзір", callback_data="back")]
            ])
        )

    elif query.data == "back":
        context.user_data["mode"] = "audio"
        await query.edit_message_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu())


def detect_voice(text: str) -> str:
    kazakh_specific = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
    if any(c in kazakh_specific for c in text):
        return VOICES["kk"]
    cyrillic_count = sum(1 for c in text if "Ѐ" <= c <= "ӿ")
    if cyrillic_count > len(text) * 0.25:
        return VOICES["ru"]
    return VOICES["en"]


async def generate_audio(update: Update, text: str):
    if len(text) > 2000:
        await update.message.reply_text("⚠️ Мәтін тым ұзын (макс. 2000 символ). Қысқартып жіберіңіз.")
        return

    msg = await update.message.reply_text("⏳ Аудио жасалуда...")
    tmp_path = None
    try:
        voice = detect_voice(text)
        communicate = edge_tts.Communicate(text, voice)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        await communicate.save(tmp_path)
        await msg.delete()

        preview = text[:80] + ("..." if len(text) > 80 else "")
        with open(tmp_path, "rb") as f:
            await update.message.reply_audio(
                audio=f,
                caption=f"\U0001f3b5 *Аудио дайын!*\n_{preview}_",
                parse_mode="Markdown",
                reply_markup=back_button()
            )
    except Exception as e:
        logger.error(f"Audio error: {e}")
        await msg.edit_text("❌ Қате болды. Мәтінді тексеріп, қайтадан жіберіңіз.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def generate_image(update: Update, prompt: str):
    msg = await update.message.reply_text("⏳ Сурет жасалуда... (~30 секунд күтіңіз)")
    tmp_path = None
    try:
        encoded = urllib.parse.quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            "?width=1024&height=1024&nologo=true&enhance=true"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        tmp.write(data)
                        tmp_path = tmp.name

                    await msg.delete()
                    preview = prompt[:80] + ("..." if len(prompt) > 80 else "")
                    with open(tmp_path, "rb") as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=f"\U0001f5bc *Сурет дайын!*\n_{preview}_",
                            parse_mode="Markdown",
                            reply_markup=back_button()
                        )
                else:
                    await msg.edit_text("❌ Сурет жасалмады. Басқа сипаттама жіберіңіз.")

    except asyncio.TimeoutError:
        await msg.edit_text("⏱ Уақыт асып кетті. Қайтадан көріңіз.")
    except Exception as e:
        logger.error(f"Image error: {e}")
        await msg.edit_text("❌ Қате болды. Қайтадан көріңіз.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode", "audio")
    text = update.message.text

    if mode == "image":
        await generate_image(update, text)
    else:
        await generate_audio(update, text)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Айша Бот іске қосылды! \U0001f680")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

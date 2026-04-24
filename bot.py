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

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]

VOICES = {
    "kk": "kk-KZ-AigulNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "en": "en-US-JennyNeural",
}


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 Аудио жасау", callback_data="mode:audio")],
        [InlineKeyboardButton("🖼 Сурет жасау", callback_data="mode:image")],
    ])


def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Басты мәзір", callback_data="back")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "audio"
    await update.message.reply_text(
        "👋 Сәлем! Мен — *Айша Бот* 🤖\n\n"
        "🎵 Мәтінді аудиоға айналдырамын\n"
        "🖼 Сипаттама бойынша сурет жасаймын\n\n"
        "Режимді таңдаңыз:",
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
                "🎵 *Аудио режимі*\n\nМәтінді жіберіңіз — қазақша, орысша немесе ағылшынша.",
                parse_mode="Markdown",
                reply_markup=back_button()
            )
        elif mode == "image":
            await query.edit_message_text(
                "🖼 *Сурет режимі*\n\nСуреттің сипаттамасын жіберіңіз.\n\n"
                "_Мысалы: beautiful Kazakh girl, mountains, golden hour_",
                parse_mode="Markdown",
                reply_markup=back_button()
            )

    elif query.data == "back":
        context.user_data["mode"] = "audio"
        await query.edit_message_text(
            "👋 Сәлем! Мен — *Айша Бот* 🤖\n\n"
            "🎵 Мәтінді аудиоға айналдырамын\n"
            "🖼 Сипаттама бойынша сурет жасаймын\n\n"
            "Режимді таңдаңыз:",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )


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
        await update.message.reply_text("⚠️ Мәтін тым ұзын (макс. 2000 символ).")
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
                caption=f"🎵 *Аудио дайын!*\n_{preview}_",
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
    msg = await update.message.reply_text("⏳ Сурет жасалуда... (~30 секунд)")
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
                            caption=f"🖼 *Сурет дайын!*\n_{preview}_",
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
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Айша Бот іске қосылды!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

from telegram import Update, InlineKeyboardMarkup, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import CallbackContext
from telegram.error import BadRequest
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handle_message_not_modified(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except BadRequest as e:
            logger.info(f"Возникла ошибка BadRequest {e}")
            pass
        except Exception as e:
            logger.info(f"Возникла ошибка Exception {e}")

    return wrapper


@handle_message_not_modified
async def send_or_edit_message(update: Update, context: CallbackContext, text: str,
                               reply_markup: InlineKeyboardMarkup = None, new_message=False):
    if new_message:
        message = await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return message

    if update.callback_query:
        if update.callback_query.message.text:
            try:
                await update.callback_query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                return update.callback_query.message
            except Exception:
                # Попытка удалить сообщение, если редактирование не удалось
                try:
                    await update.callback_query.message.delete()
                except Exception:
                    pass  # Просто игнорируем, если удалить нельзя
                message = await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                return message
        else:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass  # Если не удалось удалить, продолжаем
            message = await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return message
    else:
        message = await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return message


async def send_or_edit_photo(update: Update, context: CallbackContext, photo, caption: str = "",
                             reply_markup: InlineKeyboardMarkup = None, new_message=False):
    if new_message:
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return

    if update.callback_query:
        if update.callback_query.message.photo:
            try:
                await update.callback_query.edit_message_media(
                    media=InputMediaPhoto(media=photo, caption=caption, parse_mode=ParseMode.HTML),
                    reply_markup=reply_markup
                )
            except Exception:
                # Попытка удалить сообщение, если редактирование не удалось
                try:
                    await update.callback_query.message.delete()
                except Exception:
                    pass  # Просто игнорируем, если удалить нельзя
                await context.bot.send_photo(
                    chat_id=update.effective_user.id,
                    photo=photo,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
        else:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass  # Если не удалось удалить, продолжаем
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
    else:
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

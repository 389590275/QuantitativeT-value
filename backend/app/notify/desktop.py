import logging
import threading

logger = logging.getLogger(__name__)


def send_desktop_notification(title: str, message: str) -> None:
    def _notify() -> None:
        try:
            from plyer import notification

            notification.notify(
                title=title[:64],
                message=message[:256],
                app_name="T0量化助手",
                timeout=8,
            )
        except Exception as e:
            logger.warning("desktop notify failed: %s", e)

    threading.Thread(target=_notify, daemon=True).start()

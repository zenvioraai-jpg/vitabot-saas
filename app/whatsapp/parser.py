from dataclasses import dataclass
from app.webhook.models import WebhookPayload


@dataclass
class IncomingMessage:
    phone_number: str
    wa_message_id: str
    text: str
    receiving_phone_number_id: str = ""  # phone_number_id de Meta que RECIBIÓ el mensaje
                                          # (identifica a qué empresa/tenant pertenece)
    display_name: str | None = None
    image_media_id: str | None = None
    image_mime_type: str = "image/jpeg"
    audio_media_id: str | None = None
    audio_mime_type: str = "audio/ogg"
    document_media_id: str | None = None
    document_mime_type: str = "application/pdf"


def extract_message(payload: WebhookPayload) -> IncomingMessage | None:
    """Extract text, image, or audio messages from the webhook payload."""
    for entry in payload.entry:
        for change in entry.changes:
            value = change.value
            if not value.messages:
                continue
            phone_number_id = (value.metadata or {}).get("phone_number_id", "")
            for raw_msg in value.messages:
                msg_type = raw_msg.get("type")
                if msg_type not in ("text", "image", "audio", "document"):
                    continue

                phone = raw_msg.get("from", "")
                wa_id = raw_msg.get("id", "")

                display_name = None
                if value.contacts:
                    for contact in value.contacts:
                        if contact.get("wa_id") == phone:
                            display_name = contact.get("profile", {}).get("name")
                            break

                if msg_type == "text":
                    text = raw_msg.get("text", {}).get("body", "").strip()
                    if not text:
                        continue
                    return IncomingMessage(
                        phone_number=phone, wa_message_id=wa_id,
                        text=text, display_name=display_name,
                        receiving_phone_number_id=phone_number_id,
                    )

                if msg_type == "image":
                    data = raw_msg.get("image", {})
                    media_id = data.get("id", "")
                    mime_type = data.get("mime_type", "image/jpeg")
                    caption = data.get("caption", "").strip()
                    return IncomingMessage(
                        phone_number=phone, wa_message_id=wa_id,
                        text=caption or "[imagen]", display_name=display_name,
                        image_media_id=media_id, image_mime_type=mime_type,
                        receiving_phone_number_id=phone_number_id,
                    )

                if msg_type == "audio":
                    data = raw_msg.get("audio", {})
                    media_id = data.get("id", "")
                    mime_type = data.get("mime_type", "audio/ogg")
                    if media_id:
                        return IncomingMessage(
                            phone_number=phone, wa_message_id=wa_id,
                            text="[audio]", display_name=display_name,
                            audio_media_id=media_id, audio_mime_type=mime_type,
                            receiving_phone_number_id=phone_number_id,
                        )

                if msg_type == "document":
                    # Comprobante en PDF (o imagen enviada como documento)
                    data = raw_msg.get("document", {})
                    media_id = data.get("id", "")
                    mime_type = data.get("mime_type", "application/pdf")
                    caption = (data.get("caption", "") or "").strip()
                    if media_id:
                        return IncomingMessage(
                            phone_number=phone, wa_message_id=wa_id,
                            text=caption or "[documento]", display_name=display_name,
                            document_media_id=media_id, document_mime_type=mime_type,
                            receiving_phone_number_id=phone_number_id,
                        )
    return None

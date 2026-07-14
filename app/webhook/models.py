# pyrefly: ignore [missing-import]
from pydantic import BaseModel


class WhatsAppTextBody(BaseModel):
    body: str


class WhatsAppMessage(BaseModel):
    id: str
    from_: str
    timestamp: str
    type: str
    text: WhatsAppTextBody | None = None

    model_config = {"populate_by_name": True}

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if isinstance(obj, dict) and "from" in obj:
            obj = dict(obj)
            obj["from_"] = obj.pop("from")
        return super().model_validate(obj, *args, **kwargs)


class WhatsAppValue(BaseModel):
    messaging_product: str
    metadata: dict
    contacts: list[dict] | None = None
    messages: list[dict] | None = None
    statuses: list[dict] | None = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: list[WhatsAppChange]


class WebhookPayload(BaseModel):
    object: str
    entry: list[WhatsAppEntry]

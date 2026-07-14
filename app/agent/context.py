from sqlalchemy.orm import Session
from app.db.crud import get_recent_messages
from app.config import settings


def load_conversation_history(db: Session, conversation_id: int) -> list[dict]:
    """
    Load the last N messages and return them in Anthropic messages format.
    Outbound (ai/human_advisor) messages become 'assistant' role.
    Inbound (customer) messages become 'user' role.
    """
    messages = get_recent_messages(db, conversation_id, limit=settings.max_history_messages)
    history = []
    for msg in messages:
        role = "user" if msg.direction == "inbound" else "assistant"
        history.append({"role": role, "content": msg.content})

    # Anthropic requires messages to alternate roles and start with 'user'.
    # Deduplicate consecutive same-role messages by merging them.
    merged: list[dict] = []
    for item in history:
        if merged and merged[-1]["role"] == item["role"]:
            merged[-1]["content"] += "\n" + item["content"]
        else:
            merged.append({"role": item["role"], "content": item["content"]})

    # Must start with 'user' role
    while merged and merged[0]["role"] != "user":
        merged.pop(0)

    return merged

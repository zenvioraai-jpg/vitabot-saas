"""Utilidades del catálogo compartidas."""


def media_marker(kind: str, sku: str, name: str = "") -> str:
    """Marcador que se guarda en el historial del chat para mostrar la vista previa
    del recurso multimedia enviado (foto/video). El panel lo renderiza como miniatura."""
    return f"[[MEDIA|{kind}|{sku}|{name or sku}]]"
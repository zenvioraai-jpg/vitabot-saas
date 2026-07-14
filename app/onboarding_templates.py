"""Plantillas de arranque por tipo de negocio (business_type).

Cada tipo trae: una plantilla de entrenamiento por defecto (para que el bot ya suene
coherente desde el primer mensaje, antes de que la empresa edite nada) y la lista de
campos extra sugeridos para su pestaña de Configuración (Company.extra_config, JSON
libre — la empresa los llena, edita o ignora libremente, igual que hoy se edita el
Entrenamiento de Vita Qualitat)."""

BUSINESS_TYPES = {
    "skincare_salud": "Cuidado de piel / salud",
    "restaurante": "Restaurante",
    "tienda_ropa": "Tienda de ropa",
    "inmobiliaria": "Inmobiliaria",
    "servicios_citas": "Servicios con agenda/citas",
    "otro": "Otro / genérico",
}

# Campos extra sugeridos por rubro: {campo: etiqueta}. Se muestran como inputs
# adicionales en el panel de la empresa; son solo una sugerencia de qué suele
# necesitar ese rubro, no son obligatorios.
EXTRA_FIELDS = {
    "skincare_salud": {
        "protocolos_uso": "Protocolos de uso (antes/durante/después de un tratamiento)",
        "respaldo_medico": "Respaldo médico/registros (INVIMA, dermatólogos, etc.)",
    },
    "restaurante": {
        "horario_atencion": "Horario de atención",
        "domicilios": "¿Maneja domicilios? ¿Zonas y costo?",
        "menu_del_dia": "Menú del día / especialidades",
        "reservas": "¿Se pueden reservar mesas? ¿Cómo?",
    },
    "tienda_ropa": {
        "tallas_disponibles": "Tallas y colores disponibles",
        "cambios_devoluciones": "Política de cambios y devoluciones",
        "guia_tallas": "Guía de tallas",
    },
    "inmobiliaria": {
        "zonas_cobertura": "Zonas / barrios donde opera",
        "tipos_propiedad": "Tipos de propiedad (arriendo, venta, comercial, etc.)",
        "agendar_visitas": "Cómo se agenda una visita",
    },
    "servicios_citas": {
        "duracion_citas": "Duración típica de una cita/servicio",
        "agenda_disponible": "Días y horarios disponibles",
        "politica_cancelacion": "Política de cancelación/reprogramación",
    },
    "otro": {},
}

_GENERIC_INTRO = """CÓMO PRESENTAR EL NEGOCIO (primera impresión)
Preséntate con calidez, sin sonar a call center. Interésate primero por lo que la
persona necesita antes de listar todo el catálogo de una vez.

Interpreta y comprende al cliente AUNQUE escriba con errores, sin tildes, abreviado o
con typos. Deduce lo que quiere decir y responde con normalidad. NUNCA le corrijas la
ortografía ni le pidas que reescriba el mensaje.

Responde siempre en ESPAÑOL NEUTRO (o el idioma en que te escriba el cliente), claro y
accesible, con ortografía y tildes correctas. Evita modismos muy regionales salvo que
este entrenamiento indique lo contrario.
"""

_TEMPLATES = {
    "skincare_salud": _GENERIC_INTRO + """
PRODUCTOS Y CUIDADO
Presenta cada producto por su beneficio para la piel/salud antes que por el precio.
Menciona el precio solo cuando el cliente lo pida. Si el cliente menciona una condición
médica o tratamiento (ej: quimioterapia, alergias, piel sensible), prioriza claridad y
prudencia: recomienda según lo que sepas del producto, pero deja claro que la última
palabra es de su médico.
""",
    "restaurante": _GENERIC_INTRO + """
MENÚ Y PEDIDOS
Ayuda al cliente a decidir qué pedir según lo que busca (rápido, para compartir, algo
específico). Confirma siempre: qué pidió, si es para domicilio o recoger, dirección si
aplica, y el método de pago. Informa el tiempo estimado si lo sabes.
""",
    "tienda_ropa": _GENERIC_INTRO + """
PRODUCTOS Y TALLAS
Pregunta talla/color/preferencias antes de recomendar. Sé clara sobre disponibilidad
(no prometas algo que no está en el catálogo). Confirma siempre el pedido completo
(prenda, talla, color, cantidad) antes de pasar a los datos de envío y pago.
""",
    "inmobiliaria": _GENERIC_INTRO + """
PROPIEDADES Y VISITAS
Pregunta qué busca el cliente (zona, presupuesto, tipo de propiedad) antes de listar
opciones. Para agendar una visita, recopila: propiedad de interés, disponibilidad de
fecha/hora, y datos de contacto.
""",
    "servicios_citas": _GENERIC_INTRO + """
CITAS Y AGENDA
Ayuda a agendar: qué servicio necesita, duración estimada, disponibilidad, y confirma
los datos de contacto. Sé clara sobre política de cancelación si el cliente pregunta.
""",
    "otro": _GENERIC_INTRO,
}


def get_default_training(business_type: str) -> str:
    return _TEMPLATES.get(business_type, _TEMPLATES["otro"])


def get_extra_fields(business_type: str) -> dict:
    return EXTRA_FIELDS.get(business_type, {})
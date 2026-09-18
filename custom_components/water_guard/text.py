"""Alert text. Notifications take no translation keys, so this follows Home
Assistant's language: Bokmål for nb, no and nn, else English."""

TEXT = {
    "en": {
        "leak_title": "Water leak detected",
        "leak_alert": (
            "A leak was detected by {sensors}. Check that the water is shut off. "
            "When it is safe, use Override in Water Guard to open the water again."
        ),
        "leak_closed": (
            "A leak was detected by {sensors}. The water is shut off. When it is safe, "
            "use Override in Water Guard to open the water again."
        ),
        "leak_not_closed": (
            "A leak was detected by {sensors}, but the water could not be shut off: "
            "{valves} did not close. Shut the water off by hand."
        ),
    },
    "nb": {
        "leak_title": "Vannlekkasje oppdaget",
        "leak_alert": (
            "{sensors} har oppdaget en lekkasje. Kontroller at vannet er stengt. "
            "Når det er trygt, bruk Overstyr i Vannvakt for å åpne vannet igjen."
        ),
        "leak_closed": (
            "{sensors} har oppdaget en lekkasje. Vannet er stengt. Når det er trygt, "
            "bruk Overstyr i Vannvakt for å åpne vannet igjen."
        ),
        "leak_not_closed": (
            "{sensors} har oppdaget en lekkasje, men vannet kunne ikke stenges: "
            "{valves} stengte ikke. Steng vannet manuelt."
        ),
    },
}


def language(hass):
    code = (hass.config.language or "en").lower().replace("_", "-").split("-")[0]
    return "nb" if code in {"nb", "no", "nn"} else "en"


def text(hass, key, **values):
    return TEXT[language(hass)][key].format(**values)

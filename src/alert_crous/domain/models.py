from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Logement:
    id: str
    title: str
    link: str
    price: str = "N/A"
    address: str = "N/A"
    surface: str = "N/A"
    occupation: str = "N/A"
    logement_type: str = "N/A"
    image_url: str = ""
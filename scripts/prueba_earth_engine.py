"""Prueba de integración real Earth Engine -> NORA con validaciones."""
import json

from nora_engine.earth_engine import config_desde_entorno, extraer

REGION = {"lat": 4.6097, "lon": -74.0817, "buffer_m": 2000}
VARIABLES = ["precipitacion", "sentinel2", "evi"]


def validar(resultado):
    assert resultado["estado"] == "ok"
    fuentes = resultado["fuentes"]

    for variable in VARIABLES:
        item = fuentes[variable]
        assert item["estado"] == "ok", f"{variable}: sin datos"
        assert item["imagenes"] > 0, f"{variable}: colección vacía"
        assert item["estadistica"], f"{variable}: estadística vacía"

    precipitacion = fuentes["precipitacion"]["estadistica"]["precipitation"]
    assert precipitacion is not None and precipitacion >= 0, "Precipitación inválida"

    reflectancia = fuentes["sentinel2"]["estadistica"]["B4"]
    assert reflectancia is not None and 0 <= reflectancia <= 1.5, "Reflectancia Sentinel-2 fuera de rango"

    evi = fuentes["evi"]["estadistica"]["EVI"]
    assert evi is not None and -1.0 <= evi <= 1.0, "EVI fuera de rango"


if __name__ == "__main__":
    resultado = extraer(
        config_desde_entorno(),
        REGION,
        "2025-01-01",
        "2025-01-08",
        VARIABLES,
    )
    validar(resultado)
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    print("EARTH ENGINE REAL-DATA SMOKE TEST: OK")

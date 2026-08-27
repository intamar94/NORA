"""Prueba mínima de integración Earth Engine -> NORA."""
import json
from nora_engine.earth_engine import config_desde_entorno, extraer

REGION={"lat":4.6097,"lon":-74.0817,"buffer_m":2000}

if __name__ == "__main__":
    resultado=extraer(config_desde_entorno(),REGION,"2025-01-01","2025-01-08",["precipitacion","sentinel2","evi"])
    print(json.dumps(resultado,ensure_ascii=False,indent=2,default=str))

from flask import Flask, jsonify
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuración
BANXICO_TOKEN = os.getenv("BANXICO_API_KEY")
EXCHANGE_KEY = os.getenv("EXCHANGERATE_API_KEY") # Nueva KEY
BANXICO_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

SERIES_BMX = {
    "USD_FIX": "SF43718",            
    "USD_APER_COMPRA": "SF43787",
    "USD_APER_VENTA": "SF43784",
    "USD_LIQ": "SF60653",
    "UDI": "SP68257",
    "EUR": "SF46410",
    "GBP": "SF46407",
    "JPY": "SF46406",
    "CNY": "SF290383"
}

# Monedas seleccionadas por su interés en México
MONEDAS_REGION = ["BRL", "COP", "CLP", "CAD", "CHF"]

def obtener_datos_latam():
    """Consulta solo los valores actuales para evitar el error de Plan Upgrade"""
    if not EXCHANGE_KEY:
        return {}
    
    url_hoy = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_KEY}/latest/USD"
    
    try:
        res = requests.get(url_hoy, timeout=10).json()
        if res.get("result") == "error":
            return {}

        rates = res.get("conversion_rates", {})
        
        # Solo devolvemos el valor actual
        resultado = {}
        for m in MONEDAS_REGION:
            if m in rates:
                resultado[m] = {"valor": round(rates[m], 4)}
        return resultado
    except:
        return {}

@app.route('/tipo-cambio', methods=['GET'])
def obtener_datos():
    headers = {"Bmx-Token": BANXICO_TOKEN, "Accept": "application/json"}
    resultado = {}
    
    # 1. DATOS ACTUALES BANXICO
    ids_str = ",".join(SERIES_BMX.values())
    fecha_segura = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    url_bmx = f"{BANXICO_URL}/{ids_str}/datos/{fecha_segura}/{datetime.today().strftime('%Y-%m-%d')}"
    
    res_bmx = requests.get(url_bmx, headers=headers)
    if res_bmx.status_code == 200:
        series = res_bmx.json().get("bmx", {}).get("series", [])
        for s in series:
            nombre = next((k for k, v in SERIES_BMX.items() if v == s["idSerie"]), s["idSerie"])
            if s.get("datos"):
                ultimo = s["datos"][-1]
                resultado[nombre] = {"valor": float(ultimo["dato"]), "fecha": ultimo["fecha"]}

    # 2. DATOS REGIONALES (Calculados en Python)
    resultado["DIVISAS_REGION"] = obtener_datos_latam()

    # 3. ANÁLISIS TENDENCIA USD_FIX (Tu lógica original simplificada)
    # [Mantener tu lógica de DATO_MAÑANA y CONTEXTO_ANUAL aquí...]
    
    return jsonify(resultado)

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

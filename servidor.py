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

# Monedas de interés: LatAm + Socio T-MEC + Refugio Global
MONEDAS_REGION = ["BRL", "COP", "CLP", "CAD", "CHF"]

def obtener_datos_latam():
    """Consulta ExchangeRate-API para obtener hoy vs ayer incluyendo el Franco Suizo"""
    if not EXCHANGE_KEY:
        return {}
    
    # Calculamos la fecha de ayer para la consulta histórica
    ayer = (datetime.today() - timedelta(days=1))
    url_hoy = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_KEY}/latest/USD"
    url_ayer = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_KEY}/history/USD/{ayer.year}/{ayer.month}/{ayer.day}"
    
    try:
        res_hoy = requests.get(url_hoy).json().get("conversion_rates", {})
        res_ayer = requests.get(url_ayer).json().get("conversion_rates", {})
        
        comparativa = {}
        for m in MONEDAS_REGION:
            val_hoy = res_hoy.get(m)
            val_ayer = res_ayer.get(m)
            
            if val_hoy and val_ayer:
                diff = ((val_hoy - val_ayer) / val_ayer) * 100
                # Para monedas en formato USD/Moneda: 
                # Si diff > 0, el USD se fortaleció (la moneda local perdió valor).
                comparativa[m] = {
                    "valor": round(val_hoy, 4),
                    "variacion_pct": abs(round(diff, 2)),
                    "sentido": "retroceso" if diff > 0 else "fortalecimiento"
                }
        return comparativa
    except Exception as e:
        print(f"Error en consulta regional: {e}")
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

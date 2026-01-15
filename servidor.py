from flask import Flask, jsonify
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuración
BANXICO_TOKEN = os.getenv("BANXICO_API_KEY")
EXCHANGE_KEY = os.getenv("EXCHANGERATE_API_KEY")
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

MONEDAS_REGION = ["MXN", "BRL", "COP", "CLP", "CAD", "CHF"]

def obtener_datos_latam():
    if not EXCHANGE_KEY: return {}
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_KEY}/latest/USD"
    try:
        res = requests.get(url, timeout=10).json()
        rates = res.get("conversion_rates", {})
        return {m: {"valor": round(rates[m], 4)} for m in MONEDAS_REGION if m in rates}
    except: return {}

@app.route('/tipo-cambio', methods=['GET'])
def obtener_datos():
    headers = {"Bmx-Token": BANXICO_TOKEN, "Accept": "application/json"}
    resultado = {}
    hoy_dt = datetime.today()
    hoy_str = hoy_dt.strftime("%Y-%m-%d")
    
    # 1. VALORES ACTUALES BANXICO
    ids_str = ",".join(SERIES_BMX.values())
    fecha_segura = (hoy_dt - timedelta(days=5)).strftime("%Y-%m-%d")
    url_bmx = f"{BANXICO_URL}/{ids_str}/datos/{fecha_segura}/{hoy_str}"
    
    res_bmx = requests.get(url_bmx, headers=headers)
    if res_bmx.status_code == 200:
        series = res_bmx.json().get("bmx", {}).get("series", [])
        for s in series:
            nombre = next((k for k, v in SERIES_BMX.items() if v == s["idSerie"]), s["idSerie"])
            if s.get("datos"):
                ultimo = s["datos"][-1]
                resultado[nombre] = {"valor": float(ultimo["dato"]), "fecha": ultimo["fecha"]}

    # 2. DIVISAS INTERNACIONALES (NUEVAS)
    resultado["DIVISAS_REGION"] = obtener_datos_latam()

    # 3. RECUPERANDO: DATO_MAÑANA (HISTORIAL 5 DÍAS)
    url_hist = f"{BANXICO_URL}/{SERIES_BMX['USD_FIX']}/datos/{(hoy_dt - timedelta(days=12)).strftime('%Y-%m-%d')}/{hoy_str}"
    res_hist = requests.get(url_hist, headers=headers)
    if res_hist.status_code == 200:
        datos_raw = res_hist.json().get("bmx", {}).get("series", [{}])[0].get("datos", [])
        datos_limpios = [d for d in datos_raw if d["dato"] not in ["N/E", ""]]
        ultimos_5 = datos_limpios[-5:]
        precios = [float(d["dato"]) for d in ultimos_5]
        
        resultado["DATO_MAÑANA"] = {
            "valor_actual": precios[-1],
            "historial": precios,
            "fecha_inicio_semana": ultimos_5[0]["fecha"],
            "tendencia": "sube" if precios[-1] > precios[-2] else "baja"
        }

    # 4. RECUPERANDO: CONTEXTO_ANUAL
    hace_un_anio = hoy_dt - timedelta(days=365)
    url_anio = f"{BANXICO_URL}/{SERIES_BMX['USD_FIX']}/datos/{(hace_un_anio - timedelta(days=7)).strftime('%Y-%m-%d')}/{hace_un_anio.strftime('%Y-%m-%d')}"
    res_anio = requests.get(url_anio, headers=headers)
    if res_anio.status_code == 200:
        datos_anio = res_anio.json().get("bmx", {}).get("series", [{}])[0].get("datos", [])
        if datos_anio:
            val_y = float(datos_anio[-1]["dato"])
            val_hoy = resultado.get("USD_FIX", {}).get("valor", 0)
            variacion = ((val_hoy - val_y) / val_y) * 100
            resultado["CONTEXTO_ANUAL"] = {
                "valor_hace_un_anio": val_y,
                "variacion_anual": f"{round(variacion, 2)}%"
            }

# --- LÓGICA DE MONITOREO (Insertar antes del return) ---
    precio_actual = float(resultado.get("DIVISAS_REGION", {}).get("MXN", {}).get("valor", 0))
    precio_ayer = float(resultado.get("USD_FIX", {}).get("valor", 0))

    diferencia_centavos = round((precio_actual - precio_ayer) * 100, 2)
    
    # Creamos el objeto MONITOR
    resultado["MONITOR"] = {
        "diferencia_abs_centavos": abs(diferencia_centavos),
        "variacion_real_centavos": diferencia_centavos,
        "alerta_activa": abs(diferencia_centavos) >= 10.0, # Umbral de 10 centavos
        "sentido": "DEPRECIACIÓN" if diferencia_centavos > 0 else "APRECIACIÓN",
        "emoji": "🚨" if diferencia_centavos > 0 else "🚀"
    }

    return jsonify(resultado)
  
 
if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

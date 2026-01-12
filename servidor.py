from flask import Flask, jsonify
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)

API_TOKEN = os.getenv("BANXICO_API_KEY")
BANXICO_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

# Diccionario de series actualizado
SERIES = {
    "USD_FIX": "SF43718",            # Oficial (Mañana/Apertura)
    "USD_CIERRE": "SF343410",        # Cierre de Jornada (Tarde)
    "USD_COMPRA_MERCADO": "SF43717", # Interbancario Compra
    "USD_VENTA_MERCADO": "SF43719",  # Interbancario Venta
    "USD_HIST_1954": "SF63528",      # Histórico de largo plazo
    "UDI": "SP68257",
    "EUR": "SF46410",
    "GBP": "SF46407",
    "JPY": "SF46406",
    "CNY": "SF290383"
}

def obtener_fechas():
    hoy = datetime.today()
    hace_365 = hoy - timedelta(days=365)
    return {
        "hoy": hoy.strftime("%Y-%m-%d"),
        "inicio_anio": (hace_365 - timedelta(days=5)).strftime("%Y-%m-%d"),
        "fin_anio": hace_365.strftime("%Y-%m-%d")
    }

@app.route('/tipo-cambio', methods=['GET'])
def obtener_datos():
    headers = {"Bmx-Token": API_TOKEN, "Accept": "application/json"}
    resultado = {}
    f = obtener_fechas()

    # 1. Consulta Masiva (Datos Oportunos)
    ids_series = ",".join(SERIES.values())
    res_op = requests.get(f"{BANXICO_URL}/{ids_series}/datos/oportuno", headers=headers)
    
    if res_op.status_code == 200:
        series_lista = res_op.json().get("bmx", {}).get("series", [])
        for s in series_lista:
            nombre = next((k for k, v in SERIES.items() if v == s["idSerie"]), s["idSerie"])
            if s.get("datos"):
                d = s["datos"][0]
                resultado[nombre] = {
                    "valor": float(d["dato"]),
                    "fecha": d["fecha"]
                }

    # 2. Análisis Diario (Variación respecto al día anterior para el FIX)
    # Pedimos los últimos 5 días para asegurar tener el dato de ayer aunque sea lunes
    url_hist = f"{BANXICO_URL}/{SERIES['USD_FIX']}/datos/{(datetime.today() - timedelta(days=5)).strftime('%Y-%m-%d')}/{f['hoy']}"
    res_hist = requests.get(url_hist, headers=headers)
    
    if res_hist.status_code == 200:
        datos = [d for d in res_hist.json().get("bmx", {}).get("series", [])[0].get("datos", []) if d["dato"] not in ["N/E", ""]]
        if len(datos) >= 2:
            actual, anterior = float(datos[-1]["dato"]), float(datos[-2]["dato"])
            dif = actual - anterior
            resultado["DATO_MAÑANA"] = {
                "valor_actual": actual,
                "cambio": round(dif, 4),
                "pct": f"{round((dif/anterior)*100, 2)}%",
                "tendencia": "sube" if dif > 0 else "baja"
            }

    # 3. Comparativa Anual (Para dar profundidad a las notas)
    url_anio = f"{BANXICO_URL}/{SERIES['USD_FIX']}/datos/{f['inicio_anio']}/{f['fin_anio']}"
    res_anio = requests.get(url_anio, headers=headers)
    if res_anio.status_code == 200:
        datos_y = res_anio.json().get("bmx", {}).get("series", [])[0].get("datos", [])
        if datos_y:
            val_y = float(datos_y[-1]["dato"])
            resultado["CONTEXTO_ANUAL"] = {
                "valor_hace_un_anio": val_y,
                "variacion_anual": f"{round(((resultado['USD_FIX']['valor'] - val_y)/val_y)*100, 2)}%"
            }

    return jsonify(resultado)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))

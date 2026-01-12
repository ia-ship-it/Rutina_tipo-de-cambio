from flask import Flask, jsonify
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Token de acceso de Banxico
API_TOKEN = os.getenv("BANXICO_API_KEY")

# Series de Banxico con los códigos corregidos
SERIES = {
    "USD": "SF43718",  # Dólar estadounidense (FIX)
    "EUR": "SF46410",  # Euro
    "GBP": "SF46407",  # Libra esterlina
    "CNY": "SF290383",  # Yuan chino
    "JPY": "SF46406"   # Yen japonés
}

# Función para obtener la fecha de hoy y la de hace 20 días hábiles
def obtener_fechas():
    hoy = datetime.today()
    hace_20_dias = hoy - timedelta(days=30)  # Consideramos 30 días atrás para asegurarnos de capturar 20 hábiles
    return hoy.strftime("%Y-%m-%d"), hace_20_dias.strftime("%Y-%m-%d")

@app.route('/')
def home():
    return "¡El servidor está funcionando correctamente! Usa /tipo-cambio para obtener datos."

@app.route('/tipo-cambio', methods=['GET'])
def obtener_tipo_cambio():
    headers = {"Bmx-Token": API_TOKEN}
    resultado = {}

    # Obtener las fechas necesarias
    fecha_hoy, fecha_inicio = obtener_fechas()

    # 1️⃣ Consulta del USD (últimos 20 días hábiles)
    url_usd_hist = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{SERIES['USD']}/datos/{fecha_inicio}/{fecha_hoy}"
    response_usd_hist = requests.get(url_usd_hist, headers=headers)

    if response_usd_hist.status_code == 200:
        data_usd_hist = response_usd_hist.json()
        serie_usd_hist = data_usd_hist.get("bmx", {}).get("series", [])[0]
        historial_usd = serie_usd_hist.get("datos", [])

        # Convertimos los datos en formato JSON y aseguramos que haya datos disponibles
        if historial_usd:
            resultado["USD_HIST"] = [
                {"fecha": item["fecha"], "dato": float(item["dato"])}
                for item in historial_usd if item["dato"] not in ["N/E", ""]
            ]

            # 2️⃣ Obtener el USD del último día hábil (el penúltimo dato en la lista)
            if len(resultado["USD_HIST"]) > 1:
                resultado["USD_YESTERDAY"] = resultado["USD_HIST"][-2]

    # 3️⃣ Consulta del USD (hoy)
    url_usd_today = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{SERIES['USD']}/datos/oportuno"
    response_usd_today = requests.get(url_usd_today, headers=headers)

    if response_usd_today.status_code == 200:
        data_usd_today = response_usd_today.json()
        serie_usd_today = data_usd_today.get("bmx", {}).get("series", [])[0]
        if serie_usd_today.get("datos"):
            dato_usd_today = serie_usd_today.get("datos")[0]
            resultado["USD_TODAY"] = {
                "fecha": dato_usd_today["fecha"],
                "dato": float(dato_usd_today["dato"])
            }

    # 4️⃣ Consulta de otras divisas (solo la más reciente)
    url_otras = f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/{','.join(SERIES.values())}/datos/oportuno"
    response_otras = requests.get(url_otras, headers=headers)

    if response_otras.status_code == 200:
        data_otras = response_otras.json()
        series_otras = data_otras.get("bmx", {}).get("series", [])

        for serie in series_otras:
            nombre_divisa = next((key for key, value in SERIES.items() if value == serie.get("idSerie")), "Desconocido")
            if serie.get("datos"):
                valor = serie.get("datos")[0].get("dato")
                fecha = serie.get("datos")[0].get("fecha")

                resultado[nombre_divisa] = {
                    "fecha": fecha,
                    "dato": float(valor) if valor not in ["N/E", ""] else None
                }

    return jsonify(resultado)

if __name__ == '__main__':
    port = int(os.getenv("PORT", "8080"))
    app.run(host='0.0.0.0', port=port)


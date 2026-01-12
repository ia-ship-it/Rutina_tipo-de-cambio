from flask import Flask, jsonify
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuración de Acceso
API_TOKEN = os.getenv("BANXICO_API_KEY")
BANXICO_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

# Catálogo completo de series para tus notas
SERIES = {
    "USD_FIX": "SF43718",            # Dólar FIX (Oficial)
    "USD_VENTA_PROM": "SF46543",    # Dólar Ventanilla (Venta)
    "USD_COMPRA_PROM": "SF46544",   # Dólar Ventanilla (Compra)
    "UDI": "SP68257",               # Unidades de Inversión
    "EUR": "SF46410",               # Euro
    "GBP": "SF46407",               # Libra Esterlina
    "JPY": "SF46406",               # Yen Japonés
    "CNY": "SF290383"               # Yuan Chino
}

def obtener_fechas():
    hoy = datetime.today()
    hace_30_dias = hoy - timedelta(days=30)
    hace_un_anio = hoy - timedelta(days=365)
    return {
        "hoy": hoy.strftime("%Y-%m-%d"),
        "inicio_hist": hace_30_dias.strftime("%Y-%m-%d"),
        "hace_un_anio_rango": (hace_un_anio - timedelta(days=5)).strftime("%Y-%m-%d"),
        "hace_un_anio_fin": hace_un_anio.strftime("%Y-%m-%d")
    }

@app.route('/tipo-cambio', methods=['GET'])
def obtener_datos_completos():
    headers = {"Bmx-Token": API_TOKEN, "Accept": "application/json"}
    resultado = {}
    f = obtener_fechas()

    # 1. OBTENER DATOS ACTUALES (Todas las divisas + UDI + Ventanilla)
    ids_todas = ",".join(SERIES.values())
    url_op = f"{BANXICO_URL}/{ids_todas}/datos/oportuno"
    
    res_op = requests.get(url_op, headers=headers)
    if res_op.status_code == 200:
        series_lista = res_op.json().get("bmx", {}).get("series", [])
        for s in series_lista:
            nombre = next((k for k, v in SERIES.items() if v == s["idSerie"]), s["idSerie"])
            if s.get("datos"):
                d = s["datos"][0]
                resultado[nombre] = {
                    "valor": float(d["dato"]) if d["dato"] not in ["N/E", ""] else None,
                    "fecha": d["fecha"]
                }

    # 2. ANÁLISIS DE VARIACIÓN DIARIA (Usando historial de 30 días para USD FIX)
    url_hist = f"{BANXICO_URL}/{SERIES['USD_FIX']}/datos/{f['inicio_hist']}/{f['hoy']}"
    res_hist = requests.get(url_hist, headers=headers)
    
    if res_hist.status_code == 200:
        datos_usd = [d for d in res_hist.json().get("bmx", {}).get("series", [])[0].get("datos", []) if d["dato"] not in ["N/E", ""]]
        
        if len(datos_usd) >= 2:
            hoy_v, ayer_v = float(datos_usd[-1]["dato"]), float(datos_usd[-2]["dato"])
            dif_diaria = hoy_v - ayer_v
            resultado["ANALISIS_DIARIO"] = {
                "dif_nominal": round(dif_diaria, 4),
                "dif_porcentual": f"{round((dif_diaria/ayer_v)*100, 2)}%",
                "tendencia": "sube" if dif_diaria > 0 else "baja"
            }

    # 3. COMPARATIVA ANUAL (Dólar hoy vs hace un año)
    url_anio = f"{BANXICO_URL}/{SERIES['USD_FIX']}/datos/{f['hace_un_anio_rango']}/{f['hace_un_anio_fin']}"
    res_anio = requests.get(url_anio, headers=headers)
    
    if res_anio.status_code == 200:
        datos_anio = res_anio.json().get("bmx", {}).get("series", [])[0].get("datos", [])
        if datos_anio and "USD_FIX" in resultado:
            val_pasado = float(datos_anio[-1]["dato"])
            val_actual = resultado["USD_FIX"]["valor"]
            dif_anual = val_actual - val_pasado
            resultado["ANALISIS_ANUAL"] = {
                "valor_hace_un_anio": val_pasado,
                "variacion_anual": f"{round((dif_anual/val_pasado)*100, 2)}%"
            }

    return jsonify(resultado)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 8080)))

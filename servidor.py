from flask import Flask, jsonify
import requests
import os
from datetime import datetime, timedelta

app = Flask(__name__)

API_TOKEN = os.getenv("BANXICO_API_KEY")
BANXICO_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

# Diccionario de series actualizado con los IDs técnicos de tu documento
SERIES = {
    "USD_FIX": "SF43718",            
    "USD_APER_COMPRA": "SF43787",    # Apertura Real 9:00 AM
    "USD_APER_VENTA": "SF43784",     # Apertura Real 9:00 AM
    "USD_CIERRE": "SF343410",        # Cierre de Jornada 14:10 PM
    "USD_LIQ": "SF60653",            # Para solventar obligaciones (DOF)
    "USD_HIST_1954": "SF63528",
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
    
    # IMPORTANTE: Definir la cadena de IDs antes de la consulta
    ids_series = ",".join(SERIES.values())

    # 1. Consulta Masiva (Últimos 3 días para garantizar datos en apertura)
    fecha_inicio_segura = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    url_op = f"{BANXICO_URL}/{ids_series}/datos/{fecha_inicio_segura}/{f['hoy']}"
    res_op = requests.get(url_op, headers=headers)

    if res_op.status_code == 200:
        series_lista = res_op.json().get("bmx", {}).get("series", [])
        for s in series_lista: # Corregida la indentación aquí
            nombre = next((k for k, v in SERIES.items() if v == s["idSerie"]), s["idSerie"])
            if s.get("datos"):
                ultimo = s["datos"][-1]
                resultado[nombre] = {
                    "valor": float(ultimo["dato"]),
                    "fecha": ultimo["fecha"]
                }

    # 2. Análisis Diario (Variación respecto al día anterior para el FIX)
    url_hist = f"{BANXICO_URL}/{SERIES['USD_FIX']}/datos/{(datetime.today() - timedelta(days=5)).strftime('%Y-%m-%d')}/{f['hoy']}"
    res_hist = requests.get(url_hist, headers=headers)
    
    if res_hist.status_code == 200:
        series = res_hist.json().get("bmx", {}).get("series", [])
        if series and series[0].get("datos"):
            datos = [d for d in series[0]["datos"] if d["dato"] not in ["N/E", ""]]
            if len(datos) >= 2:
                actual, anterior = float(datos[-1]["dato"]), float(datos[-2]["dato"])
                dif = actual - anterior
                resultado["DATO_MAÑANA"] = {
                    "valor_actual": actual,
                    "cambio": round(dif, 4),
                    "pct": f"{round((dif/anterior)*100, 2)}%",
                    "tendencia": "sube" if dif > 0 else "baja"
                }

    # 3. Comparativa Anual
    url_anio = f"{BANXICO_URL}/{SERIES['USD_FIX']}/datos/{f['inicio_anio']}/{f['fin_anio']}"
    res_anio = requests.get(url_anio, headers=headers)
    if res_anio.status_code == 200:
        series_y = res_anio.json().get("bmx", {}).get("series", [])
        if series_y and series_y[0].get("datos"):
            datos_y = series_y[0]["datos"]
            val_y = float(datos_y[-1]["dato"])
            # Usamos el FIX obtenido arriba para la comparativa
            val_actual = resultado.get("USD_FIX", {}).get("valor", 0)
            if val_actual > 0:
                resultado["CONTEXTO_ANUAL"] = {
                    "valor_hace_un_anio": val_y,
                    "variacion_anual": f"{round(((val_actual - val_y)/val_y)*100, 2)}%"
                }

    return jsonify(resultado)

if __name__ == '__main__':
    # Puerto dinámico para Railway
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

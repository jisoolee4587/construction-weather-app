from flask import Flask, render_template, request
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

API_KEY = "a00a90d02bc10b21c47605174b7013dc"
CITY = "Seoul"

JOB_OPTIONS = {
    "concrete": "콘크리트 타설",
    "painting": "도장 작업",
    "steel": "고소 작업",
    "waterproof": "방수 작업",
    "tile": "조적/타일 작업"
}

def check_job_feasibility(job_type, temp, humidity, wind, rain):
    if job_type == "concrete":
        if temp < 5 or temp > 30 or wind >= 7:
            return "❌ 타설 금지"
    elif job_type == "painting":
        if humidity > 85 or rain > 0:
            return "❌ 도장 금지"
    elif job_type == "steel":
        if wind >= 10:
            return "❌ 고소작업 금지"
    elif job_type == "waterproof":
        if rain > 0:
            return "❌ 방수 금지"
    elif job_type == "tile":
        if temp < 0 or rain > 0:
            return "❌ 조적작업 금지"
    return "✅ 작업 가능"

@app.route("/", methods=["GET", "POST"])
def index():
    selected_job = request.form.get("job_type", "concrete")
    filter_value = request.form.get("filter", None)
    graph_items = request.form.getlist("graph_items")
    start_str = request.form.get("start_date")
    end_str = request.form.get("end_date")

    today = datetime.now(pytz.timezone('Asia/Seoul')).date()
    start_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
    end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else today + timedelta(days=4)

    if not graph_items:
        graph_items = ["temp", "humidity", "wind", "rain"]

    job_name = JOB_OPTIONS[selected_job]

    url = f"https://api.openweathermap.org/data/2.5/forecast?q={CITY}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    data = response.json()
    forecast_list = data.get('list', [])

    times, temps, humidities, winds, rains, judgments = [], [], [], [], [], []

    for forecast in forecast_list:
        dt = datetime.utcfromtimestamp(forecast['dt']).replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Seoul'))

        if not (start_date <= dt.date() <= end_date):
            continue

        temp = forecast['main']['temp']
        humidity = forecast['main']['humidity']
        wind = forecast['wind']['speed']
        rain = forecast.get('rain', {}).get('3h', 0)
        status = check_job_feasibility(selected_job, temp, humidity, wind, rain)

        times.append(dt.strftime('%m-%d %H시'))
        temps.append(temp)
        humidities.append(humidity)
        winds.append(wind)
        rains.append(rain)
        judgments.append(status)

    df = pd.DataFrame({
        "시간": times,
        "기온 (°C)": temps,
        "습도 (%)": humidities,
        "풍속 (m/s)": winds,
        "강수량 (mm)": rains,
        "작업 판단": judgments
    })

    # 테이블에만 필터 적용 (그래프는 항상 전체 데이터 사용)
    df_filtered = df.copy()
    if filter_value == "ok":
        df_filtered = df[df["작업 판단"].str.contains("✅")]
    elif filter_value == "warning":
        df_filtered = df[df["작업 판단"].str.contains("❌")]

    return render_template("index.html",
                           df=df_filtered.values.tolist(),
                           columns=df.columns.tolist(),
                           job_name=job_name,
                           job_key=selected_job,
                           job_options=JOB_OPTIONS,
                           labels=df["시간"].tolist(),
                           temps=df["기온 (°C)"].tolist(),
                           humidities=df["습도 (%)"].tolist(),
                           winds=df["풍속 (m/s)"].tolist(),
                           rains=df["강수량 (mm)"].tolist(),
                           judgments=df["작업 판단"].tolist(),
                           filter=filter_value,
                           graph_items=graph_items,
                           start_date=start_date.isoformat(),
                           end_date=end_date.isoformat()
                           )

if __name__ == "__main__":
    app.run(debug=True)








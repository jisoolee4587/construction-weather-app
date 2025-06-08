from flask import Flask, render_template, request
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

API_KEY = os.getenv("API_KEY")  # .env에서 불러오기
CITY = "Seoul"

JOB_OPTIONS = {
    "all": "전체 작업",
    "concrete": "콘크리트 타설",
    "painting": "도장 작업",
    "steel": "고소 작업",
    "waterproof": "방수 작업",
    "tile": "조적/타일 작업"
}

def check_job_feasibility(job_type, temp, humidity, wind, rain, avg_temp=None, rain_rate=None, welding_method=None, preheated=False):
    # 콘크리트 타설 기준
    if job_type == "concrete":
        if avg_temp is not None and avg_temp <= 4:
            return "❌ 타설 금지 (일평균 기온 ≤ 4℃)"
        if rain_rate is not None and rain_rate > 3:
            return "❌ 타설 금지 (강우량 > 3mm/hr)"
        if temp > 35:
            return "❌ 타설 금지 (콘크리트 온도 > 35℃)"
        return "✅ 타설 가능"

    # 도장 작업 기준
    elif job_type == "painting":
        if temp < 5 or humidity > 85 or rain > 0:
            return "❌ 도장 금지 (기온 < 5℃, 습도 > 85%, 강우 시)"
        return "✅ 도장 가능"

    # 용접 기준
    elif job_type == "welding":
        if temp < 10:
            return "❌ 용접 금지 (기온 < 10℃)"
        if wind >= 5:
            return "❌ 방풍막 필요 (풍속 ≥ 5m/s)"
        if welding_method == "TIG" and wind >= 2:
            return "❌ TIG 용접 금지 (풍속 ≥ 2m/s)"
        if rain > 0 or humidity > 90:
            return "❌ 용접 금지 (비·높은 습도)"
        return "✅ 용접 가능"

    # 타일/조적 시공 기준
    elif job_type == "tile":
        if temp < 5:
            return "❌ 타일 시공 금지 (기온 < 5℃)"
        if not (18 <= temp <= 22):
            return "⚠ 접착제 적정 온도권 아님 (18~22℃ 권장)"
        return "✅ 타일 시공 가능"

    # 형틀(거푸집) 설치/해체 기준
    elif job_type == "formwork":
        if wind >= 10:
            return "❌ 형틀 작업 금지 (풍속 ≥ 10m/s)"
        if rain > 0:
            return "⚠ 형틀 습기 주의 (강우 시 안전 점검 필수)"
        if temp <= 5:
            return "⚠ 형틀 작업 저온 주의 (기온 ≤ 5℃)"
        return "✅ 형틀 작업 가능"

    # 고소작업 기준
    elif job_type == "steel":
        if wind >= 10:
            return "❌ 고소작업 금지 (풍속 ≥ 10m/s)"
        return "✅ 고소작업 가능"

    # 방수 작업 기준
    elif job_type == "waterproof":
        if rain > 0 or humidity > 85:
            return "❌ 방수 금지 (강우 또는 습도 > 85%)"
        return "✅ 방수 가능"

    # 기본값
    return "✅ 작업 가능"


@app.route("/", methods=["GET", "POST"])
def index():
    selected_job = request.form.get("job_type", "concrete")
    filter_value = request.form.get("filter", None)
    graph_items = request.form.getlist("graph_items")
    start_str = request.form.get("start_date")
    end_str = request.form.get("end_date")

    lat = request.form.get("lat")
    lon = request.form.get("lon")

    today = datetime.now(pytz.timezone('Asia/Seoul')).date()
    start_date = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
    end_date = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else today + timedelta(days=4)

    if not graph_items:
        graph_items = ["temp", "humidity", "wind", "rain"]

    job_name = JOB_OPTIONS[selected_job]

    if lat and lon:
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    else:
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

        # ✅ 전체 작업일 경우: 모든 작업의 판단 결과를 리스트로 합침
        if selected_job == "all":
            status_list = []
            for job in JOB_OPTIONS:
                if job == "all":
                    continue  # '전체'는 건너뛰기
                result = check_job_feasibility(job, temp, humidity, wind, rain)
                status_list.append(f"{JOB_OPTIONS[job]}: {result}")
            status = " / ".join(status_list)
        else:
            # 개별 작업일 경우 기존처럼 판단
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


# print("API KEY:", API_KEY)
# print("API 요청 주소:", url)
# print("API 응답 상태:", response.status_code)
# print("응답 내용:", data)







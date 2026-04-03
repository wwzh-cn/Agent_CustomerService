import json
import requests

key = "f2f13fe4721c1babe351a75e005e6de2"
city_code = "430000"

response = requests.get("https://restapi.amap.com/v3/weather/weatherInfo?key=" + key + "&city=" + city_code)
text = response.text
result = json.loads(text)
need = result["lives"][0]

print("您查询的" + need["province"] + need["city"] + "在" + need["reporttime"] + "的天气为" + need["weather"] + "，温度为" + need["temperature_float"] + "，" + need["winddirection"] + "风" + need["windpower"] +"级。")

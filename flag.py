import os
import requests
from PIL import Image
from io import BytesIO
import zipfile

# 国家映射
country_to_iso = {
    "Russia": "ru", "Ukraine": "ua", "Kazakhstan": "kz", "Lithuania": "lt",
    "Denmark": "dk", "France": "fr", "Sweden": "se", "United Kingdom": "gb",
    "Estonia": "ee", "Finland": "fi", "Poland": "pl", "Bosnia and Herzegovina": "ba",
    "Turkey": "tr", "Israel": "il", "Latvia": "lv", "Germany": "de",
    "Slovakia": "sk", "Czech Republic": "cz", "Hungary": "hu", "Norway": "no",
    "Serbia": "rs", "Bulgaria": "bg", "Spain": "es", "Romania": "ro",
    "United States": "us", "Canada": "ca",
    "Brazil": "br", "Argentina": "ar",
    "Australia": "au", "China": "cn", "Indonesia": "id",
    "Malaysia": "my", "Mongolia": "mn"
}

# 创建保存国旗的文件夹
os.makedirs("flags", exist_ok=True)

# 下载并缩放函数
def download_and_resize(country_name, iso_code):
    url = f"https://flagcdn.com/64x48/{iso_code}.png"  
    try:
        response = requests.get(url)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            img = img.resize((28, 21), Image.LANCZOS)
            filename = f"{country_name.replace(' ', '_')}.png"
            filepath = os.path.join("flags", filename)
            img.save(filepath)
            print(f"{country_name} saved as {filename}")
        else:
            print(f" {country_name}: HTTP {response.status_code}")
    except Exception as e:
        print(f" Error downloading {country_name}: {e}")

# 下载所有国旗
for country, code in country_to_iso.items():
    download_and_resize(country, code)

# 打包成 zip 
def zip_flags():
    with zipfile.ZipFile("flags_28x21.zip", "w") as zipf:
        for filename in os.listdir("flags"):
            path = os.path.join("flags", filename)
            zipf.write(path, arcname=filename)
    print("\n All flags zipped as flags_28x21.zip")

zip_flags()

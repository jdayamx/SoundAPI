import subprocess
import sys
import os
import platform
import shutil
import argparse

# =========================================================
# === AUTOSTART (Windows Startup .bat) ====================
# =========================================================
APP_NAME = "SoundAPI"
SCRIPT_PATH = os.path.abspath(__file__)
PYTHON_PATH = sys.executable

def get_startup_bat():
    startup = os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
    )
    return os.path.join(startup, f"{APP_NAME}.bat")

def enable_autostart():
    bat = get_startup_bat()
    with open(bat, "w", encoding="utf-8") as f:
        f.write(f'"{PYTHON_PATH}" "{SCRIPT_PATH}"\n')
    print("✔ Автозапуск УВІМКНЕНО (Windows Startup)")

def disable_autostart():
    bat = get_startup_bat()
    if os.path.exists(bat):
        os.remove(bat)
        print("✔ Автозапуск ВИМКНЕНО")
    else:
        print("ℹ Автозапуск вже вимкнений")

def handle_autostart_args():
    if platform.system() != "Windows":
        return

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--autostart", choices=["on", "off"])
    args, _ = parser.parse_known_args()

    if args.autostart == "on":
        enable_autostart()
        sys.exit(0)
    elif args.autostart == "off":
        disable_autostart()
        sys.exit(0)

# ⬇ ОБРОБЛЯЄМО АРГУМЕНТИ ДО ВСЬОГО ІНШОГО
handle_autostart_args()
# =========================================================
import subprocess
import sys
import os
import platform
import shutil

def install_requirements():
    # 1. ПЕРЕВІРКА ТА ВСТАНОВЛЕННЯ СИСТЕМНИХ ЗАЛЕЖНОСТЕЙ (FFMPEG)
    if platform.system() == "Windows":
        if not shutil.which("ffmpeg"):
            print("FFmpeg не знайдено. Спроба встановлення через winget...")
            try:
                # Встановлюємо ffmpeg через winget
                subprocess.check_call(["winget", "install", "--id", "Gyan.FFmpeg", "--silent"])
                print("FFmpeg встановлено. Налаштовую шляхи...")
                
                # Додаємо стандартний шлях winget до PATH поточної сесії, 
                # щоб не перезавантажувати скрипт
                winget_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1-full_build\bin")
                if os.path.exists(winget_path):
                    os.environ["PATH"] += os.pathpathsep + winget_path
            except Exception as e:
                print(f"Не вдалося встановити FFmpeg автоматично: {e}")
                print("Будь ласка, встановіть його вручну: winget install ffmpeg")
    
    # 2. ПЕРЕВІРКА ТА ВСТАНОВЛЕННЯ PYTHON МОДУЛІВ
    requirements = {
        "fastapi[all]": "fastapi",
        "uvicorn": "uvicorn",
        "sounddevice": "sounddevice",
        "pydub": "pydub",
        "numpy": "numpy",
        "python-jose[cryptography]": "jose",
        "httpx": "httpx",
        "python-multipart": "multipart",
        "audioop-lts": "audioop"
    }
    
    for package, import_name in requirements.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"Встановлення модуля {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--user"])
            except subprocess.CalledProcessError as e:
                print(f"Помилка встановлення {package}: {e}")

# Викликаємо встановлення
install_requirements()

# Фікс для Python 3.13 (як ми обговорювали раніше)
try:
    import audioop
except ImportError:
    import audioop_lts as audioop
    sys.modules["audioop"] = audioop

import sounddevice as sd
from pydub import AudioSegment
import numpy as np

# --- ОСНОВНИЙ ІМПОРТ ПІСЛЯ ВСТАНОВЛЕННЯ ---
import io
import numpy as np
import sounddevice as sd
import httpx
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from pydantic import BaseModel
from pydub import AudioSegment
from datetime import datetime, timedelta
import threading

# --- НАЛАШТУВАННЯ ТА БЕЗПЕКА ---
SECRET_KEY = "SOUND_API_SECRET_2026"
ALGORITHM = "HS256"
USER_DB = {"admin": "password123"}

active_streams = {}
app = FastAPI(title="SoundAPI 2026")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth")

# --- МОДЕЛІ ---
class PlayRequest(BaseModel):
    device_id: int
    url: str

# --- ЛОГІКА JWT ---
def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(hours=1)
    return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

async def check_auth(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Невалідний токен")

# --- ЕНДПОЇНТИ ---

@app.post("/api/auth")
async def auth(form_data: OAuth2PasswordRequestForm = Depends()):
    if USER_DB.get(form_data.username) == form_data.password:
        return {"access_token": create_token({"sub": form_data.username}), "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Невірний логін або пароль")

@app.get("/api/list")
async def list_devices(user: str = Depends(check_auth)):
    try:
        # Отримуємо всі пристрої
        devices = sd.query_devices()
        # Отримуємо ID пристрою відтворення за замовчуванням
        default_device_id = sd.default.device[1] # [input, output]
        
        active_devices = []
        for i, d in enumerate(devices):
            # Критерії активного пристрою відтворення:
            # 1. Має вихідні канали (max_output_channels > 0)
            # 2. Не є віртуальним "порожнім" драйвером (назва не містить 'Mapper' або 'Primary')
            if d['max_output_channels'] > 0:
                is_default = (i == default_device_id)
                
                active_devices.append({
                    "id": i,
                    "name": d['name'],
                    "channels": d['max_output_channels'],
                    "samplerate": d['default_samplerate'],
                    "is_default": is_default,
                    "hostapi": d['hostapi']
                })
        
        # Сортуємо: спочатку пристрій за замовчуванням
        active_devices.sort(key=lambda x: x['is_default'], reverse=True)
        
        return active_devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не вдалося отримати список пристроїв: {str(e)}")

class PlayRequest(BaseModel):
    device_id: int
    url: str
    volume: float = 1.0  # Гучність за замовчуванням (1.0 = 100%)

@app.post("/api/play")
async def play(req: PlayRequest, user: str = Depends(check_auth)):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(req.url, timeout=15.0)

        audio = AudioSegment.from_file(io.BytesIO(res.content))

        raw = np.array(audio.get_array_of_samples(), dtype=np.float32)
        raw /= np.iinfo(audio.array_type).max

        channels = audio.channels

        if channels == 1:
            samples = raw[:, np.newaxis]   # ⬅ ЖОРСТКО робимо (N,1)
        else:
            samples = raw.reshape((-1, channels))

        def callback(outdata, frames, time, status):
            nonlocal samples

            if status:
                print(status)

            chunk = samples[:frames]
            samples = samples[frames:]

            # ⬇⬇⬇ АВАРІЙНИЙ ЗАХИСТ ⬇⬇⬇
            if chunk.ndim == 1:
                chunk = chunk[:, np.newaxis]

            if len(chunk) < frames:
                outdata[:len(chunk), :] = chunk
                outdata[len(chunk):, :] = 0
                raise sd.CallbackStop()
            else:
                outdata[:, :] = chunk

        stream = sd.OutputStream(
            samplerate=audio.frame_rate,
            device=req.device_id,
            channels=channels,
            dtype='float32',
            callback=callback
        )

        active_streams[req.device_id] = stream
        stream.start()

        return {
            "status": "playing",
            "volume": volume,
            "duration": audio.duration_seconds
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Автоматично відкриваємо документацію в браузері
    print("\n[INFO] SoundAPI запущено!")
    print("[INFO] Документація: http://127.0.0.1\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)

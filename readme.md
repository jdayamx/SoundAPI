# 🔊 SoundAPI

Кросплатформна система для дистанційного керування аудіо-пристроями через REST API. Дозволяє централізовано керувати звуком на багатьох комп'ютерах (інстансах) через ваш Laravel додаток.

## 🌟 Ключові особливості
- **Кросплатформність:** Стабільна робота на Windows 11 та Linux (Debian/Ubuntu).
- **Python 3.13 Support:** Виправлено проблему видаленого модуля `audioop` через `audioop-lts`.
- **Multi-Instance:** Laravel може керувати необмеженою кількістю звукових серверів.
- **Volume Control:** Програмне керування гучністю (0.0-1.0) без зміни системного мікшера.
- **Auto-Setup:** Автоматичне встановлення Python-залежностей та FFmpeg через `winget`.

## 🚀 Налаштування Python Сервера (Інстансу)

1. **Запуск:**
   Просто запустіть головний скрипт. Він автоматично перевірить наявність системних утиліт та бібліотек:
   ```bash
   python main.py
   ```

2. **Порт за замовчуванням:** 8000
3. **Ендпоїнти:**
POST /api/auth — отримання JWT токена.
GET /api/list — список активних колонок (сортований: пристрій за замовчуванням — перший).
POST /api/play — запуск аудіо за URL з вказанням гучності та ID пристрою.

## 🔗 Інтеграція з Laravel

### 1. Конфігурація (`config/sound_api.php`)
Створіть файл конфігурації для опису всіх звукових точок:

```php
<?php

return [
    'instances' => [
        'living_room' => [
            'url'  => env('SOUND_API_LR_URL', 'http://192.168.1.10:8000'),
            'user' => 'admin',
            'pass' => 'password123',
        ],
        'kitchen' => [
            'url'  => env('SOUND_API_KITCHEN_URL', 'http://192.168.1.11:8000'),
            'user' => 'admin',
            'pass' => 'password123',
        ],
    ],
];
```

### 2. Laravel Сервіс (App\Services\SoundApiService.php)
```php
<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Cache;

class SoundApiService
{
    /**
     * Отримати токен для конкретного хоста
     */
    protected function getToken(string $url, string $user, string $pass)
    {
        $cacheKey = "sound_api_token_" . md5($url);

        return Cache::remember($cacheKey, 3000, function () use ($url, $user, $pass) {
            $response = Http::asForm()->post("{$url}/api/auth", [
                'username' => $user,
                'password' => $pass,
            ]);

            return $response->json()['access_token'] ?? null;
        });
    }

    /**
     * Універсальний метод для запитів до будь-якого інстансу
     */
    protected function request(array $instance, string $method, string $endpoint, array $data = [])
    {
        $url = $instance['url'];
        $token = $this->getToken($url, $instance['user'], $instance['pass']);

        return Http::withToken($token)
            ->timeout(5)
            ->{$method}("{$url}/api/{$endpoint}", $data)
            ->json();
    }

    public function listDevices(array $instance)
    {
        return $this->request($instance, 'get', 'list');
    }

    public function play(array $instance, int $deviceId, string $soundUrl, float $volume = 1.0)
    {
        return $this->request($instance, 'post', 'play', [
            'device_id' => $deviceId,
            'url' => $soundUrl,
            'volume' => $volume, // Передаємо гучність
        ]);
    }
}
```

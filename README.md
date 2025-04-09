# Manga.ovh Loader 1.0 by Yukich 
## Требования

- Python 3.7 или выше
- Установленные пакеты:
  - requests
  - beautifulsoup4
  - colorama

## Установка зависимостей

```bash
pip install -r requirements.txt
```
## Использование

```bash
python Loader.py "URL_страницы" -o папка_для_сохранения
```

### Важно!

1. **URL должен быть заключен в кавычки** (иначе символы & в URL будут интерпретированы как команды терминала)
2. **URL должен содержать ID главы и не содержать дополнительных параметров**

#### Правильный формат URL:
```
https://manga.ovh/content/имя_манги/ID_главы
```

#### Примеры:

✅ **ПРАВИЛЬНО**:
```bash
python Loader.py "https://manga.ovh/content/lookism/ac875d64-07b0-4f1c-9e34-f06648719ffd"
```

❌ **НЕПРАВИЛЬНО**:
```bash
python Loader.py https://manga.ovh/content/lookism/ac875d64-07b0-4f1c-9e34-f06648719ffd?page=0
```


## Параметры командной строки

- `url` - URL страницы манги (обязательный параметр)
- `-o, --output` - директория для сохранения загруженных изображений (по умолчанию: `manga_downloads`)

## Примеры использования

1. Базовое использование:
```bash
python Loader.py "https://manga.ovh/content/lookism/ac875d64-07b0-4f1c-9e34-f06648719ffd"
```

2. Указание собственной директории для сохранения:
```bash
python Loader.py "https://manga.ovh/content/lookism/ac875d64-07b0-4f1c-9e34-f06648719ffd" -o my_downloads
```



import os
import requests
import re
import json
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import sys
from colorama import init, Fore, Style

init()

t0 = 0
total_items = 0
current_idx = 0
current_item = ""
proc_status = 0
last_ts = 0

def p_ok(m):
    print(f"{Fore.GREEN}{m}{Style.RESET_ALL}")
    
def p_info(m):
    print(f"{Fore.CYAN}{m}{Style.RESET_ALL}")

def p_warn(m):
    print(f"{Fore.YELLOW}{m}{Style.RESET_ALL}")

def p_err(m):
    print(f"{Fore.RED}{m}{Style.RESET_ALL}")

def calc_eta(curr, total, elapsed):
    if curr == 0:
        return "∞"

    rate = curr / elapsed 
    remaining_units = total - curr
    if rate > 0:
        remaining_seconds = remaining_units / rate
        if remaining_seconds < 60:
            return f"{int(remaining_seconds)} сек"
        elif remaining_seconds < 3600:
            return f"{remaining_seconds/60:.1f} мин"
        else:
            return f"{remaining_seconds/3600:.1f} ч"
    return "∞"

def make_bar(curr, total, length=50):
    
    if total == 0:
        return "|" + "-" * length + "|"
    
    percent = (curr / total) * 100
    filled_length = int(length * curr / total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    return f"|{Fore.GREEN}{bar}{Style.RESET_ALL}| {percent:.1f}%"

def update_status(force=False):
    
    global t0, total_items, current_idx, current_item, proc_status, last_ts

    now = time.time()
    if not force and now - last_ts < 0.1:
        return
    
    last_ts = now
    
    elapsed = time.time() - t0
    time_estimate = "∞"
    if current_idx > 0 and elapsed > 0:
        time_estimate = calc_eta(current_idx, total_items, elapsed)
    
    bar = make_bar(current_idx, total_items)
    
    file_info = ""
    if current_item:
        if proc_status > 0 and proc_status < 100:
            file_info = f" | {current_item} [{proc_status}%]"
        elif proc_status == 100:
            file_info = f" | {current_item} [✓]"
        else:
            file_info = f" | {current_item}"
    
    
    status_text = f"\r{bar} [{current_idx}/{total_items}] | {int(elapsed)}с/{time_estimate}{file_info}"
    sys.stdout.write(status_text)
    sys.stdout.flush()

def mk_dir(path):
    
    os.makedirs(path, exist_ok=True)

def dl_file(url, save_path, headers=None):
    
    global current_item, proc_status
    
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://manga.ovh/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
        }
    
    try:
        current_item = os.path.basename(save_path)
        proc_status = 0
        update_status(True)
        
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()  
           
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            
            if '?' in url:
                base_url = url.split('?')[0]
                
                alt_urls = [
                    f"{base_url}?width=700&type=jpeg&quality=75",
                    f"{base_url}?width=1000&type=jpeg&quality=80",
                    f"{base_url}?width=1280&type=jpeg&quality=90",
                    base_url  
                ]
                
                for alt_url in alt_urls:
                    if alt_url != url:  
                        return dl_file(alt_url, save_path, headers)
            
            return False
         
        total_size = int(response.headers.get('content-length', 0))
        
        
        with open(save_path, 'wb') as file:
            if total_size > 0:
                
                downloaded = 0
                last_percent = 0
                
                for data in response.iter_content(chunk_size=8192):  
                    downloaded += len(data)
                    file.write(data)
                    
                    
                    current_percent = int((downloaded / total_size) * 100)
                    if current_percent > last_percent + 9:  
                        proc_status = current_percent
                        update_status()
                        last_percent = current_percent
            else:
                
                file.write(response.content)
               
        proc_status = 100
        update_status(True)
        
        return True
    
    except requests.RequestException as e:
       
        sys.stdout.write(f"\rОшибка при скачивании {current_item}: {e}".ljust(100))
        sys.stdout.flush()
        time.sleep(0.5)  
        
        
        if '?' in url and (isinstance(e, requests.HTTPError) or "timeout" in str(e).lower()):
            base_url = url.split('?')[0]
            time.sleep(0.5)  
            return dl_file(base_url, save_path, headers)
            
        return False

def get_image_urls(html, chapter_id, cfg_dir):
    
    urls = []
    
    
    pages_match = re.search(r'"pages":\s*\[\s*1\s*,\s*(\[.*?\])\s*\]', html, re.DOTALL)
    if pages_match:
        try:
            pages_json_str = pages_match.group(1)
            img_urls = re.findall(r'"image":\s*\[\s*0\s*,\s*"(https://static\.manga\.ovh/chapters/[^"]+)"\s*\]', pages_json_str)
            if img_urls:
                urls.extend(img_urls)
        except Exception as e:
            pass
    
    
    if len(urls) < 3:
        try:
            next_data_match = re.search(r'window\.__NEXT_DATA__\s*=\s*({.*?});', html, re.DOTALL)
            if next_data_match:
                json_text = next_data_match.group(1)
                
                with open(os.path.join(cfg_dir, 'data.json'), 'w', encoding='utf-8') as f:
                    f.write(json_text)
                
                image_pattern = fr'https://static\.manga\.ovh/chapters/{chapter_id}/[^"\'\\]+\.(?:jpeg|jpg|png|webp)'
                all_images = re.findall(image_pattern, json_text)
                if all_images:
                    urls.extend(all_images)
        except Exception:
            pass
    
    
    image_pattern = fr'https://static\.manga\.ovh/chapters/{chapter_id}/[^"\'\\<>\s]+\.(?:jpeg|jpg|png|webp)(?:\?[^"\'\\<>\s]+)?'
    all_images = re.findall(image_pattern, html)
    if all_images:
        for img in all_images:
            if img not in urls:
                urls.append(img)
    
    # URL  в формате: "0":{"url":"https://..."}
    numbered_urls = re.findall(r'"(\d+)"[^{]*?{\s*"url"\s*:\s*"([^"]+)"', html)
    if numbered_urls:
        
        numbered_urls.sort(key=lambda x: int(x[0]))
        for _, url in numbered_urls:
            if url not in urls:
                urls.append(url)
  
    soup = BeautifulSoup(html, 'html.parser')
   
    for div in soup.find_all('div', attrs={'data-chapter-id': True, 'data-page-index': True}):
        img = div.find('img', src=True)
        if img and img['src'] not in urls:
            urls.append(img['src'])
   
    for img in soup.find_all('img'):
        for attr in ['src', 'data-src', 'data-original', 'data-lazy', 'data-srcset']:
            if img.has_attr(attr) and img[attr].endswith(('.jpg', '.jpeg', '.png', '.webp')):
                if img[attr] not in urls:
                    urls.append(img[attr])
   
    clean_urls = []
    seen_base_urls = set()
    
    for url in urls:
        
        url = url.replace('\\"', '"').replace('\\/', '/')
        
        
        if len(url) > 500 or "&quot;" in url or "%5D" in url or "{" in url or "}" in url:
            continue
       
        base_url = url.split('?')[0]
        
        
        if base_url in seen_base_urls:
            continue
            
        seen_base_urls.add(base_url)
        
        
        if url not in clean_urls:
            clean_urls.append(url)
    
    
    with open(os.path.join(cfg_dir, 'all_urls.ini'), 'w', encoding='utf-8') as f:
        f.write("[urls]\n")
        for i, url in enumerate(clean_urls, 1):
            f.write(f"u{i} = {url}\n")
    
    
    final_urls = []
    seen_base_urls = set()
    
    for url in clean_urls:
       
        base_url = url.split('?')[0]
        
        
        if base_url in seen_base_urls:
            continue
            
        seen_base_urls.add(base_url)
        
        # содержит .jpg/.jpeg/.png/.webp
        if not re.search(r'\.(jpeg|jpg|png|webp)($|\?)', base_url.lower()):
            continue
            
        if "width=" in url and "type=" in url and "quality=" in url:
           
            final_urls.append(url)
        else:
            
            modified_url = f"{base_url}?width=700&type=jpeg&quality=75"
            final_urls.append(modified_url)
    
    # ОТЛАДКА
    with open(os.path.join(cfg_dir, 'dl_urls.ini'), 'w', encoding='utf-8') as f:
        f.write("[urls]\n")
        for i, url in enumerate(final_urls, 1):
            f.write(f"u{i} = {url}\n")
    
    p_ok(f"Найдено {len(final_urls)} изображений для загрузки")
    return final_urls

def sort_items(urls):
    """Анализирует и сортирует URL-адреса изображений по их порядковому номеру"""
    indexed_urls = []
    for url in urls:
        try:
           
            index_match = re.search(r'index["\s:=]+(\d+)', url)
            if index_match:
                indexed_urls.append((url, int(index_match.group(1))))
                continue
                
            
            page_match = re.search(r'/([0-9]+)\.[a-zA-Z]+$', url)
            if page_match:
                indexed_urls.append((url, int(page_match.group(1))))
                continue
                
            
            number_match = re.search(r'[-_](\d+)\.(?:jpe?g|png|webp)', url)
            if number_match:
                indexed_urls.append((url, int(number_match.group(1))))
                continue
                
            
            indexed_urls.append((url, len(indexed_urls)))
        except Exception:
            
            indexed_urls.append((url, len(indexed_urls)))
    
    
    indexed_urls.sort(key=lambda x: x[1])
    
    
    return [url for url, _ in indexed_urls]

def process_content(url, out_dir, headers=None):
    
    global t0, total_items, current_idx
    
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://manga.ovh/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    
    # Извлекаем название манги и ID главы из URL
    url_parts = url.strip('/').split('/')
    manga_name = url_parts[-2] if len(url_parts) >= 2 else "unknown"
    chapter_id = url_parts[-1]
    
    # Номер главы по умолчанию и метка времени для уникальности
    chapter_number = "000"
    timestamp = int(time.time())
    
    # Создаем уникальную директорию для каждой главы
    folder_name = f"{manga_name}_{chapter_number}_{timestamp}"
    chapter_dir = os.path.join(out_dir, folder_name)
    mk_dir(chapter_dir)
    
    # Создаем директорию для конфигураций
    cfg_dir = os.path.join(chapter_dir, 'cfg')
    mk_dir(cfg_dir)
    
    try:
        # Получаем HTML-код страницы
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Пытаемся найти номер главы в HTML
        try:
            # Ищем типичные паттерны номера главы в тексте
            chapter_match = re.search(r'[Гг]лава\s+(\d+)', response.text)
            if chapter_match:
                chapter_number = chapter_match.group(1).zfill(3)
                # Обновляем имя папки с правильным номером главы, сохраняя метку времени
                new_folder_name = f"{manga_name}_{chapter_number}_{timestamp}"
                new_chapter_dir = os.path.join(out_dir, new_folder_name)
                
                # Переименовываем директорию
                if chapter_dir != new_chapter_dir:
                    os.rename(chapter_dir, new_chapter_dir)
                    chapter_dir = new_chapter_dir
                    cfg_dir = os.path.join(chapter_dir, 'cfg')
        except Exception as e:
            p_warn(f"Не удалось определить номер главы: {e}")
       
        # Сохраняем исходный HTML для отладки
        html_file = os.path.join(cfg_dir, 'src.html')
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Получаем URL изображений
        image_urls = get_image_urls(response.text, chapter_id, cfg_dir)
        
        if not image_urls:
            p_err("Не удалось найти изображения на странице!")
            return
        
        # Сортируем URL-адреса по порядку страниц
        image_urls = sort_items(image_urls)
        
        # Сохраняем список URL для отладки
        with open(os.path.join(cfg_dir, 'sorted_urls.ini'), 'w', encoding='utf-8') as f:
            f.write("[urls]\n")
            for i, url in enumerate(image_urls, 1):
                f.write(f"p{i:03d} = {url}\n")
        
        # Устанавливаем переменные для прогресса
        total_items = len(image_urls)
        current_idx = 0
        
        print("\n" + "=" * 60)
        print(f"Обработка манги: {manga_name}, глава {chapter_number}")
        print("=" * 60)

        t0 = time.time()
        update_status(True)
        
        downloaded_count = 0
        
        for i, url in enumerate(image_urls, 1):
            current_idx = i - 1
            update_status(True)
       
            ext = url.split('.')[-1].lower().split('?')[0]  
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                ext = 'jpeg'  
                
            # Формируем путь для сохранения
            filepath = os.path.join(chapter_dir, f"p_{i:03d}.{ext}")
            
            # В новой директории файлы точно не существуют, поэтому убираем проверку
            # и всегда скачиваем
            
            current_item = f"p_{i:03d}.{ext}"
            
            # Скачиваем с несколькими попытками
            max_retries = 3
            success = False
            for retry in range(max_retries):
                if retry > 0:
                    current_item = f"p_{i:03d}.{ext} (попытка {retry+1}/{max_retries})"
                    update_status(True)
                
                success = dl_file(url, filepath, headers)
                if success:
                    downloaded_count += 1
                    break
                elif retry < max_retries - 1:
                    time.sleep(0.5) 
            
            time.sleep(0.1)
   
        current_idx = total_items
        current_item = "Завершено!"
        update_status(True)
        print("\n")  
        
        print("=" * 60)
        p_ok(f"Скачано {downloaded_count} из {len(image_urls)} изображений")
        p_ok(f"Данные сохранены в: {chapter_dir}")
        print("=" * 60)
    
    except Exception as e:
        p_err(f"Ошибка при загрузке главы: {e}")
        import traceback
        traceback.print_exc()
        
    # Возвращаем путь к директории с главой
    return chapter_dir

def main():
    parser = argparse.ArgumentParser(description='Скачивание манги с manga.ovh')
    parser.add_argument('url', help='URL главы манги')
    parser.add_argument('-o', '--output', default='manga_downloads', help='Директория для сохранения')
    args = parser.parse_args()

    os.system('')  
    
    # Извлекаем название манги из URL для информационного вывода
    url_parts = args.url.strip('/').split('/')
    manga_name = url_parts[-2] if len(url_parts) >= 2 else "unknown"
    
    # Базовая директория для сохранения
    base_dir = args.output
    
    print("\n" + "=" * 60)
    print(f"{Fore.CYAN}Manga.ovh Loader v1.0{Style.RESET_ALL}")
    print("=" * 60)
    print(f"URL: {Fore.YELLOW}{args.url}{Style.RESET_ALL}")
    print(f"Манга: {Fore.YELLOW}{manga_name}{Style.RESET_ALL}")
    print(f"Базовая директория: {Fore.YELLOW}{base_dir}{Style.RESET_ALL}")
    print("=" * 60 + "\n")
    
    # Скачиваем главу
    start_time = time.time()
    chapter_dir = process_content(args.url, base_dir)
   
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    
    print("\n" + "=" * 60)
    p_ok(f"Загрузка завершена за {int(minutes)} мин. {int(seconds)} сек.!")
    print(f"Сохранено в: {Fore.YELLOW}{chapter_dir}{Style.RESET_ALL}")
    print("=" * 60)

if __name__ == "__main__":
    main() 
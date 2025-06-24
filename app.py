# app.py - Простая и надежная версия
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import os
import requests
import re
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Конфигурация
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

# Папка для шрифтов
FONTS_DIR = Path("fonts")
FONTS_DIR.mkdir(exist_ok=True)

# Популярные Google Fonts с поддержкой кириллицы
GOOGLE_FONTS_CYRILLIC = {
    "roboto": "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu72xKOzY.woff2",
    "opensans": "https://fonts.gstatic.com/s/opensans/v40/memSYaGs126MiZpBA-UvWbX2vVnXBbObj2OVZyOOSr4dVJWUgsjZ0B4gaVc.ttf",
    "montserrat": "https://fonts.gstatic.com/s/montserrat/v26/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCtr6Ew7.ttf",
    "ptsans": "https://fonts.gstatic.com/s/ptsans/v17/jizaRExUiTo99u79D0KEwA.ttf",
    "ptserif": "https://fonts.gstatic.com/s/ptserif/v18/EJRVQgYoZZY2vCFuvAFWzr8.ttf",
    "playfair": "https://fonts.gstatic.com/s/playfairdisplay/v36/nuFiD-vYSZviVYUb_rj3ij__anPXDTzYgEM8.ttf",
    "lora": "https://fonts.gstatic.com/s/lora/v32/0QIvMX1D_JOuMw_hLdO6T2wV.ttf",
    "nunito": "https://fonts.gstatic.com/s/nunito/v26/XRXI3I6Li01BKofAjsOUb-vISTs.ttf"
}

def test_font_with_cyrillic(font, test_text="Тест"):
    """Проверяет может ли шрифт отобразить кириллицу"""
    try:
        # Создаем тестовое изображение
        test_img = Image.new('RGB', (200, 100), color=(255, 255, 255))
        test_draw = ImageDraw.Draw(test_img)
        
        # Пробуем нарисовать кириллицу
        test_draw.text((10, 10), test_text, font=font, fill=(0, 0, 0))
        
        # Проверяем что текст действительно нарисовался
        # Простая проверка - есть ли черные пиксели
        pixels = list(test_img.getdata())
        has_black_pixels = any(pixel != (255, 255, 255) for pixel in pixels)
        
        if has_black_pixels:
            print(f"Font passed cyrillic test")
            return True
        else:
            print(f"Font failed cyrillic test - no black pixels")
            return False
            
    except Exception as e:
        print(f"Font failed cyrillic test - exception: {e}")
        return False

def download_google_font(font_name, font_size):
    """Скачивает Google Font если нужен"""
    if not font_name:
        return None
        
    font_name_lower = font_name.lower().replace(' ', '').replace('-', '')
    
    # Проверяем есть ли в предустановленных
    if font_name_lower in GOOGLE_FONTS_CYRILLIC:
        font_url = GOOGLE_FONTS_CYRILLIC[font_name_lower]
        
        # Путь для сохранения
        font_path = FONTS_DIR / f"{font_name_lower}.ttf"
        
        # Скачиваем если еще нет
        if not font_path.exists():
            try:
                print(f"Downloading Google Font: {font_name}")
                headers = {'User-Agent': 'Mozilla/5.0 (compatible)'}
                response = requests.get(font_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    with open(font_path, 'wb') as f:
                        f.write(response.content)
                    print(f"Font saved: {font_path}")
                else:
                    print(f"Failed to download: {response.status_code}")
                    return None
            except Exception as e:
                print(f"Download error: {e}")
                return None
        
        # Загружаем шрифт
        try:
            font = ImageFont.truetype(str(font_path), font_size)
            
            # ВАЖНО: Проверяем что шрифт может отображать кириллицу
            if test_font_with_cyrillic(font):
                print(f"Loaded Google Font with Cyrillic: {font_name}")
                return font
            else:
                print(f"Google Font {font_name} doesn't support Cyrillic")
                return None
                
        except Exception as e:
            print(f"Font load error: {e}")
            return None
    
    return None

def get_safe_font(font_size):
    """Получение безопасного шрифта"""
    # Системные шрифты с кириллицей
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
                
                # Проверяем поддержку кириллицы
                if test_font_with_cyrillic(font):
                    print(f"Using system font with Cyrillic: {font_path}")
                    return font
                else:
                    print(f"System font {font_path} doesn't support Cyrillic")
                    continue
                    
            except:
                continue
    
    # Fallback
    try:
        return ImageFont.load_default()
    except:
        return None

def transliterate(text):
    """Простая транслитерация кириллицы"""
    cyrillic = "абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
    latin = "abvgdeezziyklmnoprstufhcchshsch'y'euyaABVGDEEZZIYKLMNOPRSTUFHCCHSHSCH'Y'EUYA"
    
    result = ""
    for char in text:
        if char in cyrillic:
            index = cyrillic.index(char)
            result += latin[index]
        else:
            result += char
    return result

def wrap_text(text, max_width, font_size):
    """Простое разбиение текста на строки"""
    words = text.split()
    lines = []
    current_line = []
    
    # Приблизительная ширина символа
    char_width = font_size * 0.6
    chars_per_line = int(max_width / char_width)
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        if len(test_line) <= chars_per_line:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

@app.route('/', methods=['GET'])
def home():
    """API информация"""
    return jsonify({
        "service": "Simple Text Overlay API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "POST /overlay": "Простое наложение текста",
            "GET /health": "Статус сервиса"
        }
    })

@app.route('/overlay', methods=['POST'])
def overlay_text():
    """Основной endpoint наложения текста"""
    try:
        data = request.get_json(force=True)
        
        if not data or 'image' not in data:
            return jsonify({"error": "Поле 'image' обязательно"}), 400
        
        if 'text' not in data or not str(data['text']).strip():
            return jsonify({"error": "Поле 'text' обязательно"}), 400
        
        # Декодируем изображение
        image_data = data['image']
        if image_data.startswith('data:image'):
            header, encoded = image_data.split(',', 1)
            image_bytes = base64.b64decode(encoded)
        else:
            image_bytes = base64.b64decode(image_data)
        
        # Открываем изображение
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # Параметры
        original_text = str(data.get('text', 'ТЕКСТ'))
        font_size = data.get('fontSize', min(width, height) // 15)
        position = data.get('position', 'bottom')  # top, center, bottom
        font_family = data.get('fontFamily', None)  # Новый параметр для Google Fonts
        
        # Цвета
        text_color = tuple(data.get('textColor', [255, 255, 255]))[:3]
        bg_color = tuple(data.get('backgroundColor', [0, 0, 0, 180]))
        outline_width = data.get('outlineWidth', 2)
        
        print(f"Processing: '{original_text}' on {width}x{height}")
        if font_family:
            print(f"Requested font: {font_family}")
        
        # Получаем шрифт (сначала пробуем Google Font)
        font = None
        used_google_font = False
        
        if font_family:
            font = download_google_font(font_family, font_size)
            if font:
                used_google_font = True
        
        if not font:
            font = get_safe_font(font_size)
        
        # Определяем текст для отображения
        display_text = original_text
        font_works = True
        
        # Проверяем есть ли кириллица в тексте
        has_cyrillic = any(ord(c) > 127 and ord(c) < 1200 for c in original_text)
        
        if has_cyrillic:
            print(f"Text contains Cyrillic characters")
            
            # Если есть кириллица, проверяем что шрифт может её отобразить
            if font and not test_font_with_cyrillic(font, original_text):
                print("Font cannot display Cyrillic, using transliteration")
                font_works = False
                display_text = transliterate(original_text)
            elif not font:
                print("No font available, using transliteration")
                font_works = False
                display_text = transliterate(original_text)
        else:
            print(f"Text is Latin/ASCII")
        
        print(f"Final display text: '{display_text}'")
        
        # Разбиваем текст на строки
        max_text_width = width - (width // 10)  # 90% ширины
        lines = wrap_text(display_text, max_text_width, font_size)
        
        # Вычисляем размеры
        line_height = font_size * 1.2
        total_height = len(lines) * line_height
        max_line_width = max(len(line) for line in lines) * font_size * 0.6
        
        # Позиция
        margin = max(20, min(width, height) // 30)
        
        if position == 'top':
            start_y = margin
        elif position == 'bottom':
            start_y = height - margin - total_height
        else:  # center
            start_y = (height - total_height) // 2
        
        start_x = (width - max_line_width) // 2
        
        # Рисуем фон
        padding = max(15, font_size // 4)
        bg_rect = [
            max(0, start_x - padding),
            max(0, start_y - padding),
            min(width, start_x + max_line_width + padding),
            min(height, start_y + total_height + padding)
        ]
        
        # Полупрозрачный фон
        if len(bg_color) >= 4:
            overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rounded_rectangle(bg_rect, radius=padding//2, fill=bg_color)
            
            image = image.convert('RGBA')
            image = Image.alpha_composite(image, overlay)
            image = image.convert('RGB')
            draw = ImageDraw.Draw(image)
        else:
            draw.rounded_rectangle(bg_rect, radius=padding//2, fill=bg_color[:3])
        
        # Рисуем текст
        current_y = start_y
        
        for line in lines:
            if not line.strip():
                current_y += line_height
                continue
            
            line_width = len(line) * font_size * 0.6
            line_x = (width - line_width) // 2
            
            try:
                # Обводка
                if outline_width > 0:
                    for dx in range(-outline_width, outline_width + 1):
                        for dy in range(-outline_width, outline_width + 1):
                            if dx != 0 or dy != 0:
                                if font:
                                    draw.text((line_x + dx, current_y + dy), line, font=font, fill=(0, 0, 0))
                                else:
                                    draw.text((line_x + dx, current_y + dy), line, fill=(0, 0, 0))
                
                # Основной текст
                if font:
                    draw.text((line_x, current_y), line, font=font, fill=text_color)
                else:
                    draw.text((line_x, current_y), line, fill=text_color)
                
                print(f"Drew: '{line}' at ({line_x}, {current_y})")
                
            except Exception as e:
                print(f"Error drawing line: {e}")
                # Fallback - простые прямоугольники
                char_width = font_size // 3
                rect_x = line_x
                for char in line:
                    if char != ' ':
                        draw.rectangle([rect_x, current_y, rect_x + char_width, current_y + font_size], fill=text_color)
                    rect_x += char_width + 3
            
            current_y += line_height
        
        # Сохраняем
        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG', quality=95)
        output_buffer.seek(0)
        
        result_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": result_base64,
            "debug": {
                "original_text": original_text,
                "display_text": display_text,
                "font_works": font_works,
                "used_google_font": used_google_font,
                "requested_font": font_family,
                "lines": lines,
                "image_size": f"{width}x{height}"
            }
        })
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/test-cyrillic', methods=['POST'])
def test_cyrillic():
    """Тестирует отображение кириллицы"""
    try:
        data = request.get_json(force=True)
        font_name = data.get('fontFamily', None)
        test_text = data.get('text', 'Тест кириллицы АБВ 123')
        font_size = 48
        
        # Создаем тестовое изображение
        test_img = Image.new('RGB', (600, 200), color=(255, 255, 255))
        test_draw = ImageDraw.Draw(test_img)
        
        results = {}
        y_position = 20
        
        # Тестируем Google Font
        if font_name:
            google_font = download_google_font(font_name, font_size)
            if google_font:
                cyrillic_works = test_font_with_cyrillic(google_font, test_text)
                results[f"google_{font_name}"] = cyrillic_works
                
                try:
                    test_draw.text((20, y_position), f"Google {font_name}: {test_text}", 
                                 font=google_font, fill=(0, 0, 0))
                    y_position += 50
                except:
                    test_draw.text((20, y_position), f"Google {font_name}: ERROR", 
                                 fill=(255, 0, 0))
                    y_position += 50
        
        # Тестируем системный шрифт
        system_font = get_safe_font(font_size)
        if system_font:
            cyrillic_works = test_font_with_cyrillic(system_font, test_text)
            results["system_font"] = cyrillic_works
            
            try:
                test_draw.text((20, y_position), f"System: {test_text}", 
                             font=system_font, fill=(0, 0, 0))
                y_position += 50
            except:
                test_draw.text((20, y_position), f"System: ERROR", fill=(255, 0, 0))
                y_position += 50
        
        # Тестируем без шрифта
        try:
            test_draw.text((20, y_position), f"Default: {test_text}", fill=(0, 0, 0))
            y_position += 50
            results["default_font"] = True
        except:
            test_draw.text((20, y_position), f"Default: ERROR", fill=(255, 0, 0))
            results["default_font"] = False
            y_position += 50
        
        # Транслитерация
        transliterated = transliterate(test_text)
        test_draw.text((20, y_position), f"Transliterated: {transliterated}", fill=(0, 0, 0))
        results["transliteration"] = transliterated
        
        # Сохраняем результат
        output_buffer = io.BytesIO()
        test_img.save(output_buffer, format='PNG')
        output_buffer.seek(0)
        
        result_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": result_base64,
            "test_results": results,
            "test_text": test_text
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/fonts', methods=['GET'])
def available_fonts():
    """Список доступных Google Fonts для основного endpoint"""
    return jsonify({
        "available_google_fonts": list(GOOGLE_FONTS_CYRILLIC.keys()),
        "usage": "Добавьте параметр 'fontFamily' в запрос к /overlay",
        "examples": {
            "roboto": "Roboto",
            "opensans": "Open Sans", 
            "montserrat": "Montserrat",
            "ptsans": "PT Sans",
            "ptserif": "PT Serif",
            "playfair": "Playfair Display",
            "lora": "Lora",
            "nunito": "Nunito"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья"""
    return jsonify({
        "status": "healthy",
        "version": "1.0.0"
    })

# Обработчики ошибок
@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Файл слишком большой (макс 32MB)"}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint не найден"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Внутренняя ошибка сервера"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

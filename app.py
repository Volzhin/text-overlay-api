from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
import io
import os
import requests

app = Flask(__name__)
CORS(app)

# Форматы изображений
FORMATS = {
    'vk-square': {'width': 600, 'height': 600},
    'vk-portrait': {'width': 1080, 'height': 1350},
    'vk-landscape': {'width': 1080, 'height': 607},
    'stories': {'width': 1080, 'height': 1920}
}

def get_font_sizes(format_name):
    """Получить размеры шрифтов для формата"""
    sizes = {
        'vk-square': {'logo_text': 52, 'title': 42, 'subtitle': 24, 'disclaimer': 16, 'padding': 40},
        'vk-portrait': {'logo_text': 72, 'title': 64, 'subtitle': 36, 'disclaimer': 24, 'padding': 60},
        'vk-landscape': {'logo_text': 58, 'title': 48, 'subtitle': 28, 'disclaimer': 20, 'padding': 50},
        'stories': {'logo_text': 68, 'title': 56, 'subtitle': 32, 'disclaimer': 22, 'padding': 60}
    }
    return sizes.get(format_name, sizes['vk-square'])

def create_font(size):
    """Создать шрифт с поддержкой Unicode"""
    try:
        # Попробуем шрифты с поддержкой кириллицы
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/System/Library/Fonts/Arial Unicode MS.ttf",
            "/System/Library/Fonts/Arial.ttf"
        ]
        
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, size)
                # Проверим, поддерживает ли шрифт кириллицу
                test_text = "Тест"
                temp_img = Image.new('RGB', (100, 50), 'white')
                temp_draw = ImageDraw.Draw(temp_img)
                try:
                    temp_draw.text((0, 0), test_text, font=font, fill='black')
                    return font
                except:
                    continue
            except:
                continue
        
        # Если ничего не найдено, используем стандартный
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

def safe_text(text):
    """Безопасная обработка текста"""
    if not text:
        return ""
    
    # Убедимся, что текст в UTF-8
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except:
            text = text.decode('utf-8', errors='ignore')
    
    # Заменим проблематичные символы на безопасные аналоги
    replacements = {
        ''': "'",
        ''': "'",
        '"': '"',
        '"': '"',
        '–': '-',
        '—': '-',
        '…': '...'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return str(text)

def wrap_text(text, font, max_width, draw):
    """Разбить текст на строки"""
    text = safe_text(text)
    if not text:
        return []
    
    words = text.split(' ')
    lines = []
    current_line = ''
    
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        try:
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
        except:
            # Fallback для старых версий Pillow
            line_width = len(test_line) * (font.size * 0.6)
        
        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines

def draw_text_with_shadow(draw, text, position, font, fill_color='white', shadow_color='black'):
    """Нарисовать текст с тенью"""
    text = safe_text(text)
    if not text:
        return
        
    x, y = position
    try:
        # Тень
        draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
        # Основной текст
        draw.text((x, y), text, font=font, fill=fill_color)
    except Exception as e:
        print(f"Ошибка отрисовки текста '{text}': {e}")
        # Попробуем без специальных символов
        safe_text_ascii = text.encode('ascii', errors='ignore').decode('ascii')
        if safe_text_ascii:
            draw.text((x + 2, y + 2), safe_text_ascii, font=font, fill=shadow_color)
            draw.text((x, y), safe_text_ascii, font=font, fill=fill_color)

def generate_image(background_image, logo_text, title, subtitle, disclaimer, logo_url, format_name):
    """Генерировать изображение"""
    if format_name not in FORMATS:
        raise ValueError(f"Неподдерживаемый формат: {format_name}")
    
    # Безопасная обработка всех текстов
    logo_text = safe_text(logo_text)
    title = safe_text(title)
    subtitle = safe_text(subtitle)
    disclaimer = safe_text(disclaimer)
    
    # Получить размеры
    target_size = FORMATS[format_name]
    width, height = target_size['width'], target_size['height']
    font_sizes = get_font_sizes(format_name)
    padding = font_sizes['padding']
    
    # Изменить размер фонового изображения
    background = background_image.resize((width, height), Image.Resampling.LANCZOS)
    background = background.convert('RGBA')
    
    # Создать затемняющий слой
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Простое затемнение (градиент эмулируем через прозрачность)
    for y in range(height):
        alpha = int(76 + (153 - 76) * y / height)  # От 30% до 60%
        overlay_draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))
    
    # Наложить затемнение
    background = Image.alpha_composite(background, overlay)
    
    # Создать объект для рисования
    draw = ImageDraw.Draw(background)
    
    # Создать шрифты
    try:
        logo_font = create_font(font_sizes['logo_text'])
        title_font = create_font(font_sizes['title'])
        subtitle_font = create_font(font_sizes['subtitle'])
        disclaimer_font = create_font(font_sizes['disclaimer'])
    except Exception as e:
        print(f"Ошибка создания шрифтов: {e}")
        # Используем стандартные шрифты
        logo_font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        disclaimer_font = ImageFont.load_default()
    
    # Текущая позиция Y
    current_y = padding
    text_max_width = width - (padding * 2)
    
    # Загрузка логотипа-изображения (если есть)
    if logo_url:
        try:
            response = requests.get(logo_url, timeout=5)
            if response.status_code == 200:
                logo_image = Image.open(io.BytesIO(response.content))
                logo_size = 80 if format_name == 'vk-square' else 120
                
                # Пропорциональное изменение размера
                logo_image.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                # Наложить логотип
                if logo_image.mode == 'RGBA':
                    background.paste(logo_image, (padding, current_y), logo_image)
                else:
                    background.paste(logo_image, (padding, current_y))
                
                current_y += logo_image.height + 30
        except Exception as e:
            print(f"Ошибка загрузки логотипа: {e}")
    
    # Логотип-текст (например "YANGO")
    if logo_text:
        draw_text_with_shadow(
            draw, logo_text, (padding, current_y), 
            logo_font, 'white', 'black'
        )
        try:
            bbox = draw.textbbox((0, 0), logo_text, font=logo_font)
            current_y += (bbox[3] - bbox[1]) + 30
        except:
            current_y += font_sizes['logo_text'] + 30
    
    # Заголовок
    if title:
        title_lines = wrap_text(title, title_font, text_max_width, draw)
        for line in title_lines:
            draw_text_with_shadow(
                draw, line, (padding, current_y), 
                title_font, 'white', 'black'
            )
            try:
                bbox = draw.textbbox((0, 0), line, font=title_font)
                current_y += int((bbox[3] - bbox[1]) * 1.2)
            except:
                current_y += int(font_sizes['title'] * 1.2)
        current_y += 20
    
    # Подзаголовок
    if subtitle:
        subtitle_lines = wrap_text(subtitle, subtitle_font, text_max_width, draw)
        for line in subtitle_lines:
            draw_text_with_shadow(
                draw, line, (padding, current_y), 
                subtitle_font, 'white', 'black'
            )
            try:
                bbox = draw.textbbox((0, 0), line, font=subtitle_font)
                current_y += int((bbox[3] - bbox[1]) * 1.2)
            except:
                current_y += int(font_sizes['subtitle'] * 1.2)
        current_y += 30
    
    # Дисклеймер внизу
    if disclaimer:
        disclaimer_lines = wrap_text(disclaimer, disclaimer_font, text_max_width, draw)
        
        # Рассчитать высоту дисклеймера
        try:
            total_disclaimer_height = 0
            for line in disclaimer_lines:
                bbox = draw.textbbox((0, 0), line, font=disclaimer_font)
                total_disclaimer_height += int((bbox[3] - bbox[1]) * 1.2)
        except:
            total_disclaimer_height = len(disclaimer_lines) * int(font_sizes['disclaimer'] * 1.2)
        
        # Позиционировать внизу
        disclaimer_y = height - padding - total_disclaimer_height
        
        for line in disclaimer_lines:
            draw_text_with_shadow(
                draw, line, (padding, disclaimer_y), 
                disclaimer_font, '#CCCCCC', 'black'
            )
            try:
                bbox = draw.textbbox((0, 0), line, font=disclaimer_font)
                disclaimer_y += int((bbox[3] - bbox[1]) * 1.2)
            except:
                disclaimer_y += int(font_sizes['disclaimer'] * 1.2)
    
    return background.convert('RGB')

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        'message': 'Image Generator API работает!',
        'status': 'Production Ready with Unicode Support',
        'endpoints': {
            'POST /generate/<format>': 'Генерация изображения',
            'GET /formats': 'Получить доступные форматы',
            'GET /': 'Проверка работоспособности'
        },
        'formats': list(FORMATS.keys())
    })

@app.route('/formats')
def get_formats():
    """Получить доступные форматы"""
    return jsonify(FORMATS)

@app.route('/generate/<format_name>', methods=['POST'])
def generate_image_endpoint(format_name):
    """Генерировать изображение"""
    try:
        if format_name not in FORMATS:
            return jsonify({'error': 'Неподдерживаемый формат'}), 400
        
        # Проверить наличие изображения
        if 'image' not in request.files:
            return jsonify({'error': 'Изображение не загружено'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
        
        # Получить параметры с безопасной обработкой кодировки
        logo_text = request.form.get('logoText', '', type=str)
        title = request.form.get('title', '', type=str)
        subtitle = request.form.get('subtitle', '', type=str)
        disclaimer = request.form.get('disclaimer', '', type=str)
        logo_url = request.form.get('logoUrl', '', type=str)
        
        # Загрузить изображение
        try:
            background_image = Image.open(file.stream)
        except Exception as e:
            return jsonify({'error': f'Ошибка обработки изображения: {str(e)}'}), 400
        
        # Генерировать изображение
        result_image = generate_image(
            background_image, logo_text, title, subtitle, disclaimer, logo_url, format_name
        )
        
        # Сохранить в буфер
        img_buffer = io.BytesIO()
        result_image.save(img_buffer, format='PNG', quality=95)
        img_buffer.seek(0)
        
        return send_file(
            img_buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'generated-{format_name}.png'
        )
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return jsonify({'error': f'Ошибка генерации изображения: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)

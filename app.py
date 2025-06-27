from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import skia
import io
import os
import requests
from PIL import Image
import numpy as np

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
    if format_name == 'vk-square':
        return {
            'logo_text': 52,
            'title': 42,
            'subtitle': 24,
            'disclaimer': 16,
            'padding': 40
        }
    elif format_name == 'vk-portrait':
        return {
            'logo_text': 72,
            'title': 64,
            'subtitle': 36,
            'disclaimer': 24,
            'padding': 60
        }
    elif format_name == 'vk-landscape':
        return {
            'logo_text': 58,
            'title': 48,
            'subtitle': 28,
            'disclaimer': 20,
            'padding': 50
        }
    elif format_name == 'stories':
        return {
            'logo_text': 68,
            'title': 56,
            'subtitle': 32,
            'disclaimer': 22,
            'padding': 60
        }

def create_typeface(bold=False):
    """Создать шрифт"""
    style = skia.FontStyle.Bold() if bold else skia.FontStyle.Normal()
    return skia.Typeface('Arial', style)

def wrap_text(canvas, text, font, max_width):
    """Разбить текст на строки"""
    if not text:
        return []
    
    words = text.split(' ')
    lines = []
    current_line = ''
    
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        text_width = font.measureText(test_line)
        
        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines

def draw_text_with_shadow(canvas, text, x, y, font, color, shadow_color):
    """Нарисовать текст с тенью"""
    # Тень
    shadow_paint = skia.Paint(
        AntiAlias=True,
        Color=shadow_color
    )
    canvas.drawString(text, x + 2, y + 2, font, shadow_paint)
    
    # Основной текст
    main_paint = skia.Paint(
        AntiAlias=True,
        Color=color
    )
    canvas.drawString(text, x, y, font, main_paint)

def generate_image(background_image, logo_text, title, subtitle, disclaimer, logo_url, format_name):
    """Генерировать изображение с Canvas"""
    if format_name not in FORMATS:
        raise ValueError(f"Неподдерживаемый формат: {format_name}")
    
    # Получить размеры
    target_size = FORMATS[format_name]
    width, height = target_size['width'], target_size['height']
    font_sizes = get_font_sizes(format_name)
    padding = font_sizes['padding']
    
    # Создать Canvas
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    
    # Изменить размер фонового изображения
    background_resized = background_image.resize((width, height), Image.Resampling.LANCZOS)
    
    # Конвертировать PIL в numpy array
    bg_array = np.array(background_resized)
    
    # Создать Skia изображение из numpy array
    bg_info = skia.ImageInfo.MakeN32Premul(width, height)
    bg_skia = skia.Image.fromarray(bg_array, colorType=skia.kRGBA_8888_ColorType)
    
    # Нарисовать фон
    canvas.drawImage(bg_skia, 0, 0)
    
    # Создать градиентное затемнение
    gradient_colors = [
        skia.Color4f(0, 0, 0, 0.3),  # Верх
        skia.Color4f(0, 0, 0, 0.6)   # Низ
    ]
    gradient = skia.GradientShader.MakeLinear(
        points=[(0, 0), (0, height)],
        colors=gradient_colors
    )
    
    overlay_paint = skia.Paint(Shader=gradient)
    canvas.drawRect(skia.Rect(0, 0, width, height), overlay_paint)
    
    # Создать шрифты
    logo_typeface = create_typeface(bold=True)
    title_typeface = create_typeface(bold=True)
    subtitle_typeface = create_typeface(bold=False)
    disclaimer_typeface = create_typeface(bold=False)
    
    logo_font = skia.Font(logo_typeface, font_sizes['logo_text'])
    title_font = skia.Font(title_typeface, font_sizes['title'])
    subtitle_font = skia.Font(subtitle_typeface, font_sizes['subtitle'])
    disclaimer_font = skia.Font(disclaimer_typeface, font_sizes['disclaimer'])
    
    # Цвета
    white_color = skia.Color4f(1, 1, 1, 1)
    gray_color = skia.Color4f(0.8, 0.8, 0.8, 1)
    shadow_color = skia.Color4f(0, 0, 0, 0.8)
    light_shadow_color = skia.Color4f(0, 0, 0, 0.5)
    
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
                
                # Изменить размер логотипа
                logo_aspect = logo_image.width / logo_image.height
                logo_width = logo_size
                logo_height = int(logo_size / logo_aspect)
                
                logo_resized = logo_image.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
                logo_array = np.array(logo_resized.convert('RGBA'))
                logo_skia = skia.Image.fromarray(logo_array, colorType=skia.kRGBA_8888_ColorType)
                
                canvas.drawImage(logo_skia, padding, current_y)
                current_y += logo_height + 30
        except Exception as e:
            print(f"Ошибка загрузки логотипа: {e}")
    
    # Логотип-текст (например "YANGO")
    if logo_text:
        draw_text_with_shadow(
            canvas, logo_text, padding, current_y + font_sizes['logo_text'],
            logo_font, white_color, shadow_color
        )
        current_y += int(font_sizes['logo_text'] * 1.2) + 30
    
    # Заголовок
    if title:
        title_lines = wrap_text(canvas, title, title_font, text_max_width)
        for line in title_lines:
            draw_text_with_shadow(
                canvas, line, padding, current_y + font_sizes['title'],
                title_font, white_color, light_shadow_color
            )
            current_y += int(font_sizes['title'] * 1.2)
        current_y += 20
    
    # Подзаголовок
    if subtitle:
        subtitle_lines = wrap_text(canvas, subtitle, subtitle_font, text_max_width)
        for line in subtitle_lines:
            draw_text_with_shadow(
                canvas, line, padding, current_y + font_sizes['subtitle'],
                subtitle_font, white_color, light_shadow_color
            )
            current_y += int(font_sizes['subtitle'] * 1.2)
        current_y += 30
    
    # Дисклеймер внизу
    if disclaimer:
        disclaimer_lines = wrap_text(canvas, disclaimer, disclaimer_font, text_max_width)
        
        # Рассчитать высоту дисклеймера
        total_disclaimer_height = len(disclaimer_lines) * int(font_sizes['disclaimer'] * 1.2)
        
        # Позиционировать внизу
        disclaimer_y = height - padding - total_disclaimer_height + font_sizes['disclaimer']
        
        for line in disclaimer_lines:
            draw_text_with_shadow(
                canvas, line, padding, disclaimer_y,
                disclaimer_font, gray_color, light_shadow_color
            )
            disclaimer_y += int(font_sizes['disclaimer'] * 1.2)
    
    # Получить изображение
    image = surface.makeImageSnapshot()
    
    # Конвертировать в PNG
    png_data = image.encodeToData(skia.kPNG)
    
    return png_data.data()

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        'message': 'Image Generator API с Canvas работает!',
        'version': 'Python + Skia Canvas',
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
        
        # Получить параметры
        logo_text = request.form.get('logoText', '')
        title = request.form.get('title', '')
        subtitle = request.form.get('subtitle', '')
        disclaimer = request.form.get('disclaimer', '')
        logo_url = request.form.get('logoUrl', '')
        
        # Загрузить изображение
        try:
            background_image = Image.open(file.stream).convert('RGBA')
        except Exception as e:
            return jsonify({'error': f'Ошибка обработки изображения: {str(e)}'}), 400
        
        # Генерировать изображение
        png_data = generate_image(
            background_image, logo_text, title, subtitle, disclaimer, logo_url, format_name
        )
        
        # Создать буфер
        img_buffer = io.BytesIO(png_data)
        img_buffer.seek(0)
        
        return send_file(
            img_buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'generated-{format_name}.png'
        )
        
    except Exception as e:
        return jsonify({'error': f'Ошибка генерации изображения: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)

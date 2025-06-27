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

# Базовые форматы
FORMATS = {
    'vk-square': {'width': 600, 'height': 600},
    'vk-portrait': {'width': 1080, 'height': 1350},
    'vk-landscape': {'width': 1080, 'height': 607},
    'stories': {'width': 1080, 'height': 1920},
    'custom': {'width': 800, 'height': 600}
}

def calculate_adaptive_font_sizes(width, height):
    """Вычислить адаптивные размеры шрифтов на основе размеров изображения"""
    # Базовые размеры для референса (1080x1080)
    base_width = 1080
    base_height = 1080
    
    # Вычисляем масштабный коэффициент
    width_scale = width / base_width
    height_scale = height / base_height
    scale_factor = (width_scale + height_scale) / 2
    
    # Ограничиваем масштабный коэффициент
    scale_factor = max(0.3, min(scale_factor, 3.0))
    
    # Базовые размеры шрифтов
    base_fonts = {
        'logo_text': 80,
        'title': 64,
        'subtitle': 36,
        'disclaimer': 24,
        'padding': 60
    }
    
    # Применяем масштабирование
    adaptive_fonts = {}
    for key, base_size in base_fonts.items():
        adaptive_fonts[key] = int(base_size * scale_factor)
    
    # Корректировки для разных соотношений сторон
    aspect_ratio = width / height
    
    if aspect_ratio > 1.5:  # Широкие изображения
        adaptive_fonts['logo_text'] = int(adaptive_fonts['logo_text'] * 0.9)
        adaptive_fonts['title'] = int(adaptive_fonts['title'] * 0.9)
    elif aspect_ratio < 0.7:  # Высокие изображения
        adaptive_fonts['logo_text'] = int(adaptive_fonts['logo_text'] * 1.1)
        adaptive_fonts['title'] = int(adaptive_fonts['title'] * 1.1)
    
    return adaptive_fonts

def create_typeface(bold=False):
    """Создать шрифт с поддержкой кириллицы"""
    try:
        if bold:
            return skia.Typeface('DejaVu Sans', skia.FontStyle.Bold())
        else:
            return skia.Typeface('DejaVu Sans', skia.FontStyle.Normal())
    except:
        try:
            # Fallback на системные шрифты
            if bold:
                return skia.Typeface('Arial', skia.FontStyle.Bold())
            else:
                return skia.Typeface('Arial', skia.FontStyle.Normal())
        except:
            # Последний fallback
            return skia.Typeface()

def safe_text(text):
    """Безопасная обработка текста для Unicode"""
    if not text:
        return ""
    
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except:
            text = text.decode('utf-8', errors='replace')
    
    return str(text)

def wrap_text_canvas(canvas, text, font, max_width):
    """Разбить текст на строки для Canvas"""
    text = safe_text(text)
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

def draw_text_with_shadow_canvas(canvas, text, x, y, font, color, shadow_color, shadow_offset=2):
    """Нарисовать текст с тенью на Canvas"""
    text = safe_text(text)
    if not text:
        return
    
    # Создаем краски
    shadow_paint = skia.Paint(
        AntiAlias=True,
        Color=shadow_color
    )
    
    main_paint = skia.Paint(
        AntiAlias=True,
        Color=color
    )
    
    # Рисуем тень
    canvas.drawString(text, x + shadow_offset, y + shadow_offset, font, shadow_paint)
    
    # Рисуем основной текст
    canvas.drawString(text, x, y, font, main_paint)

def generate_image_canvas(background_image, logo_text, title, subtitle, disclaimer, logo_url, width, height):
    """Генерировать изображение с Canvas"""
    
    # Безопасная обработка текстов
    logo_text = safe_text(logo_text)
    title = safe_text(title)
    subtitle = safe_text(subtitle)
    disclaimer = safe_text(disclaimer)
    
    # Вычисляем адаптивные размеры шрифтов
    font_sizes = calculate_adaptive_font_sizes(width, height)
    padding = font_sizes['padding']
    
    print(f"Canvas: Генерируем {width}x{height}, шрифты: {font_sizes}")
    
    # Создаем Canvas surface
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    
    # Изменяем размер фонового изображения
    background_resized = background_image.resize((width, height), Image.Resampling.LANCZOS)
    
    # Конвертируем PIL в numpy array, затем в Skia Image
    bg_array = np.array(background_resized.convert('RGBA'))
    bg_skia = skia.Image.fromarray(bg_array, colorType=skia.kRGBA_8888_ColorType)
    
    # Рисуем фон
    canvas.drawImage(bg_skia, 0, 0)
    
    # Создаем градиентное затемнение
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
    
    # Создаем шрифты с адаптивными размерами
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
    
    current_y = padding
    text_max_width = width - (padding * 2)
    
    # Загрузка логотипа-изображения
    if logo_url:
        try:
            response = requests.get(logo_url, timeout=5)
            if response.status_code == 200:
                logo_pil = Image.open(io.BytesIO(response.content))
                logo_size = int(width * 0.12)  # 12% от ширины
                
                logo_pil.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
                logo_array = np.array(logo_pil.convert('RGBA'))
                logo_skia = skia.Image.fromarray(logo_array, colorType=skia.kRGBA_8888_ColorType)
                
                canvas.drawImage(logo_skia, padding, current_y)
                current_y += logo_skia.height() + int(padding * 0.5)
        except Exception as e:
            print(f"Ошибка загрузки логотипа: {e}")
    
    # Логотип-текст (например "YANGO")
    if logo_text:
        shadow_offset = max(2, font_sizes['logo_text'] // 20)
        draw_text_with_shadow_canvas(
            canvas, logo_text, padding, current_y + font_sizes['logo_text'],
            logo_font, white_color, shadow_color, shadow_offset
        )
        current_y += int(font_sizes['logo_text'] * 1.2) + int(padding * 0.5)
    
    # Заголовок
    if title:
        title_lines = wrap_text_canvas(canvas, title, title_font, text_max_width)
        shadow_offset = max(1, font_sizes['title'] // 25)
        
        for line in title_lines:
            draw_text_with_shadow_canvas(
                canvas, line, padding, current_y + font_sizes['title'],
                title_font, white_color, light_shadow_color, shadow_offset
            )
            current_y += int(font_sizes['title'] * 1.2)
        current_y += int(padding * 0.3)
    
    # Подзаголовок
    if subtitle:
        subtitle_lines = wrap_text_canvas(canvas, subtitle, subtitle_font, text_max_width)
        shadow_offset = max(1, font_sizes['subtitle'] // 30)
        
        for line in subtitle_lines:
            draw_text_with_shadow_canvas(
                canvas, line, padding, current_y + font_sizes['subtitle'],
                subtitle_font, white_color, light_shadow_color, shadow_offset
            )
            current_y += int(font_sizes['subtitle'] * 1.2)
        current_y += int(padding * 0.5)
    
    # Дисклеймер внизу
    if disclaimer:
        disclaimer_lines = wrap_text_canvas(canvas, disclaimer, disclaimer_font, text_max_width)
        shadow_offset = max(1, font_sizes['disclaimer'] // 35)
        
        # Рассчитываем высоту дисклеймера
        total_disclaimer_height = len(disclaimer_lines) * int(font_sizes['disclaimer'] * 1.2)
        disclaimer_y = height - padding - total_disclaimer_height + font_sizes['disclaimer']
        
        for line in disclaimer_lines:
            draw_text_with_shadow_canvas(
                canvas, line, padding, disclaimer_y,
                disclaimer_font, gray_color, light_shadow_color, shadow_offset
            )
            disclaimer_y += int(font_sizes['disclaimer'] * 1.2)
    
    # Получаем изображение
    image = surface.makeImageSnapshot()
    
    # Конвертируем в PNG
    png_data = image.encodeToData(skia.kPNG)
    
    return png_data.data()

@app.route('/')
def home():
    """API информация"""
    return jsonify({
        'name': 'Image Text Overlay API',
        'version': '2.0.0',
        'status': 'Production Ready',
        'renderer': 'Skia Canvas',
        'features': [
            'Canvas-рендеринг высокого качества',
            'Полная поддержка кириллицы и Unicode',
            'Адаптивное масштабирование шрифтов',
            'Поддержка любых размеров изображений',
            'Автоматическая корректировка по соотношению сторон'
        ],
        'endpoints': {
            'POST /generate/<format>': 'Генерация изображения',
            'POST /generate/custom?width=800&height=600': 'Кастомные размеры',
            'GET /formats': 'Доступные форматы',
            'GET /': 'Информация об API'
        },
        'formats': list(FORMATS.keys()),
        'limits': {
            'min_size': '100x100',
            'max_size': '4000x4000',
            'max_file_size': '10MB'
        }
    })

@app.route('/formats')
def get_formats():
    """Получить доступные форматы"""
    return jsonify({
        'formats': FORMATS,
        'description': {
            'vk-square': 'Квадратный формат для постов VK',
            'vk-portrait': 'Вертикальный формат для VK',
            'vk-landscape': 'Горизонтальный формат для VK',
            'stories': 'Формат для Stories Instagram/VK',
            'custom': 'Кастомный размер (укажите width и height в query параметрах)'
        }
    })

@app.route('/generate/<format_name>', methods=['POST'])
def generate_image_endpoint(format_name):
    """Генерировать изображение с Canvas"""
    try:
        # Определяем размеры изображения
        if format_name == 'custom':
            # Кастомные размеры из параметров запроса
            width = int(request.args.get('width', 800))
            height = int(request.args.get('height', 600))
        elif format_name in FORMATS:
            # Предустановленные форматы
            width = FORMATS[format_name]['width']
            height = FORMATS[format_name]['height']
        else:
            return jsonify({'error': 'Неподдерживаемый формат', 'available_formats': list(FORMATS.keys())}), 400
        
        # Ограничения на размеры
        if width < 100 or width > 4000 or height < 100 or height > 4000:
            return jsonify({'error': 'Размеры должны быть от 100x100 до 4000x4000 пикселей'}), 400
        
        # Проверяем наличие изображения
        if 'image' not in request.files:
            return jsonify({'error': 'Изображение не загружено'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
        
        # Получаем параметры
        logo_text = request.form.get('logoText', '')
        title = request.form.get('title', '')
        subtitle = request.form.get('subtitle', '')
        disclaimer = request.form.get('disclaimer', '')
        logo_url = request.form.get('logoUrl', '')
        
        print(f"Canvas генерация: {width}x{height}")
        print(f"Тексты: logoText='{logo_text}', title='{title}', subtitle='{subtitle}', disclaimer='{disclaimer}'")
        
        # Загружаем изображение
        try:
            background_image = Image.open(file.stream)
            print(f"Оригинальное изображение: {background_image.size}, режим: {background_image.mode}")
        except Exception as e:
            return jsonify({'error': f'Ошибка обработки изображения: {str(e)}'}), 400
        
        # Генерируем изображение с Canvas
        png_data = generate_image_canvas(
            background_image, logo_text, title, subtitle, disclaimer, logo_url, width, height
        )
        
        print(f"Canvas изображение сгенерировано, размер данных: {len(png_data)} байт")
        
        # Создаем буфер
        img_buffer = io.BytesIO(png_data)
        img_buffer.seek(0)
        
        return send_file(
            img_buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'generated-{width}x{height}.png'
        )
        
    except Exception as e:
        print(f"Ошибка Canvas генерации: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Ошибка генерации изображения: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)

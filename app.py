from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
import io
import os
import requests

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

def create_font_unicode(size, bold=False):
    """Создать шрифт с максимальной поддержкой Unicode"""
    # Список шрифтов с хорошей поддержкой кириллицы
    font_paths = [
        # Linux (Railway/Docker)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        
        # Альтернативные пути
        "/System/Library/Fonts/Arial Unicode MS.ttf",
        "/System/Library/Fonts/Arial.ttf",
        
        # Fallback
        "arial.ttf",
        "DejaVuSans.ttf"
    ]
    
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, size)
            # Тестируем кириллицу
            test_img = Image.new('RGB', (100, 50), 'white')
            test_draw = ImageDraw.Draw(test_img)
            test_draw.text((0, 0), "Тест кириллицы", font=font, fill='black')
            print(f"Успешно загружен шрифт: {font_path}")
            return font
        except Exception as e:
            print(f"Не удалось загрузить шрифт {font_path}: {e}")
            continue
    
    # Если ничего не найдено, используем дефолтный
    print("Используется дефолтный шрифт")
    return ImageFont.load_default()

def safe_text_unicode(text):
    """Максимально безопасная обработка Unicode текста"""
    if not text:
        return ""
    
    # Если байты, декодируем
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text = text.decode('cp1251')  # Windows кодировка
            except UnicodeDecodeError:
                text = text.decode('utf-8', errors='replace')
    
    # Убираем управляющие символы
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    return str(text).strip()

def get_text_dimensions(text, font):
    """Получить размеры текста безопасно"""
    try:
        # Новый способ для современной Pillow
        bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        try:
            # Старый способ для совместимости
            return ImageDraw.Draw(Image.new('RGB', (1, 1))).textsize(text, font=font)
        except:
            # Примерный расчет
            char_width = font.size * 0.6 if hasattr(font, 'size') else 12
            return len(text) * char_width, font.size if hasattr(font, 'size') else 20

def wrap_text_smart(text, font, max_width):
    """Умная разбивка текста на строки"""
    text = safe_text_unicode(text)
    if not text:
        return []
    
    words = text.split(' ')
    lines = []
    current_line = ''
    
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        text_width, _ = get_text_dimensions(test_line, font)
        
        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
            
            # Если одно слово слишком длинное, разбиваем его
            while current_line:
                test_width, _ = get_text_dimensions(current_line, font)
                if test_width <= max_width:
                    break
                # Разбиваем слово пополам
                split_point = len(current_line) // 2
                lines.append(current_line[:split_point] + '-')
                current_line = current_line[split_point:]
    
    if current_line:
        lines.append(current_line)
    
    return lines

def draw_text_with_outline(draw, text, position, font, fill_color='white', outline_color='black', outline_width=2):
    """Нарисовать текст с контуром для лучшей читаемости"""
    text = safe_text_unicode(text)
    if not text:
        return
        
    x, y = position
    
    try:
        # Рисуем контур (несколько раз со смещением)
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
        
        # Рисуем основной текст
        draw.text((x, y), text, font=font, fill=fill_color)
        
    except Exception as e:
        print(f"Ошибка отрисовки текста '{text}': {e}")
        # Fallback - простая тень
        try:
            draw.text((x + 2, y + 2), text, font=font, fill=outline_color)
            draw.text((x, y), text, font=font, fill=fill_color)
        except:
            print("Критическая ошибка отрисовки текста")

def generate_image_adaptive(background_image, logo_text, title, subtitle, disclaimer, logo_url, width, height):
    """Генерировать изображение с адаптивным масштабированием"""
    
    # Безопасная обработка всех текстов
    logo_text = safe_text_unicode(logo_text)
    title = safe_text_unicode(title)
    subtitle = safe_text_unicode(subtitle)
    disclaimer = safe_text_unicode(disclaimer)
    
    # Вычисляем адаптивные размеры шрифтов
    font_sizes = calculate_adaptive_font_sizes(width, height)
    padding = font_sizes['padding']
    
    print(f"Генерируем {width}x{height}, шрифты: {font_sizes}")
    print(f"Тексты: logo='{logo_text}', title='{title}', subtitle='{subtitle}', disclaimer='{disclaimer}'")
    
    # Изменяем размер фонового изображения
    background = background_image.resize((width, height), Image.Resampling.LANCZOS)
    background = background.convert('RGBA')
    
    # Создаем затемняющий слой
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    # Градиентное затемнение
    for y in range(height):
        alpha = int(76 + (153 - 76) * y / height)  # От 30% до 60%
        overlay_draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))
    
    # Накладываем затемнение
    background = Image.alpha_composite(background, overlay)
    draw = ImageDraw.Draw(background)
    
    # Создаем шрифты с адаптивными размерами
    logo_font = create_font_unicode(font_sizes['logo_text'], bold=True)
    title_font = create_font_unicode(font_sizes['title'], bold=True)
    subtitle_font = create_font_unicode(font_sizes['subtitle'], bold=False)
    disclaimer_font = create_font_unicode(font_sizes['disclaimer'], bold=False)
    
    current_y = padding
    text_max_width = width - (padding * 2)
    
    # Загрузка логотипа-изображения
    if logo_url:
        try:
            response = requests.get(logo_url, timeout=5)
            if response.status_code == 200:
                logo_image = Image.open(io.BytesIO(response.content))
                logo_size = int(width * 0.12)  # 12% от ширины
                
                logo_image.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                if logo_image.mode == 'RGBA':
                    background.paste(logo_image, (padding, current_y), logo_image)
                else:
                    background.paste(logo_image, (padding, current_y))
                
                current_y += logo_image.height + int(padding * 0.5)
        except Exception as e:
            print(f"Ошибка загрузки логотипа: {e}")
    
    # Логотип-текст (например "YANGO")
    if logo_text:
        outline_width = max(2, font_sizes['logo_text'] // 20)
        draw_text_with_outline(
            draw, logo_text, (padding, current_y), 
            logo_font, 'white', 'black', outline_width
        )
        _, text_height = get_text_dimensions(logo_text, logo_font)
        current_y += int(text_height * 1.2) + int(padding * 0.5)
    
    # Заголовок
    if title:
        title_lines = wrap_text_smart(title, title_font, text_max_width)
        outline_width = max(1, font_sizes['title'] // 30)
        
        for line in title_lines:
            draw_text_with_outline(
                draw, line, (padding, current_y), 
                title_font, 'white', 'black', outline_width
            )
            _, text_height = get_text_dimensions(line, title_font)
            current_y += int(text_height * 1.2)
        current_y += int(padding * 0.3)
    
    # Подзаголовок
    if subtitle:
        subtitle_lines = wrap_text_smart(subtitle, subtitle_font, text_max_width)
        outline_width = max(1, font_sizes['subtitle'] // 35)
        
        for line in subtitle_lines:
            draw_text_with_outline(
                draw, line, (padding, current_y), 
                subtitle_font, 'white', 'black', outline_width
            )
            _, text_height = get_text_dimensions(line, subtitle_font)
            current_y += int(text_height * 1.2)
        current_y += int(padding * 0.5)
    
    # Дисклеймер внизу
    if disclaimer:
        disclaimer_lines = wrap_text_smart(disclaimer, disclaimer_font, text_max_width)
        
        # Рассчитываем высоту дисклеймера
        total_disclaimer_height = 0
        for line in disclaimer_lines:
            _, text_height = get_text_dimensions(line, disclaimer_font)
            total_disclaimer_height += int(text_height * 1.2)
        
        disclaimer_y = height - padding - total_disclaimer_height
        outline_width = max(1, font_sizes['disclaimer'] // 40)
        
        for line in disclaimer_lines:
            draw_text_with_outline(
                draw, line, (padding, disclaimer_y), 
                disclaimer_font, '#CCCCCC', 'black', outline_width
            )
            _, text_height = get_text_dimensions(line, disclaimer_font)
            disclaimer_y += int(text_height * 1.2)
    
    return background.convert('RGB')

@app.route('/')
def home():
    """API информация"""
    return jsonify({
        'name': 'Image Text Overlay API',
        'version': '2.1.0',
        'status': 'Production Ready',
        'renderer': 'PIL with Enhanced Unicode Support',
        'features': [
            'Улучшенная поддержка кириллицы и Unicode',
            'Адаптивное масштабирование шрифтов',
            'Умная разбивка текста на строки',
            'Контурный текст для лучшей читаемости',
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

@app.route('/health')
def health_check():
    """Проверка здоровья приложения"""
    try:
        # Тестируем создание изображения
        test_img = Image.new('RGB', (100, 100), 'white')
        test_font = create_font_unicode(20)
        
        return jsonify({
            'status': 'healthy',
            'pil_version': Image.__version__ if hasattr(Image, '__version__') else 'unknown',
            'unicode_test': 'Тест кириллицы: успешно'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/generate/<format_name>', methods=['POST'])
def generate_image_endpoint(format_name):
    """Генерировать изображение"""
    try:
        # Определяем размеры изображения
        if format_name == 'custom':
            width = int(request.args.get('width', 800))
            height = int(request.args.get('height', 600))
        elif format_name in FORMATS:
            width = FORMATS[format_name]['width']
            height = FORMATS[format_name]['height']
        else:
            return jsonify({
                'error': 'Неподдерживаемый формат', 
                'available_formats': list(FORMATS.keys())
            }), 400
        
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
        
        print(f"Запрос на генерацию: {width}x{height}")
        
        # Загружаем изображение
        try:
            background_image = Image.open(file.stream)
            print(f"Загружено изображение: {background_image.size}, режим: {background_image.mode}")
        except Exception as e:
            return jsonify({'error': f'Ошибка обработки изображения: {str(e)}'}), 400
        
        # Генерируем изображение
        result_image = generate_image_adaptive(
            background_image, logo_text, title, subtitle, disclaimer, logo_url, width, height
        )
        
        print(f"Изображение сгенерировано: {result_image.size}")
        
        # Сохраняем в буфер
        img_buffer = io.BytesIO()
        result_image.save(img_buffer, format='PNG', quality=95, optimize=True)
        img_buffer.seek(0)
        
        return send_file(
            img_buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'generated-{width}x{height}.png'
        )
        
    except Exception as e:
        print(f"Ошибка генерации: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Ошибка генерации изображения: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)

# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import os
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Конфигурация
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB

# Папка для шрифтов
FONTS_DIR = Path("fonts")
FONTS_DIR.mkdir(exist_ok=True)

# Пресеты для размеров
SIZE_PRESETS = {
    "600x600": {
        "name": "square_small",
        "default_font_size": 28,
        "max_text_width": 540,
        "default_position": {"x": 50, "y": 85},
        "padding": 20
    },
    "1080x1350": {
        "name": "instagram_portrait", 
        "default_font_size": 48,
        "max_text_width": 972,
        "default_position": {"x": 50, "y": 88},
        "padding": 35
    },
    "1080x607": {
        "name": "facebook_landscape",
        "default_font_size": 42,
        "max_text_width": 972,
        "default_position": {"x": 50, "y": 82},
        "padding": 30
    }
}

def get_size_preset(width, height):
    """Определяет пресет для размера изображения"""
    size_key = f"{width}x{height}"
    
    if size_key in SIZE_PRESETS:
        return SIZE_PRESETS[size_key]
    
    # Приблизительное совпадение ±5%
    for preset_size, config in SIZE_PRESETS.items():
        preset_width, preset_height = map(int, preset_size.split('x'))
        width_diff = abs(width - preset_width) / preset_width
        height_diff = abs(height - preset_height) / preset_height
        
        if width_diff <= 0.05 and height_diff <= 0.05:
            return config
    
    # Динамический пресет
    aspect_ratio = width / height
    area = width * height
    base_font_size = max(20, min(80, int((area ** 0.5) / 25)))
    
    return {
        "name": f"custom_{width}x{height}",
        "default_font_size": base_font_size,
        "max_text_width": int(width * 0.9),
        "default_position": {"x": 50, "y": 85 if aspect_ratio < 1.2 else 80},
        "padding": max(15, int(min(width, height) * 0.03))
    }

def load_font(font_name="arial", font_size=30):
    """Загружает шрифт с поддержкой Unicode"""
    try:
        # Пользовательские шрифты
        custom_font_path = FONTS_DIR / f"{font_name}.ttf"
        if custom_font_path.exists():
            return ImageFont.truetype(str(custom_font_path), font_size, encoding='utf-8')
        
        # Системные шрифты с поддержкой Unicode
        system_fonts = {
            "arial": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/Arial Unicode MS.ttf",
                "/System/Library/Fonts/Arial.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/calibri.ttf"
            ],
            "roboto": [
                "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
                "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:/Windows/Fonts/segoeui.ttf"
            ]
        }
        
        font_paths = system_fonts.get(font_name.lower(), system_fonts["arial"])
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, font_size, encoding='utf-8')
                except (OSError, UnicodeError):
                    continue
        
        # Fallback к дефолтному шрифту
        return ImageFont.load_default()
        
    except Exception as e:
        print(f"Ошибка загрузки шрифта: {e}")
        return ImageFont.load_default()

def calculate_optimal_font_size(text, max_width, base_font_size, font_name="arial"):
    """Вычисляет оптимальный размер шрифта с поддержкой Unicode"""
    try:
        lines = text.split('\n')
        longest_line = max(lines, key=len) if lines else text
        
        font_size = base_font_size
        
        while font_size > 12:
            font = load_font(font_name, font_size)
            temp_img = Image.new('RGB', (1, 1))
            temp_draw = ImageDraw.Draw(temp_img)
            
            try:
                bbox = temp_draw.textbbox((0, 0), longest_line, font=font)
                text_width = bbox[2] - bbox[0]
                
                if text_width <= max_width:
                    break
            except (UnicodeError, OSError):
                # Если проблема с кодировкой, уменьшаем размер
                pass
                
            font_size -= 2
        
        return max(font_size, 12)
    except Exception:
        return base_font_size

def process_image_with_auto_sizing(image_data, text_config):
    """Обрабатывает изображение с автоопределением размеров"""
    try:
        # Декодируем изображение
        if isinstance(image_data, str):
            if image_data.startswith('data:image'):
                header, encoded = image_data.split(',', 1)
                image_bytes = base64.b64decode(encoded)
            else:
                image_bytes = base64.b64decode(image_data)
        else:
            image_bytes = image_data
        
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size
        preset = get_size_preset(width, height)
        
        # Конвертируем в RGBA
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        draw = ImageDraw.Draw(image)
        
        # Параметры текста с безопасной обработкой Unicode
        text = str(text_config.get('text', ''))
        
        # Проверяем и очищаем текст от проблемных символов
        try:
            # Простая нормализация без внешних библиотек
            text = text.encode('utf-8').decode('utf-8')
        except:
            pass
        
        font_name = text_config.get('fontName', 'arial')
        
        # Автоматический размер шрифта или пользовательский
        if 'fontSize' in text_config and text_config['fontSize']:
            font_size = int(text_config['fontSize'])
        else:
            font_size = calculate_optimal_font_size(
                text, preset['max_text_width'], preset['default_font_size'], font_name
            )
        
        # Цвета с безопасным преобразованием
        font_color = text_config.get('fontColor', [255, 255, 255])
        if isinstance(font_color, list) and len(font_color) >= 3:
            font_color = tuple(font_color[:4])  # RGBA или RGB
        else:
            font_color = (255, 255, 255)
            
        bg_color = text_config.get('bgColor', [0, 0, 0, 180])
        if isinstance(bg_color, list) and len(bg_color) >= 3:
            bg_color = tuple(bg_color[:4])
        else:
            bg_color = (0, 0, 0, 180)
            
        transparent_bg = text_config.get('transparentBg', False)
        
        # Позиция
        pos_x = float(text_config.get('posX', preset['default_position']['x']))
        pos_y = float(text_config.get('posY', preset['default_position']['y']))
        
        font = load_font(font_name, font_size)
        
        # Обрабатываем многострочный текст
        lines = text.split('\n')
        line_heights = []
        line_widths = []
        
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_widths.append(bbox[2] - bbox[0])
                line_heights.append(bbox[3] - bbox[1])
            except (UnicodeError, OSError):
                # Если проблема с отдельной линией, используем приблизительные размеры
                line_widths.append(len(line) * font_size * 0.6)
                line_heights.append(font_size)
        
        max_width = max(line_widths) if line_widths else 0
        total_height = sum(line_heights) + (len(lines) - 1) * (font_size * 0.2)
        
        # Позиция
        x = int((width * pos_x) / 100)
        y = int((height * pos_y) / 100)
        
        # Фон для текста
        if not transparent_bg and text.strip():
            padding = preset['padding']
            bg_bbox = (
                x - max_width//2 - padding,
                y - int(total_height//2) - padding//2,
                x + max_width//2 + padding,
                y + int(total_height//2) + padding//2
            )
            
            overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            corner_radius = min(padding, 15)
            overlay_draw.rounded_rectangle(bg_bbox, corner_radius, fill=bg_color)
            image = Image.alpha_composite(image, overlay)
            draw = ImageDraw.Draw(image)
        
        # Рисуем текст
        current_y = y - int(total_height//2)
        shadow_offset = max(1, font_size // 20)
        
        for i, line in enumerate(lines):
            if not line.strip():
                current_y += line_heights[i] if i < len(line_heights) else font_size
                continue
                
            line_width = line_widths[i]
            line_x = x - line_width//2
            
            try:
                # Тень
                if not transparent_bg:
                    draw.text(
                        (line_x + shadow_offset, current_y + shadow_offset), 
                        line, font=font, fill=(0, 0, 0, 100)
                    )
                
                # Основной текст
                draw.text((line_x, current_y), line, font=font, fill=font_color)
            except (UnicodeError, OSError) as e:
                print(f"Ошибка рисования текста: {e}")
                # Пропускаем проблемную строку
                pass
                
            current_y += line_heights[i] + int(font_size * 0.2)
        
        # Конвертируем для сохранения
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        
        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG', quality=95, optimize=True)
        output_buffer.seek(0)
        
        return output_buffer, {
            "detected_size": f"{width}x{height}",
            "preset_used": preset['name'],
            "calculated_font_size": font_size,
            "position": {"x": pos_x, "y": pos_y},
            "text_lines": len(lines)
        }
        
    except Exception as e:
        print(f"Детальная ошибка: {e}")
        raise Exception(f"Ошибка обработки изображения: {str(e)}")

# API Routes
@app.route('/', methods=['GET'])
def home():
    """API информация"""
    return jsonify({
        "service": "Text Overlay API",
        "version": "2.1.0",
        "status": "running",
        "unicode_support": True,
        "supported_sizes": list(SIZE_PRESETS.keys()),
        "endpoints": {
            "POST /overlay": "Наложение текста",
            "POST /upload-font": "Загрузка шрифта",
            "GET /fonts": "Список шрифтов",
            "DELETE /fonts/{name}": "Удаление шрифта",
            "GET /health": "Статус сервиса"
        }
    })

@app.route('/overlay', methods=['POST'])
def overlay_text():
    """Основной endpoint наложения текста"""
    try:
        # Детальная обработка входящих данных
        content_type = request.content_type or ''
        
        # Логирование для отладки
        print(f"Content-Type: {content_type}")
        print(f"Request data length: {len(request.data)}")
        
        # Попытка получить JSON данные
        data = None
        if request.is_json:
            data = request.get_json()
        elif 'application/json' in content_type:
            data = request.get_json(force=True)
        else:
            # Последняя попытка - парсим как JSON
            try:
                import json
                raw_data = request.data.decode('utf-8')
                data = json.loads(raw_data)
            except Exception as e:
                return jsonify({
                    "error": f"Ошибка парсинга JSON: {str(e)}", 
                    "content_type": content_type,
                    "data_preview": str(request.data[:100])
                }), 400
        
        if not data:
            return jsonify({"error": "Пустые данные"}), 400
        
        # Валидация обязательных полей
        if 'image' not in data:
            return jsonify({
                "error": "Поле 'image' обязательно",
                "received_fields": list(data.keys()) if isinstance(data, dict) else "not_dict"
            }), 400
        
        if 'text' not in data or not str(data['text']).strip():
            return jsonify({
                "error": "Поле 'text' обязательно и не может быть пустым",
                "received_text": data.get('text', 'missing')
            }), 400
        
        # Валидация изображения
        image_data = data['image']
        if not isinstance(image_data, str):
            return jsonify({"error": "Поле 'image' должно быть строкой"}), 400
        
        if len(image_data) < 100:
            return jsonify({"error": "Изображение слишком маленькое или повреждено"}), 400
        
        result_buffer, metadata = process_image_with_auto_sizing(image_data, data)
        result_base64 = base64.b64encode(result_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": f"data:image/png;base64,{result_base64}",
            "metadata": metadata
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"Ошибка API: {error_msg}")
        return jsonify({
            "success": False, 
            "error": error_msg,
            "debug_info": {
                "content_type": getattr(request, 'content_type', 'unknown'),
                "method": request.method,
                "data_length": len(request.data) if request.data else 0
            }
        }), 500

@app.route('/upload-font', methods=['POST'])
def upload_font():
    """Загрузка шрифта"""
    try:
        if 'font' not in request.files:
            return jsonify({"error": "Файл шрифта обязателен"}), 400
        
        file = request.files['font']
        font_name = request.form.get('name', file.filename.split('.')[0])
        
        if not file.filename.lower().endswith(('.ttf', '.otf')):
            return jsonify({"error": "Поддерживаются только TTF и OTF"}), 400
        
        font_path = FONTS_DIR / f"{font_name}.ttf"
        file.save(font_path)
        
        # Тестируем шрифт
        try:
            ImageFont.truetype(str(font_path), 24, encoding='utf-8')
        except Exception:
            font_path.unlink()
            return jsonify({"error": "Невозможно загрузить шрифт"}), 400
        
        return jsonify({
            "success": True,
            "message": f"Шрифт '{font_name}' загружен",
            "font_name": font_name
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fonts', methods=['GET'])
def list_fonts():
    """Список шрифтов"""
    try:
        system_fonts = ["arial", "roboto", "helvetica"]
        custom_fonts = [f.stem for f in FONTS_DIR.glob("*.ttf")]
        
        return jsonify({
            "system_fonts": system_fonts,
            "custom_fonts": custom_fonts,
            "total": len(system_fonts) + len(custom_fonts),
            "unicode_support": True
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fonts/<font_name>', methods=['DELETE'])
def delete_font(font_name):
    """Удаление шрифта"""
    try:
        font_path = FONTS_DIR / f"{font_name}.ttf"
        
        if not font_path.exists():
            return jsonify({"error": "Шрифт не найден"}), 404
        
        font_path.unlink()
        return jsonify({"success": True, "message": f"Шрифт '{font_name}' удален"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья"""
    return jsonify({
        "status": "healthy",
        "fonts_available": len(list(FONTS_DIR.glob("*.ttf"))) + 3,
        "unicode_support": True,
        "version": "2.1.0"
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

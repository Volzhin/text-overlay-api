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
        
        # Проверяем размер изображения
        if len(image_bytes) < 1000:  # Минимум 1KB
            raise Exception("Изображение слишком маленькое. Минимальный размер: 1KB")
        
        # Открываем изображение с обработкой ошибок
        try:
            from PIL import ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True  # Разрешаем загрузку поврежденных изображений
            
            image = Image.open(io.BytesIO(image_bytes))
            image.load()  # Принудительная загрузка для проверки
            
        except Exception as img_error:
            raise Exception(f"Не удается открыть изображение: {str(img_error)}. Проверьте корректность base64 данных")
        
        width, height = image.size
        
        # Проверяем минимальные размеры
        if width < 10 or height < 10:
            raise Exception(f"Изображение слишком маленькое: {width}x{height}. Минимум: 10x10 пикселей")
        
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
        
        # Дополнительные параметры для улучшения качества
        outline_width = int(text_config.get('outlineWidth', 3))
        outline_color = tuple(text_config.get('outlineColor', [0, 0, 0, 255]))
        
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
        
        print(f"DEBUG: Image size: {width}x{height}")
        print(f"DEBUG: Text position: x={x}, y={y} (from {pos_x}%, {pos_y}%)")
        print(f"DEBUG: Font size: {font_size}")
        print(f"DEBUG: Text lines: {len(lines)}")
        print(f"DEBUG: Max text width: {max_width}")
        print(f"DEBUG: Total text height: {total_height}")
        
        # Фон для текста
        if not transparent_bg and text.strip():
            padding = preset['padding']
            bg_bbox = (
                max(0, x - max_width//2 - padding),
                max(0, y - int(total_height//2) - padding//2),
                min(width, x + max_width//2 + padding),
                min(height, y + int(total_height//2) + padding//2)
            )
            
            print(f"DEBUG: Background bbox: {bg_bbox}")
            
            overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            corner_radius = min(padding, 15)
            overlay_draw.rounded_rectangle(bg_bbox, corner_radius, fill=bg_color)
            image = Image.alpha_composite(image, overlay)
            draw = ImageDraw.Draw(image)
        
        # Рисуем текст с улучшенной обводкой
        current_y = y - int(total_height//2)
        
        print(f"DEBUG: Starting text drawing at y={current_y}")
        
        for i, line in enumerate(lines):
            if not line.strip():
                current_y += line_heights[i] if i < len(line_heights) else font_size
                continue
                
            line_width = line_widths[i]
            line_x = x - line_width//2
            
            print(f"DEBUG: Drawing line '{line}' at position ({line_x}, {current_y})")
            
            try:
                # Убедимся что координаты в пределах изображения
                if line_x < 0 or current_y < 0 or line_x > width or current_y > height:
                    print(f"WARNING: Text position outside image bounds: ({line_x}, {current_y})")
                
                # Простая обводка (если нужна)
                if outline_width > 0:
                    for adj_x in range(-outline_width, outline_width + 1):
                        for adj_y in range(-outline_width, outline_width + 1):
                            if adj_x == 0 and adj_y == 0:
                                continue
                            draw.text(
                                (line_x + adj_x, current_y + adj_y), 
                                line, font=font, fill=outline_color[:3]  # Только RGB
                            )
                
                # Основной текст - ОБЯЗАТЕЛЬНО рисуем
                draw.text((line_x, current_y), line, font=font, fill=font_color[:3])  # Только RGB
                print(f"DEBUG: Text drawn successfully at ({line_x}, {current_y})")
                
            except Exception as e:
                print(f"ERROR drawing text: {e}")
                # Попробуем без обводки
                try:
                    draw.text((line_x, current_y), line, font=font, fill=(255, 255, 255))
                    print(f"DEBUG: Fallback text drawn")
                except Exception as e2:
                    print(f"ERROR even with fallback: {e2}")
                
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
        
        # Опция для выбора формата вывода
        include_prefix = data.get('includeDataUrl', False)
        
        response_data = {
            "success": True,
            "metadata": metadata
        }
        
        if include_prefix:
            response_data["image"] = f"data:image/png;base64,{result_base64}"
        else:
            response_data["image"] = result_base64
            
        return jsonify(response_data)
        
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

@app.route('/simple-overlay', methods=['POST'])
def simple_overlay():
    """Простое наложение текста без сложной логики"""
    try:
        data = request.get_json(force=True)
        
        # Декодируем изображение
        image_data = data['image']
        if image_data.startswith('data:image'):
            header, encoded = image_data.split(',', 1)
            image_bytes = base64.b64decode(encoded)
        else:
            image_bytes = base64.b64decode(image_data)
        
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        
        image = Image.open(io.BytesIO(image_bytes))
        # Конвертируем в RGB для простоты
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # Простые параметры с безопасной обработкой Unicode
        text = str(data.get('text', 'HELLO WORLD'))
        
        # Очищаем текст от проблемных символов
        try:
            # Проверяем что текст можно корректно обработать
            text.encode('utf-8')
        except:
            text = 'TEXT_ERROR'
        
        font_size = data.get('fontSize', min(width, height) // 8)
        
        # Позиция по умолчанию - центр верхней части
        x = data.get('x', width // 2)
        y = data.get('y', height // 4)
        
        print(f"Drawing text '{text}' at ({x}, {y}) with size {font_size} on {width}x{height} image")
        
        # Загружаем шрифт с поддержкой Unicode
        try:
            # Пробуем системные шрифты с Unicode поддержкой
            unicode_fonts = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
            ]
            
            font = None
            for font_path in unicode_fonts:
                if os.path.exists(font_path):
                    try:
                        font = ImageFont.truetype(font_path, font_size)
                        # Тестируем шрифт с нашим текстом
                        test_bbox = draw.textbbox((0, 0), text, font=font)
                        break
                    except:
                        continue
            
            if font is None:
                font = ImageFont.load_default()
                
        except Exception as e:
            print(f"Font loading error: {e}")
            font = ImageFont.load_default()
        
        # Получаем размеры текста для центрирования
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            # Если не можем получить размеры, используем приблизительные
            text_width = len(text) * font_size * 0.6
            text_height = font_size
        
        # Центрируем текст
        final_x = int(x - text_width // 2)
        final_y = int(y - text_height // 2)
        
        # Убеждаемся что текст в границах изображения
        final_x = max(10, min(final_x, width - int(text_width) - 10))
        final_y = max(10, min(final_y, height - int(text_height) - 10))
        
        print(f"Final position: ({final_x}, {final_y}), text size: {text_width}x{text_height}")
        
        # Рисуем ОЧЕНЬ контрастный текст
        outline_size = max(3, font_size // 16)
        
        try:
            # Сначала пробуем нарисовать с нормальным шрифтом
            draw.text((final_x, final_y), text, font=font, fill=(255, 255, 255))
            print("Text drawn with normal font")
            
        except Exception as e:
            print(f"Normal font failed: {e}")
            try:
                # Пробуем с дефолтным шрифтом
                default_font = ImageFont.load_default()
                draw.text((final_x, final_y), text, font=default_font, fill=(255, 255, 255))
                print("Text drawn with default font")
                
            except Exception as e2:
                print(f"Default font failed: {e2}")
                try:
                    # Последний fallback - рисуем без шрифта (PIL должен использовать встроенный)
                    draw.text((final_x, final_y), "FALLBACK TEXT", fill=(255, 255, 255))
                    print("Fallback text drawn")
                    
                except Exception as e3:
                    print(f"Even fallback failed: {e3}")
                    # Если ничего не работает - рисуем белый прямоугольник вместо текста
                    draw.rectangle([final_x, final_y, final_x + 200, final_y + 50], fill=(255, 255, 255))
                    print("White rectangle drawn as ultimate fallback")
        
        # Добавляем красный прямоугольник для отладки
        debug_rect = [
            final_x - 5, final_y - 5,
            final_x + int(text_width) + 5, final_y + int(text_height) + 5
        ]
        draw.rectangle(debug_rect, outline=(255, 0, 0), width=3)
        
        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG', quality=95)
        output_buffer.seek(0)
        
        result_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": result_base64,
            "debug": {
                "image_size": f"{width}x{height}",
                "text_position": f"({final_x}, {final_y})",
                "text_size": f"{text_width}x{text_height}",
                "font_size": font_size,
                "text": text,
                "text_length": len(text)
            }
        })
        
    except Exception as e:
        print(f"Error in simple_overlay: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/test-fonts', methods=['GET'])
def test_fonts():
    """Тестирует доступные шрифты"""
    try:
        results = {}
        
        # Тестируем системные шрифты
        test_fonts = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf"
        ]
        
        for font_path in test_fonts:
            try:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 24)
                    results[font_path] = "Available"
                else:
                    results[font_path] = "Not found"
            except Exception as e:
                results[font_path] = f"Error: {str(e)}"
        
        # Тестируем дефолтный шрифт
        try:
            default_font = ImageFont.load_default()
            results["default_font"] = "Available"
        except Exception as e:
            results["default_font"] = f"Error: {str(e)}"
        
        return jsonify({
            "font_test_results": results,
            "platform": os.name
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def smart_text_wrap(text, max_width, font, draw):
    """Умное разбиение текста на строки"""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        # Проверяем поместится ли слово в текущую строку
        test_line = ' '.join(current_line + [word])
        try:
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
        except:
            # Если не можем получить размер, используем приблизительный расчет
            line_width = len(test_line) * (font.size if hasattr(font, 'size') else 20) * 0.6
        
        if line_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                # Слово слишком длинное - разбиваем его
                lines.append(word)
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def get_safe_font(font_size):
    """Получение безопасного шрифта с поддержкой кириллицы"""
    # Шрифты с хорошей поддержкой кириллицы
    cyrillic_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
    ]
    
    for font_path in cyrillic_fonts:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
                # Тестируем с кириллицей
                test_img = Image.new('RGB', (100, 100))
                test_draw = ImageDraw.Draw(test_img)
                test_draw.textbbox((0, 0), "Тест", font=font)
                return font
            except:
                continue
    
    # Fallback к дефолтному
    return ImageFont.load_default()

@app.route('/smart-overlay', methods=['POST'])
def smart_overlay():
    """Умное наложение текста с автоматическим разбиением и позиционированием"""
    try:
        data = request.get_json(force=True)
        
        # Декодируем изображение
        image_data = data['image']
        if image_data.startswith('data:image'):
            header, encoded = image_data.split(',', 1)
            image_bytes = base64.b64decode(encoded)
        else:
            image_bytes = base64.b64decode(image_data)
        
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        draw = ImageDraw.Draw(image)
        width, height = image.size
        
        # Параметры
        text = str(data.get('text', 'Пример текста'))
        base_font_size = data.get('fontSize', min(width, height) // 15)
        position = data.get('position', 'center')  # top, center, bottom
        margin = data.get('margin', min(width, height) // 20)
        
        # Цвета
        text_color = tuple(data.get('textColor', [255, 255, 255]))[:3]
        outline_color = tuple(data.get('outlineColor', [0, 0, 0]))[:3]
        bg_color = tuple(data.get('backgroundColor', [0, 0, 0, 128]))
        use_background = data.get('useBackground', True)
        
        print(f"Processing text: '{text}' on {width}x{height} image")
        
        # Получаем безопасный шрифт
        font = get_safe_font(base_font_size)
        
        # Максимальная ширина текста (с отступами)
        max_text_width = width - (margin * 2)
        
        # Разбиваем текст на строки
        lines = smart_text_wrap(text, max_text_width, font, draw)
        
        # Вычисляем размеры текстового блока
        line_heights = []
        line_widths = []
        
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_widths.append(bbox[2] - bbox[0])
                line_heights.append(bbox[3] - bbox[1])
            except:
                # Fallback расчет
                char_width = base_font_size * 0.6
                line_widths.append(len(line) * char_width)
                line_heights.append(base_font_size)
        
        total_text_width = max(line_widths) if line_widths else 0
        line_spacing = max(line_heights) * 0.3 if line_heights else base_font_size * 0.3
        total_text_height = sum(line_heights) + (len(lines) - 1) * line_spacing
        
        # Определяем позицию текстового блока
        if position == 'top':
            block_y = margin + total_text_height // 2
        elif position == 'bottom':
            block_y = height - margin - total_text_height // 2
        else:  # center
            block_y = height // 2
        
        block_x = width // 2
        
        # Рисуем фон для текста (если нужен)
        if use_background and len(bg_color) >= 3:
            padding = margin // 2
            bg_rect = [
                block_x - total_text_width // 2 - padding,
                int(block_y - total_text_height // 2 - padding),
                block_x + total_text_width // 2 + padding,
                int(block_y + total_text_height // 2 + padding)
            ]
            
            # Создаем полупрозрачный фон
            if len(bg_color) == 4:
                overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.rounded_rectangle(bg_rect, radius=padding//3, fill=bg_color)
                # Конвертируем в RGBA для наложения
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                image = Image.alpha_composite(image, overlay)
                # Возвращаем в RGB
                if image.mode == 'RGBA':
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[-1] if len(image.split()) == 4 else None)
                    image = rgb_image
                draw = ImageDraw.Draw(image)
            else:
                draw.rounded_rectangle(bg_rect, radius=padding//3, fill=bg_color[:3])
        
        # Рисуем текст строка за строкой
        current_y = block_y - total_text_height // 2
        
        for i, line in enumerate(lines):
            if not line.strip():
                current_y += line_heights[i] if i < len(line_heights) else base_font_size
                continue
            
            line_width = line_widths[i]
            line_x = block_x - line_width // 2
            
            # Убеждаемся что координаты валидны
            line_x = max(margin, min(line_x, width - line_width - margin))
            current_y = max(0, min(current_y, height - base_font_size))
            
            try:
                # Рисуем обводку
                outline_size = max(1, base_font_size // 20)
                for dx in range(-outline_size, outline_size + 1):
                    for dy in range(-outline_size, outline_size + 1):
                        if dx != 0 or dy != 0:
                            draw.text((line_x + dx, int(current_y) + dy), line, font=font, fill=outline_color)
                
                # Рисуем основной текст
                draw.text((line_x, int(current_y)), line, font=font, fill=text_color)
                
                print(f"Drew line '{line}' at ({line_x}, {current_y})")
                
            except Exception as e:
                print(f"Error drawing line '{line}': {e}")
                # Простой fallback без обводки
                try:
                    draw.text((line_x, int(current_y)), line, fill=text_color)
                except:
                    # Рисуем прямоугольник как индикатор
                    draw.rectangle([line_x, int(current_y), line_x + 100, int(current_y) + 20], fill=text_color)
            
            current_y += line_heights[i] + line_spacing
        
        # Сохраняем результат
        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG', quality=95, optimize=True)
        output_buffer.seek(0)
        
        result_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": result_base64,
            "debug": {
                "image_size": f"{width}x{height}",
                "lines_count": len(lines),
                "lines": lines,
                "position": position,
                "text_block_size": f"{total_text_width}x{total_text_height}",
                "font_size": base_font_size
            }
        })
        
    except Exception as e:
        print(f"Error in smart_overlay: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/simple-text-test', methods=['POST'])
def simple_text_test():
    """Максимально простой тест наложения текста"""
    try:
        data = request.get_json(force=True)
        
        # Создаем простое изображение
        image = Image.new('RGB', (400, 300), color=(100, 150, 200))
        draw = ImageDraw.Draw(image)
        
        text = data.get('text', 'TEST')
        
        # Используем только дефолтный шрифт
        try:
            # Рисуем белый текст без всяких сложностей
            draw.text((50, 50), text, fill=(255, 255, 255))
            draw.text((50, 100), "STATIC TEXT", fill=(255, 255, 255))
            draw.text((50, 150), "123456789", fill=(255, 255, 255))
            
            # Рисуем прямоугольники для проверки
            draw.rectangle([200, 50, 350, 100], fill=(255, 0, 0))  # Красный
            draw.rectangle([200, 120, 350, 170], fill=(0, 255, 0))  # Зеленый
            draw.rectangle([200, 190, 350, 240], fill=(0, 0, 255))  # Синий
            
        except Exception as e:
            print(f"Even simple drawing failed: {e}")
        
        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG')
        output_buffer.seek(0)
        
        result_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": result_base64,
            "message": "Simple test completed"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/create-text-image', methods=['POST'])
def create_text_image():
    """Создает новое изображение с текстом"""
    try:
        data = request.get_json(force=True)
        
        width = data.get('width', 800)
        height = data.get('height', 600)
        text = str(data.get('text', 'HELLO WORLD'))
        font_size = data.get('fontSize', 48)
        bg_color = tuple(data.get('bgColor', [70, 130, 180]))  # Steel blue
        text_color = tuple(data.get('textColor', [255, 255, 255]))  # White
        
        # Создаем изображение
        image = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(image)
        
        # Загружаем шрифт
        try:
            font = load_font('arial', font_size)
        except:
            font = ImageFont.load_default()
        
        # Получаем размеры текста
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            text_width = len(text) * font_size * 0.6
            text_height = font_size
        
        # Центрируем текст
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # Рисуем текст с обводкой
        outline_size = 2
        for dx in range(-outline_size, outline_size + 1):
            for dy in range(-outline_size, outline_size + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
        
        draw.text((x, y), text, font=font, fill=text_color)
        
        # Конвертируем в base64
        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG', quality=95)
        output_buffer.seek(0)
        
        result_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": result_base64,
            "debug": {
                "image_size": f"{width}x{height}",
                "text": text,
                "font_size": font_size
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/generate-test-image', methods=['GET'])
def generate_test_image():
    """Генерирует тестовое изображение 1024x1024"""
    try:
        # Создаем изображение 1024x1024
        width, height = 1024, 1024
        image = Image.new('RGB', (width, height), color='#4A90E2')  # Синий фон
        draw = ImageDraw.Draw(image)
        
        # Добавляем градиент
        for y in range(height):
            alpha = int(255 * (y / height))
            color = (74, 144, 226, alpha)
            draw.line([(0, y), (width, y)], fill=color[:3])
        
        # Добавляем сетку
        grid_size = 128
        for x in range(0, width, grid_size):
            draw.line([(x, 0), (x, height)], fill='white', width=2)
        for y in range(0, height, grid_size):
            draw.line([(0, y), (width, y)], fill='white', width=2)
        
        # Добавляем центральный круг
        center_x, center_y = width // 2, height // 2
        radius = 200
        draw.ellipse([
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius
        ], fill='white', outline='black', width=4)
        
        # Добавляем текст с размерами
        font = load_font('arial', 48)
        size_text = f"{width}x{height}"
        bbox = draw.textbbox((0, 0), size_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = center_x - text_width // 2
        text_y = center_y - 24
        
        # Тень
        draw.text((text_x + 2, text_y + 2), size_text, font=font, fill='black')
        # Основной текст
        draw.text((text_x, text_y), size_text, font=font, fill='white')
        
        # Конвертируем в base64
        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG', quality=95)
        output_buffer.seek(0)
        
        result_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": result_base64,
            "image_with_prefix": f"data:image/png;base64,{result_base64}",
            "size": f"{width}x{height}",
            "message": "Тестовое изображение создано"
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/overlay-raw', methods=['POST'])
def overlay_text_raw():
    """Endpoint наложения текста с возвратом чистого base64"""
    try:
        # Используем ту же логику что и в основном endpoint
        data = overlay_text().get_json()
        
        if data.get('success'):
            # Убираем префикс если он есть
            image_data = data['image']
            if image_data.startswith('data:image'):
                clean_base64 = image_data.split(',', 1)[1]
            else:
                clean_base64 = image_data
                
            return jsonify({
                "success": True,
                "image": clean_base64,
                "metadata": data.get('metadata', {})
            })
        else:
            return jsonify(data), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/test', methods=['POST'])
def test_endpoint():
    """Тестовый endpoint для отладки"""
    try:
        data = request.get_json(force=True)
        
        return jsonify({
            "received_data": {
                "keys": list(data.keys()) if isinstance(data, dict) else "not_dict",
                "image_length": len(data.get('image', '')) if 'image' in data else 0,
                "text_value": data.get('text', 'missing'),
                "has_image": 'image' in data,
                "has_text": 'text' in data
            },
            "content_type": request.content_type,
            "method": request.method
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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

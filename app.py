from flask import Flask, request, jsonify, send_file, render_template_string
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

# HTML шаблон для /process/ страницы
PROCESS_HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Text Overlay Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .form-container {
            padding: 40px;
        }
        
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        .form-group.full-width {
            grid-column: 1 / -1;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #4facfe;
            background: white;
            box-shadow: 0 0 0 3px rgba(79, 172, 254, 0.1);
        }
        
        .file-input-wrapper {
            position: relative;
            overflow: hidden;
            display: inline-block;
            width: 100%;
        }
        
        .file-input-wrapper input[type=file] {
            position: absolute;
            left: -9999px;
        }
        
        .file-input-label {
            display: block;
            padding: 20px;
            border: 2px dashed #4facfe;
            border-radius: 10px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }
        
        .file-input-label:hover {
            background: #e9ecef;
            border-color: #0056b3;
        }
        
        .file-input-label.has-file {
            background: #d4edda;
            border-color: #28a745;
            color: #155724;
        }
        
        .format-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
        }
        
        .format-option {
            position: relative;
        }
        
        .format-option input[type="radio"] {
            position: absolute;
            opacity: 0;
        }
        
        .format-option label {
            display: block;
            padding: 20px 10px;
            text-align: center;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            background: #f8f9fa;
            margin: 0;
            text-transform: none;
            letter-spacing: normal;
            font-weight: 500;
        }
        
        .format-option input[type="radio"]:checked + label {
            background: #4facfe;
            color: white;
            border-color: #4facfe;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.3);
        }
        
        .generate-btn {
            width: 100%;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            border: none;
            padding: 18px 30px;
            font-size: 18px;
            font-weight: 600;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .generate-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(79, 172, 254, 0.3);
        }
        
        .generate-btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .result {
            margin-top: 30px;
            padding: 20px;
            border-radius: 10px;
            display: none;
        }
        
        .result.success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        
        .result.error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        
        .result.loading {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
        }
        
        .result img {
            max-width: 100%;
            border-radius: 10px;
            margin: 15px 0;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        .download-btn {
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin-top: 15px;
            transition: all 0.3s ease;
        }
        
        .download-btn:hover {
            background: #218838;
            transform: translateY(-1px);
        }
        
        @media (max-width: 768px) {
            .form-grid {
                grid-template-columns: 1fr;
                gap: 20px;
            }
            
            .format-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .form-container {
                padding: 20px;
            }
        }
        
        .loader {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #4facfe;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-right: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎨 Image Text Overlay</h1>
            <p>Создавайте красивые изображения с текстом для социальных сетей</p>
        </div>
        
        <div class="form-container">
            <form id="imageForm" enctype="multipart/form-data">
                <div class="form-group full-width">
                    <label>📸 Фоновое изображение</label>
                    <div class="file-input-wrapper">
                        <input type="file" id="image" name="image" accept="image/*" required>
                        <label for="image" class="file-input-label" id="fileLabel">
                            <div>📁 Выберите изображение</div>
                            <small>JPG, PNG, GIF до 10MB</small>
                        </label>
                    </div>
                </div>
                
                <div class="form-group full-width">
                    <label>📐 Формат изображения</label>
                    <div class="format-grid">
                        <div class="format-option">
                            <input type="radio" id="vk-square" name="format" value="vk-square" checked>
                            <label for="vk-square">
                                <div><strong>VK Квадрат</strong></div>
                                <small>600×600</small>
                            </label>
                        </div>
                        <div class="format-option">
                            <input type="radio" id="vk-portrait" name="format" value="vk-portrait">
                            <label for="vk-portrait">
                                <div><strong>VK Портрет</strong></div>
                                <small>1080×1350</small>
                            </label>
                        </div>
                        <div class="format-option">
                            <input type="radio" id="vk-landscape" name="format" value="vk-landscape">
                            <label for="vk-landscape">
                                <div><strong>VK Пейзаж</strong></div>
                                <small>1080×607</small>
                            </label>
                        </div>
                        <div class="format-option">
                            <input type="radio" id="stories" name="format" value="stories">
                            <label for="stories">
                                <div><strong>Stories</strong></div>
                                <small>1080×1920</small>
                            </label>
                        </div>
                    </div>
                </div>
                
                <div class="form-grid">
                    <div class="form-group">
                        <label>🏷️ Логотип-текст</label>
                        <input type="text" name="logoText" placeholder="YANGO" value="YANGO">
                    </div>
                    
                    <div class="form-group">
                        <label>📝 Заголовок</label>
                        <input type="text" name="title" placeholder="Заголовок" value="Заголовок">
                    </div>
                    
                    <div class="form-group">
                        <label>📄 Подзаголовок</label>
                        <input type="text" name="subtitle" placeholder="Подзаголовок" value="Подзаголовок">
                    </div>
                    
                    <div class="form-group">
                        <label>🔗 URL логотипа</label>
                        <input type="url" name="logoUrl" placeholder="https://example.com/logo.png">
                    </div>
                </div>
                
                <div class="form-group">
                    <label>⚠️ Дисклеймер</label>
                    <textarea name="disclaimer" rows="3" placeholder="Дисклеймер">Дисклеймер</textarea>
                </div>
                
                <button type="submit" class="generate-btn" id="generateBtn">
                    🚀 Сгенерировать изображение
                </button>
            </form>
            
            <div id="result" class="result">
                <div id="resultContent"></div>
            </div>
        </div>
    </div>

    <script>
        // Обработка выбора файла
        document.getElementById('image').addEventListener('change', function(e) {
            const fileLabel = document.getElementById('fileLabel');
            const file = e.target.files[0];
            
            if (file) {
                fileLabel.innerHTML = `
                    <div>✅ ${file.name}</div>
                    <small>${(file.size / 1024 / 1024).toFixed(1)} MB</small>
                `;
                fileLabel.classList.add('has-file');
            } else {
                fileLabel.innerHTML = `
                    <div>📁 Выберите изображение</div>
                    <small>JPG, PNG, GIF до 10MB</small>
                `;
                fileLabel.classList.remove('has-file');
            }
        });

        // Обработка формы
        document.getElementById('imageForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const resultDiv = document.getElementById('result');
            const resultContent = document.getElementById('resultContent');
            const generateBtn = document.getElementById('generateBtn');
            
            // Показать загрузку
            resultDiv.className = 'result loading';
            resultDiv.style.display = 'block';
            resultContent.innerHTML = '<div class="loader"></div>Генерируем изображение...';
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<div class="loader"></div>Обработка...';
            
            try {
                const formData = new FormData(this);
                const format = formData.get('format');
                
                const response = await fetch(`/generate/${format}`, {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    
                    resultDiv.className = 'result success';
                    resultContent.innerHTML = `
                        <h3>✅ Изображение успешно создано!</h3>
                        <img src="${url}" alt="Generated Image">
                        <br>
                        <a href="${url}" download="generated-${format}.png" class="download-btn">
                            📥 Скачать изображение
                        </a>
                    `;
                } else {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Ошибка сервера');
                }
                
            } catch (error) {
                resultDiv.className = 'result error';
                resultContent.innerHTML = `<h3>❌ Ошибка</h3><p>${error.message}</p>`;
            } finally {
                generateBtn.disabled = false;
                generateBtn.innerHTML = '🚀 Сгенерировать изображение';
            }
        });
    </script>
</body>
</html>
'''

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
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        
        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
        
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

def safe_text(text):
    """Безопасная обработка текста"""
    if not text:
        return ""
    
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except:
            text = text.decode('utf-8', errors='ignore')
    
    return str(text)

def get_text_size(text, font):
    """Получить размер текста безопасно"""
    try:
        bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except:
        try:
            return ImageDraw.Draw(Image.new('RGB', (1, 1))).textsize(text, font=font)
        except:
            return len(text) * 12, 20

def wrap_text(text, font, max_width):
    """Разбить текст на строки"""
    text = safe_text(text)
    if not text:
        return []
    
    words = text.split(' ')
    lines = []
    current_line = ''
    
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        text_width, _ = get_text_size(test_line, font)
        
        if text_width <= max_width:
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
        draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
        draw.text((x, y), text, font=font, fill=fill_color)
    except Exception as e:
        print(f"Ошибка отрисовки текста: {e}")

def generate_image(background_image, logo_text, title, subtitle, disclaimer, logo_url, format_name):
    """Генерировать изображение"""
    if format_name not in FORMATS:
        raise ValueError(f"Неподдерживаемый формат: {format_name}")
    
    logo_text = safe_text(logo_text)
    title = safe_text(title)
    subtitle = safe_text(subtitle)
    disclaimer = safe_text(disclaimer)
    
    target_size = FORMATS[format_name]
    width, height = target_size['width'], target_size['height']
    font_sizes = get_font_sizes(format_name)
    padding = font_sizes['padding']
    
    background = background_image.resize((width, height), Image.Resampling.LANCZOS)
    background = background.convert('RGBA')
    
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    for y in range(height):
        alpha = int(76 + (153 - 76) * y / height)
        overlay_draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))
    
    background = Image.alpha_composite(background, overlay)
    draw = ImageDraw.Draw(background)
    
    logo_font = create_font(font_sizes['logo_text'])
    title_font = create_font(font_sizes['title'])
    subtitle_font = create_font(font_sizes['subtitle'])
    disclaimer_font = create_font(font_sizes['disclaimer'])
    
    current_y = padding
    text_max_width = width - (padding * 2)
    
    if logo_url:
        try:
            response = requests.get(logo_url, timeout=5)
            if response.status_code == 200:
                logo_image = Image.open(io.BytesIO(response.content))
                logo_size = 80 if format_name == 'vk-square' else 120
                
                logo_image.thumbnail((logo_size, logo_size), Image.Resampling.LANCZOS)
                
                if logo_image.mode == 'RGBA':
                    background.paste(logo_image, (padding, current_y), logo_image)
                else:
                    background.paste(logo_image, (padding, current_y))
                
                current_y += logo_image.height + 30
        except Exception as e:
            print(f"Ошибка загрузки логотипа: {e}")
    
    if logo_text:
        draw_text_with_shadow(draw, logo_text, (padding, current_y), logo_font, 'white', 'black')
        _, text_height = get_text_size(logo_text, logo_font)
        current_y += text_height + 30
    
    if title:
        title_lines = wrap_text(title, title_font, text_max_width)
        for line in title_lines:
            draw_text_with_shadow(draw, line, (padding, current_y), title_font, 'white', 'black')
            _, text_height = get_text_size(line, title_font)
            current_y += int(text_height * 1.2)
        current_y += 20
    
    if subtitle:
        subtitle_lines = wrap_text(subtitle, subtitle_font, text_max_width)
        for line in subtitle_lines:
            draw_text_with_shadow(draw, line, (padding, current_y), subtitle_font, 'white', 'black')
            _, text_height = get_text_size(line, subtitle_font)
            current_y += int(text_height * 1.2)
        current_y += 30
    
    if disclaimer:
        disclaimer_lines = wrap_text(disclaimer, disclaimer_font, text_max_width)
        
        total_disclaimer_height = 0
        for line in disclaimer_lines:
            _, text_height = get_text_size(line, disclaimer_font)
            total_disclaimer_height += int(text_height * 1.2)
        
        disclaimer_y = height - padding - total_disclaimer_height
        
        for line in disclaimer_lines:
            draw_text_with_shadow(draw, line, (padding, disclaimer_y), disclaimer_font, '#CCCCCC', 'black')
            _, text_height = get_text_size(line, disclaimer_font)
            disclaimer_y += int(text_height * 1.2)
    
    return background.convert('RGB')

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        'message': 'Image Generator API работает!',
        'status': 'Production Ready with Web Interface',
        'endpoints': {
            'GET /process/': 'Веб-интерфейс для генерации',
            'POST /generate/<format>': 'API для генерации изображения',
            'GET /formats': 'Получить доступные форматы',
            'GET /': 'Проверка работоспособности'
        },
        'formats': list(FORMATS.keys())
    })

@app.route('/process/')
def process_page():
    """Веб-интерфейс для обработки изображений"""
    return render_template_string(PROCESS_HTML)

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
        
        if 'image' not in request.files:
            return jsonify({'error': 'Изображение не загружено'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
        
        logo_text = request.form.get('logoText', '')
        title = request.form.get('title', '')
        subtitle = request.form.get('subtitle', '')
        disclaimer = request.form.get('disclaimer', '')
        logo_url = request.form.get('logoUrl', '')
        
        try:
            background_image = Image.open(file.stream)
        except Exception as e:
            return jsonify({'error': f'Ошибка обработки изображения: {str(e)}'}), 400
        
        result_image = generate_image(
            background_image, logo_text, title, subtitle, disclaimer, logo_url, format_name
        )
        
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
        print(f"Ошибка генерации: {e}")
        return jsonify({'error': f'Ошибка генерации изображения: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=False)

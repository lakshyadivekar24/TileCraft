from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageDraw
import io
import math
import base64

app = Flask(__name__)

# --- CONFIGURATION ---
DPI = 150
MM_TO_INCH = 25.4

# Standard Page Sizes in Millimeters (Width x Height)
PAGE_SIZES = {
    'a4': (210, 297),
    'a3': (297, 420),
    'a2': (420, 594),
    'a1': (594, 841),
    'letter': (215.9, 279.4), # US Letter
    'legal': (215.9, 355.6)   # US Legal
}

def convert_to_mm(value, unit):
    if unit == 'cm': return value * 10
    if unit == 'inch': return value * 25.4
    if unit == 'ft': return value * 304.8
    return value  # mm default

def prepare_canvas(image_file, target_w_val, target_h_val, unit, page_format):
    # 1. Get Page Dimensions based on selection
    page_w_mm, page_h_mm = PAGE_SIZES.get(page_format, PAGE_SIZES['a4'])
    
    # Calculate Page Size in Pixels
    page_w_px = int((page_w_mm / MM_TO_INCH) * DPI)
    page_h_px = int((page_h_mm / MM_TO_INCH) * DPI)

    # 2. Convert Target Size to MM
    target_w_mm = convert_to_mm(target_w_val, unit)
    target_h_mm = convert_to_mm(target_h_val, unit)

    # 3. Target Size in Pixels
    target_w_px = int((target_w_mm / MM_TO_INCH) * DPI)
    target_h_px = int((target_h_mm / MM_TO_INCH) * DPI)

    # 4. Resize Image (Aspect Ratio Logic)
    img = Image.open(image_file)
    img_w, img_h = img.size
    ratio = min(target_w_px / img_w, target_h_px / img_h)
    new_w = int(img_w * ratio)
    new_h = int(img_h * ratio)
    img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 5. Calculate Grid based on Selected Page Size
    cols = math.ceil(target_w_px / page_w_px)
    rows = math.ceil(target_h_px / page_h_px)
    
    canvas_w = cols * page_w_px
    canvas_h = rows * page_h_px
    
    # 6. Create Canvas & Paste Center
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    x_offset = (canvas_w - new_w) // 2
    y_offset = (canvas_h - new_h) // 2
    canvas.paste(img_resized, (x_offset, y_offset))
    
    # Return canvas and the pixel dimensions of the single page for cutting/preview
    return canvas, cols, rows, page_w_px, page_h_px

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preview', methods=['POST'])
def preview():
    if 'image' not in request.files: return "No Image", 400
    file = request.files['image']
    val_w = float(request.form.get('width'))
    val_h = float(request.form.get('height'))
    unit = request.form.get('unit')
    page_format = request.form.get('page_format') # New Input
    
    canvas, cols, rows, p_w, p_h = prepare_canvas(file, val_w, val_h, unit, page_format)
    
    # Draw Grid Lines based on the selected page size
    draw = ImageDraw.Draw(canvas)
    grid_color = (0, 150, 255) # Blueprint Blue
    
    for x in range(0, canvas.width, p_w):
        draw.line((x, 0, x, canvas.height), fill=grid_color, width=10)
    for y in range(0, canvas.height, p_h):
        draw.line((0, y, canvas.width, y), fill=grid_color, width=10)
    
    canvas.thumbnail((800, 800)) 
    buffered = io.BytesIO()
    canvas.save(buffered, format="JPEG", quality=70)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({'image_data': img_str, 'pages': cols * rows})

@app.route('/download', methods=['POST'])
def download():
    file = request.files['image']
    val_w = float(request.form.get('width'))
    val_h = float(request.form.get('height'))
    unit = request.form.get('unit')
    page_format = request.form.get('page_format')
    
    canvas, _, _, p_w, p_h = prepare_canvas(file, val_w, val_h, unit, page_format)
    
    pages = []
    # Dynamic Slicing
    for y in range(0, canvas.height, p_h):
        for x in range(0, canvas.width, p_w):
            box = (x, y, x + p_w, y + p_h)
            tile = canvas.crop(box)
            pages.append(tile)
            
    pdf_io = io.BytesIO()
    pages[0].save(pdf_io, "PDF", resolution=DPI, save_all=True, append_images=pages[1:])
    pdf_io.seek(0)
    
    return send_file(pdf_io, as_attachment=True, download_name=f"poster_{page_format}.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)
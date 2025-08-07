import os
import base64
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

from flask import send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')
OCR_API_KEY = os.getenv('OCR_API_KEY')

if not OCR_API_KEY or OCR_API_KEY == 'YOUR_API_KEY_HERE':
    raise RuntimeError('ERROR: OCR.space API key is missing. Please add it to your .env file.')

def encode_board(board):
    return '%5B' + '%5D%2C%5B'.join([','.join(map(str, row)) for row in board]) + '%5D'

def encode_params(params):
    return '&'.join(f'{key}=%5B{encode_board(value)}%5D' for key, value in params.items())

def parse_ocr_result(parsed_result):
    grid = [[0 for _ in range(9)] for _ in range(9)]
    lines = parsed_result.get('TextOverlay', {}).get('Lines', [])
    if not lines:
        return grid
    min_x = min_y = float('inf')
    max_x = max_y = float('-inf')
    for line in lines:
        for word in line['Words']:
            min_x = min(min_x, word['Left'])
            min_y = min(min_y, word['Top'])
            max_x = max(max_x, word['Left'] + word['Width'])
            max_y = max(max_y, word['Top'] + word['Height'])
    if float('inf') in [min_x, min_y] or float('-inf') in [max_x, max_y]:
        return grid
    puzzle_width = max_x - min_x
    puzzle_height = max_y - min_y
    cell_width = puzzle_width / 9
    cell_height = puzzle_height / 9
    for line in lines:
        for word in line['Words']:
            digit_text = word['WordText'].strip()[:1]
            try:
                digit = int(digit_text)
            except ValueError:
                continue
            if 1 <= digit <= 9:
                center_x = word['Left'] + word['Width'] / 2
                center_y = word['Top'] + word['Height'] / 2
                col = int((center_x - min_x) / cell_width)
                row = int((center_y - min_y) / cell_height)
                if 0 <= row < 9 and 0 <= col < 9 and grid[row][col] == 0:
                    grid[row][col] = digit
    return grid

@app.route('/process-image', methods=['POST'])
def process_image():
    data = request.get_json()
    image = data.get('image')
    if not image:
        return jsonify({'error': 'No image provided'}), 400
    if not image.startswith('data:image'):
        image = f'data:image/png;base64,{image}'
    payload = {
        'base64Image': image,
        'OCREngine': '2',
        'isOverlayRequired': 'true',
        'detectOrientation': 'true'
    }
    headers = {'apikey': OCR_API_KEY}
    response = requests.post('https://api.ocr.space/parse/image', data=payload, headers=headers)
    data = response.json()
    if data.get('IsErroredOnProcessing'):
        return jsonify({'error': data.get('ErrorMessage', ['Unknown error'])[0]}), 500
    parsed_result = data['ParsedResults'][0]
    grid = parse_ocr_result(parsed_result)
    return jsonify({'grid': grid})

@app.route('/solve-puzzle', methods=['POST'])
def solve_puzzle():
    data = request.get_json()
    board = data.get('board')
    if not board or not isinstance(board, list):
        return jsonify({'error': 'Invalid board data provided.'}), 400
    encoded_data = encode_params({'board': board})
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post('https://sugoku.onrender.com/solve', data=encoded_data, headers=headers)
    if response.status_code != 200:
        return jsonify({'error': 'Failed to solve puzzle using external API.'}), 500
    solved = response.json()
    return jsonify({'solution': solved.get('solution')})

@app.route('/')
def root():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_proxy(path):
    # Serve static files (script.js, style.css)
    return send_from_directory('.', path)

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, request, jsonify, send_from_directory
import os
import tempfile
from openai import OpenAI
from flask_cors import CORS
import requests
from keys import openai_key, imgur_key

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=openai_key)
IMGUR_CLIENT_ID = imgur_key

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))

@app.route('/')
def serve_index():
    return send_from_directory(frontend_path, 'index.html')

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    subject = data.get('subject', '')

    # Process message with the AI model
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You're a tutor in {subject}. Answer the questions clearly and didactically."},
            {"role": "user", "content": message}
        ],
        temperature=0,
    )

    answer = response.choices[0].message.content
    return jsonify({"response": answer})

def upload_image_to_imgur(filepath):
    headers = {
        "Authorization": f"Client-ID {IMGUR_CLIENT_ID}"
    }
    with open(filepath, "rb") as f:
        response = requests.post(
            "https://api.imgur.com/3/image",
            headers=headers,
            files={'image': f}
        )
    if response.status_code == 200:
        return response.json()['data']['link']
    else:
        raise Exception(f"Imgur upload failed: {response.status_code} {response.text}")

@app.route('/upload_problem', methods=['POST'])
def upload_problem():
    if 'problem_image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['problem_image']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, file.filename)
        file.save(filepath)

        try:
            public_url = upload_image_to_imgur(filepath)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": "Please help me solve this problem."},
                    {"type": "image_url", "image_url": {"url": public_url}}
                ]}
            ],
            temperature=0
        )
        answer = response.choices[0].message.content
        return jsonify({"text": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/chat_audio", methods=["POST"])
def chat_audio():
    data = request.get_json()
    message = data.get("message", "")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text", "audio"],
            audio={"voice": "alloy", "format": "wav"},
            messages=[
                {"role": "user", "content": message}
            ],
            store=True
        )

        audio_b64 = response.choices[0].message.audio.data
        text_response = response.choices[0].message.content

        return jsonify({
            "response": text_response,
            "audio": audio_b64
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

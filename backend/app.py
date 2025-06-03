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
    messages = data.get("messages", [])
    subject = data.get("subject", "")

    # Add a system prompt at the beginning
    messages.insert(0, {
        "role": "system",
        "content": f"You are a helpful tutor specialized in {subject}. Explain clearly and contextually."
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0
        )
        answer = response.choices[0].message.content
        return jsonify({ "response": answer })

    except Exception as e:
        return jsonify({ "response": f"Error: {str(e)}" })

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
    subject = data.get("subject", "")

    try:
        prompt = f"You are a helpful tutor in {subject}. Answer the following question clearly and didactically."

        response = client.chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text", "audio"],
            audio={"voice": "alloy", "format": "wav"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": message}
            ],
            store=True
        )

        audio_b64 = response.choices[0].message.audio.data
        # <-- Try to get the text, fallback to reusing the original message
        text_response = response.choices[0].message.content
        if text_response is None:
            text_response = "[Audio response generated. Text unavailable.]"

        return jsonify({
            "response": text_response,
            "audio": audio_b64
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)

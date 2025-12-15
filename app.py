import os
import uuid
import subprocess
import platform
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

UPLOAD_FOLDER = "uploads"
COMPRESSED_FOLDER = "compressed"

app = Flask(__name__)
CORS(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(COMPRESSED_FOLDER, exist_ok=True)

GS_COMMAND = "gswin64c" if platform.system() == "Windows" else "gs"


@app.route("/compress", methods=["POST"])
def compress_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files allowed"}), 400

    compression_level = request.form.get("level", "ebook")

    pdf_settings = {
        "screen": "/screen",
        "ebook": "/ebook",
        "printer": "/printer",
        "preserve": None
    }

    setting = pdf_settings.get(compression_level, "/ebook")

    input_filename = f"{uuid.uuid4()}.pdf"
    output_filename = f"{uuid.uuid4()}_compressed.pdf"

    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    output_path = os.path.join(COMPRESSED_FOLDER, output_filename)

    file.save(input_path)

    def run_gs(gs_setting=None, preserve_images=False):
        command = [
            GS_COMMAND,
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
        ]

        if preserve_images:
            command.extend([
                "-dDownsampleColorImages=false",
                "-dDownsampleGrayImages=false",
                "-dDownsampleMonoImages=false",
                "-dAutoFilterColorImages=false",
                "-dAutoFilterGrayImages=false"
            ])
        else:
            command.append(f"-dPDFSETTINGS={gs_setting}")

        command.extend([
            f"-sOutputFile={output_path}",
            input_path
        ])

        subprocess.run(command, check=True)

    try:
        # Attempt 1
        if compression_level == "preserve":
            raise Exception("Force preserve mode")

        run_gs(setting)

        with open(output_path, "rb") as f:
            if f.read(4) != b"%PDF":
                raise Exception("Invalid PDF")

    except Exception:
        try:
            # Attempt 2 (safe)
            run_gs("/printer")

            with open(output_path, "rb") as f:
                if f.read(4) != b"%PDF":
                    raise Exception("Invalid PDF")

        except Exception:
            # Attempt 3 (preserve images)
            run_gs(preserve_images=True)

    try:
        response = send_file(
            output_path,
            as_attachment=True,
            download_name="compressed.pdf"
        )
        response.headers["X-Compression-Mode"] = compression_level
        return response

    except Exception:
        return jsonify({"error": "Compression failed"}), 500

    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

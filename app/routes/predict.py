from flask import Flask, request, jsonify, Blueprint, current_app
from mmdet.apis import init_detector, inference_detector
from mmcv import imread
import numpy as np
import cv2
import os
import torch
import jwt
import uuid
from datetime import datetime
from datetime import datetime

predict_ = Blueprint('predict', __name__)

# Folder penyimpanan
UPLOAD_FOLDER = 'Frontend-MRI-Condyle-NET/public/uploads'
RESULT_FOLDER = 'Frontend-MRI-Condyle-NET/public/results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# Konfigurasi model-model
model_configs = [
    {  # 1 - Cascade_Mask-RCNN
        "config": r'F:\DentalSegmentation\DentalSeg\Model\config_deploy_cascade.py',
        "checkpoint": r'F:\DentalSegmentation\DentalSeg\Model\epoch_25_Cascade.pth',
    },
    {  # 2 - Mask2Form
        "config": r'F:\DentalSegmentation\DentalSeg\Model\config_deploy_Mask2Form.py',
        "checkpoint": r'F:\DentalSegmentation\DentalSeg\Model\iter_750_Mask2Form.pth',
    },
    {  # 3 - HTC
        "config": r'F:\DentalSegmentation\DentalSeg\Model\config_deploy_HTC.py',
        "checkpoint": r'F:\DentalSegmentation\DentalSeg\Model\epoch_25_HTC.pth',
    },
    {  # 4 - Mask-RCNN
        "config": r'F:\DentalSegmentation\DentalSeg\Model\config_deploy_Mask-rcnn.py',
        "checkpoint": r'F:\DentalSegmentation\DentalSeg\Model\epoch_25_Mask.pth',
    },
    {  # 5 - SOLOv2
        "config": r'F:\DentalSegmentation\DentalSeg\Model\config_deploy_SoloV2.py',
        "checkpoint": r'F:\DentalSegmentation\DentalSeg\Model\epoch_25_SoloV2.pth',
    },
]

loaded_models = {}

def get_models(selected_model):
    models = []
    if selected_model == 6:
        indices = list(range(1, 6)) 
    elif 1 <= selected_model <= 5:
        indices = [selected_model]
    else:
        raise ValueError("Model harus berupa angka antara 1 dan 6.")

    for idx in indices:
        if idx not in loaded_models:
            cfg = model_configs[idx - 1]
            model = init_detector(cfg["config"], cfg["checkpoint"], device='cuda:0')
            loaded_models[idx] = model
        models.append(loaded_models[idx])
    return models, indices


@predict_.route("/api/predict", methods=["POST"])
def predict_image():
    try:
        # Cek file gambar
        if 'image' not in request.files:
            return jsonify({"status": "error", "message": "Tidak ada file gambar yang diunggah."}), 400
        file = request.files['image']

        if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            return jsonify({"status": "error", "message": "Format gambar tidak didukung. Gunakan JPG/PNG."}), 400

        # Simpan gambar
        unique_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        filename = f"upload_{unique_id}.jpg"
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)
        image = imread(input_path)

        # Cek parameter model
        model_param = request.form.get('model')
        if not model_param:
            return jsonify({"status": "error", "message": "Parameter 'model' wajib diisi."}), 400

        try:
            model_idx = int(model_param)
        except ValueError:
            return jsonify({"status": "error", "message": "Parameter 'model' harus berupa angka 1 sampai 6."}), 400

        if not (1 <= model_idx <= 6):
            return jsonify({"status": "error", "message": "Model hanya tersedia dari 1 hingga 6."}), 400

        models, indices = get_models(model_idx)

        # Majority voting params
        score_threshold = 0.1
        vote_threshold = max(1, len(models) // 2 + 1)
        alpha = 0.5
        kernel = np.ones((1, 5), np.uint8)

        # Segmentasi
        votes = []
        for model in models:
            result = inference_detector(model, image)
            masks = result.pred_instances.masks.cpu().numpy()
            scores = result.pred_instances.scores.cpu().numpy()

            valid_masks = [masks[i] for i in range(len(scores)) if scores[i] >= score_threshold]
            if valid_masks:
                combined_mask = np.any(valid_masks, axis=0).astype(np.uint8)
            else:
                combined_mask = np.zeros_like(image[..., 0], dtype=np.uint8)
            votes.append(combined_mask)

        vote_sum = np.sum(votes, axis=0)
        fused_mask = (vote_sum >= vote_threshold).astype(np.uint8)
        dilated_mask = cv2.dilate(fused_mask, kernel, iterations=1)

        overlay_image = image.copy().astype(np.float32)
        overlay_color = np.array([0, 255, 0], dtype=np.float32)
        overlay_image[dilated_mask == 1] = (
            (1 - alpha) * overlay_image[dilated_mask == 1] + alpha * overlay_color
        )
        overlay_image = overlay_image.astype(np.uint8)

        # Simpan hasil
        result_filename = f"result_{unique_id}.jpg"
        result_path = os.path.join(RESULT_FOLDER, result_filename)
        cv2.imwrite(result_path, overlay_image)

        SECRET_KEY = current_app.config['SECRET_KEY']
        token_receive = request.form.get("mytoken")
    
        if not token_receive:
            return jsonify({"msg": "Unauthorized access: No token provided"}), 401

        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        email = payload["id"]

        now = datetime.now()
        formatted = now.strftime("%Y-%m-%d %H:%M:%S")

        doc = {
            "email": email,
            "uploaded_image": filename,
            "result_image": result_filename,
            "result_url": f"/results/{result_filename}",
            "upload_url": f"/uploads/{filename}",
            "model_used": indices,
            "vote_threshold": vote_threshold,
            "date": formatted,
        }

        current_app.db.history.insert_one(doc)

        return jsonify({
            "status": "success",
            "message": "Segmentasi berhasil dilakukan.",
            "uploaded_image": filename,
            "result_image": result_filename,
            "result_url": f"/results/{result_filename}",
            "model_used": indices,
            "vote_threshold": vote_threshold
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"Terjadi kesalahan: {str(e)}"}), 500
    
@predict_.route('/api/get-history', methods=["POST"])
def get_history():
    SECRET_KEY = current_app.config['SECRET_KEY']
    token_receive = request.form.get("mytoken")
    
    if not token_receive:
        return jsonify({"msg": "Unauthorized access: No token provided"}), 401

    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        email = payload["id"]

        history_cursor = current_app.db.history.find({"email": email}, {"_id": 0, "password": 0})
        history_list = list(history_cursor)  
        if history_list:
            return jsonify({"msg": "History fetched successfully", "history": history_list}), 200
        else:
            return jsonify({"msg": "No history found", "history": []}), 200


    except (jwt.ExpiredSignatureError, jwt.exceptions.DecodeError):
        return jsonify({"msg": "Token is invalid or expired"}), 401
    
@predict_.route('/api/delete-history', methods=["POST"])
def delete_history():
    SECRET_KEY = current_app.config['SECRET_KEY']
    token_receive = request.form.get("mytoken")
    date = request.form.get("date")  # digunakan untuk identifikasi dokumen

    if not token_receive:
        return jsonify({"msg": "Unauthorized access: No token provided"}), 401
    if not date:
        return jsonify({"msg": "Bad request: 'date' is required"}), 400

    try:
        payload = jwt.decode(token_receive, SECRET_KEY, algorithms=["HS256"])
        email = payload["id"]

        # Cari dokumen berdasarkan email dan tanggal
        doc = current_app.db.history.find_one({
            "email": email,
            "date": date,
        })

        if not doc:
            return jsonify({"msg": "History not found"}), 404

        # Ambil nama file yang perlu dihapus
        uploaded_image = doc.get("uploaded_image")
        result_image = doc.get("result_image")

        # Hapus file dari sistem file lokal
        try:
            if uploaded_image:
                upload_path = os.path.join(UPLOAD_FOLDER, uploaded_image)
                if os.path.exists(upload_path):
                    os.remove(upload_path)

            if result_image:
                result_path = os.path.join(RESULT_FOLDER, result_image)
                if os.path.exists(result_path):
                    os.remove(result_path)
        except Exception as file_error:
            return jsonify({"msg": "Failed to delete file(s)", "error": str(file_error)}), 500

        # Hapus dari database
        delete_result = current_app.db.history.delete_one({
            "email": email,
            "date": date
        })

        if delete_result.deleted_count == 1:
            return jsonify({"msg": "History and files deleted successfully"}), 200
        else:
            return jsonify({"msg": "Failed to delete history from database"}), 500

    except jwt.ExpiredSignatureError:
        return jsonify({"msg": "Token has expired"}), 401
    except jwt.DecodeError:
        return jsonify({"msg": "Token is invalid"}), 401

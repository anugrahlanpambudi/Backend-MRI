from flask import Flask, request, jsonify, Blueprint
from mmdet.apis import init_detector, inference_detector
from mmcv import imread
import numpy as np
import cv2
import os
import torch
import uuid
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
from PIL import Image
import os

mapping = {
    "visitenkarte_chinesisch_1788767072.png": "chinesisch/visitenkarte_01.jpg",
    "visitenkarte_arabisch_1788767073.png": "arabisch/visitenkarte_01.jpg",
    "visitenkarte_japanisch_1788767073.png": "japanisch/visitenkarte_01.jpg",
    "visitenkarte_koreanisch_1788767083.png": "koreanisch/visitenkarte_01.jpg",
    "visitenkarte_russisch_1788767072.png": "russisch/visitenkarte_01.jpg",
    "visitenkarte_englisch_1788767072.png": "englisch/visitenkarte_01.jpg",
    "visitenkarte_deutsch_1788767071.png": "deutsch/visitenkarte_01.jpg",
    "visitenkarte_spanisch_1788767071.png": "spanisch/visitenkarte_01.jpg",
    "visitenkarte_italienisch_1788767072.png": "italienisch/visitenkarte_01.jpg",
}

src_dir = r"C:\Users\cskwiatkowski\.qoder\vibe_images"
dst_dir = r"C:\Users\cskwiatkowski\Documents\maiCatch\maicatch_hybrid\ocr\testdaten"

for src_name, dst_rel in mapping.items():
    src_path = os.path.join(src_dir, src_name)
    dst_path = os.path.join(dst_dir, dst_rel)
    if os.path.exists(src_path):
        img = Image.open(src_path).convert("RGB")
        img.save(dst_path, "JPEG", quality=95)
        print(f"OK: {dst_rel}")
    else:
        print(f"FEHLT: {src_name}")

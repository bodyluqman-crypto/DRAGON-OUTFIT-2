from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import os
import re

app = Flask(__name__)
main_key = "DRAGON-TEAM"
executor = ThreadPoolExecutor(max_workers=10)

def fetch_player_info(uid):
    """جلب بيانات اللاعب من API خارجي"""
    url = f'https://otman-info.vercel.app/player-info?uid={uid}'
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def fetch_and_process_image(image_url, size=None):
    """جلب الصورة من رابط وتحويلها إلى كائن PIL Image"""
    try:
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            if size:
                image = image.resize(size, Image.Resampling.LANCZOS)
            return image
    except Exception as e:
        print(f"Error fetching image: {image_url}, {e}")
    return None

def get_avatar_id(equipped_skills):
    """استخراج Avatar ID من قائمة المهارات"""
    # البحث عن أي skill ينتهي بـ 06
    for skill in equipped_skills:
        skill_str = str(skill)
        if skill_str.endswith("06"):
            return skill_str
    # إذا لم يوجد، نستخدم ID افتراضي
    return "406"

@app.route('/outfit-image', methods=['GET'])
def outfit_image():
    uid = request.args.get('uid')
    key = request.args.get('key')

    if not uid:
        return jsonify({'error': 'Missing uid parameter'}), 400
    if key != main_key:
        return jsonify({'error': 'Invalid or missing API key'}), 403

    # جلب بيانات اللاعب
    data = fetch_player_info(uid)
    if not data:
        return jsonify({'error': 'Failed to fetch player info'}), 500

    # استخراج البيانات المطلوبة
    profile_info = data.get("profileInfo", {})
    clothes_ids = profile_info.get("clothes", [])
    equipped_skills = profile_info.get("equipedSkills", [])
    
    pet_info = data.get("petInfo", {})
    pet_id = pet_info.get("id")
    
    basic_info = data.get("basicInfo", {})
    weapon_ids = basic_info.get("weaponSkinShows", [])
    weapon_id = weapon_ids[0] if weapon_ids else None

    # الأكواد المطلوبة للملابس بالترتيب الصحيح
    required_starts = ["211", "214", "208", "203", "204", "205", "203"]
    fallback_ids = ["211000000", "214000000", "208000000", "203000000", "204000000", "205000000", "203000000"]
    
    used_ids = set()
    outfit_images = []

    def fetch_outfit_image(idx, code):
        """جلب صورة قطعة الملابس المناسبة"""
        matched = None
        for oid in clothes_ids:
            str_oid = str(oid)
            if str_oid.startswith(code) and oid not in used_ids:
                matched = oid
                used_ids.add(oid)
                break
        if matched is None:
            matched = fallback_ids[idx]
        url = f'https://www.dl.cdn.freefireofficial.com/icons/{matched}.png'
        return fetch_and_process_image(url, size=(170, 170))

    # تنفيذ جلب صور الملابس بشكل متوازي
    futures = []
    for idx, code in enumerate(required_starts):
        futures.append(executor.submit(fetch_outfit_image, idx, code))

    # جلب صورة الخلفية
    bg_url = 'https://iili.io/C9t2qog.png'
    background_image = fetch_and_process_image(bg_url, size=(1024, 1024))
    if not background_image:
        return jsonify({'error': 'Failed to fetch background image'}), 500

    # تحديد مواقع الصور على الخلفية
    positions = [
        {'x': 760, 'y': 92,  'width': 170, 'height': 170},  # Hat (211)
        {'x': 810, 'y': 310, 'width': 170, 'height': 120},  # Face (214)
        {'x': 790, 'y': 490, 'width': 170, 'height': 170},  # Back (208)
        {'x': 72,  'y': 505, 'width': 170, 'height': 170},  # Top (203)
        {'x': 130, 'y': 792, 'width': 170, 'height': 170},  # Bottom (204)
        {'x': 728, 'y': 760, 'width': 170, 'height': 170},  # Shoes (205)
        {'x': 72,  'y': 230, 'width': 170, 'height': 170},  # Top Backup (203)
    ]

    # لصق صور الملابس
    for idx, future in enumerate(futures):
        outfit_image = future.result()
        if outfit_image:
            pos = positions[idx]
            resized = outfit_image.resize((pos['width'], pos['height']), Image.Resampling.LANCZOS)
            background_image.paste(resized, (pos['x'], pos['y']), resized)

    # جلب وصورة الـ Pet (الحيوان الأليف)
    if pet_id:
        # رابط البيت الصحيح - نستخدم نفس رابط الأيقونات
        pet_url = f'https://www.dl.cdn.freefireofficial.com/icons/pet_{pet_id}.png'
        pet_image = fetch_and_process_image(pet_url, size=(140, 170))
        if not pet_image:
            # محاولة رابط بديل
            pet_url = f'https://www.dl.cdn.freefireofficial.com/icons/{pet_id}.png'
            pet_image = fetch_and_process_image(pet_url, size=(140, 170))
        if pet_image:
            background_image.paste(pet_image, (700, 700), pet_image)

    # جلب صورة الـ Avatar (الشخصية)
    avatar_id = get_avatar_id(equipped_skills)
    # رابط الصورة الصحيح من API المخصص
    avatar_url = f'https://characteriroxmar.vercel.app/chars?id={avatar_id}'
    avatar_image = fetch_and_process_image(avatar_url, size=(650, 780))
    if not avatar_image:
        # محاولة رابط بديل للصورة
        avatar_url = f'https://www.dl.cdn.freefireofficial.com/icons/avatar_{avatar_id}.png'
        avatar_image = fetch_and_process_image(avatar_url, size=(650, 780))
    if avatar_image:
        # توسيط الصورة في المنتصف
        center_x = (1024 - avatar_image.width) // 2
        background_image.paste(avatar_image, (center_x, 145), avatar_image)

    # جلب صورة الـ Weapon (السلاح)
    if weapon_id:
        weapon_url = f'https://www.dl.cdn.freefireofficial.com/icons/weapon_{weapon_id}.png'
        weapon_image = fetch_and_process_image(weapon_url, size=(330, 200))
        if not weapon_image:
            weapon_url = f'https://www.dl.cdn.freefireofficial.com/icons/{weapon_id}.png'
            weapon_image = fetch_and_process_image(weapon_url, size=(330, 200))
        if weapon_image:
            background_image.paste(weapon_image, (670, 564), weapon_image)

    # حفظ الصورة في الذاكرة وإرجاعها
    img_io = BytesIO()
    background_image.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': '✅ API Working!',
        'endpoints': {
            '/outfit-image': 'GET - uid=ID&key=DRAGON-TEAM'
        },
        'example': '/outfit-image?uid=2129828082&key=DRAGON-TEAM'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
import cv2
import time
import logging
import os
import asyncio
import requests
from ultralytics import YOLO
from datetime import datetime

# Absolute imports
from app.database import SessionLocal
from app.models import Detection, User  # Импорт моделей базы данных

# CONFIGURATION
CONFIDENCE_THRESHOLD = 0.2  # Detection sensitivity (0.0 to 1.0)
CHECK_INTERVAL = 1          # Time delay between checks in seconds
SAVE_PATH = "static/captures" # Directory to store detection images
CAT_CLASS_ID = 15           # COCO dataset class ID for 'cat'

# Ensure the capture directory exists
os.makedirs(SAVE_PATH, exist_ok=True)

def run_detector():
    """
    Main loop to capture frames, run AI inference, and trigger notifications.
    """
    # Initialize the camera (0 to default webcam)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        logging.error("Could not open video device.")
        return

    # Load the YOLOv8 Nano model
    model = YOLO("yolov8n.pt") 

    logging.info(f"Detector started. Scanning every {CHECK_INTERVAL} seconds...")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logging.warning("Failed to grab frame from camera.")
                break

            # Run YOLO inference on the current frame
            results = model(frame, verbose=False)
            
            cat_detected = False
            max_conf = 0

            # Analyze detection results
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    
                    # Check if the detected object is a cat and meets confidence requirements
                    if class_id == CAT_CLASS_ID and conf > CONFIDENCE_THRESHOLD:
                        cat_detected = True
                        max_conf = conf
                        break

            if cat_detected:
                # Generate unique filename using timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"cat_{timestamp}.jpg"
                file_path = os.path.join(SAVE_PATH, file_name)
                
                # Save the visual proof to disk
                cv2.imwrite(file_path, frame)
                logging.info(f"Cat detected! Confidence: {max_conf:.2f}. Image saved: {file_path}")

                # ========================================================
                # 1. СОХРАНЕНИЕ МЕТАДАННЫХ В POSTGRESQL (ВОЗВРАЩЕНО И ИСПРАВЛЕНО)
                # ========================================================
                db = SessionLocal()
                try:
                    new_detection = Detection(
                        photo_url=file_path,       # Исправлено под твою модель
                        confidence_score=max_conf
                    )
                    db.add(new_detection)
                    db.commit()
                    logging.info("Successfully saved detection log to PostgreSQL database!")
                except Exception as db_err:
                    logging.error(f"Database error while saving detection: {db_err}")
                finally:
                    db.close()

                # ========================================================
                # 2. НАДЕЖНЫЙ СИНХРОННЫЙ БЛОК ОТПРАВКИ TELEGRAM
                # ========================================================
                db = SessionLocal()
                try:
                    import dotenv
                    dotenv.load_dotenv()
                    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
                    
                    if TELEGRAM_TOKEN:
                        # Находим всех активных пользователей с заполненным ID
                        active_users = db.query(User).filter(User.is_active == True, User.telegram_id.isnot(None)).all()
                        
                        caption = f"🐱 Cat detected!\nConfidence: {max_conf:.2%}"
                        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                        
                        for user in active_users:
                            try:
                                logging.info(f"Sending via HTTP API to: {user.telegram_id}")
                                with open(file_path, 'rb') as photo_file:
                                    payload = {'chat_id': int(user.telegram_id), 'caption': caption}
                                    files = {'photo': photo_file}
                                    response = requests.post(url, data=payload, files=files)
                                    
                                    if response.status_code == 200:
                                        logging.info(f"Telegram notification sent to user {user.telegram_id} successfully.")
                                    else:
                                        logging.error(f"Telegram API Error: {response.text}")
                            except Exception as user_err:
                                logging.error(f"Failed to send to {user.telegram_id}: {user_err}")
                    else:
                        logging.error("TELEGRAM_TOKEN not found in environment!")
                except Exception as tg_err:
                    logging.error(f"Notification error: {tg_err}")
                finally:
                    db.close()
                # ========================================================

            # Sleep to reduce CPU/GPU load
            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logging.info("Detector stopped by user.")
    finally:
        # Release hardware resources
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Configure logging format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    run_detector()
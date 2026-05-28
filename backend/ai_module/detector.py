import cv2
import time
import logging
import os
import asyncio
from ultralytics import YOLO
from datetime import datetime

# Absolute imports
from app.telegram import send_cat_notification
from app.database import SessionLocal
from app.models import Detection

# CONFIGURATION
CONFIDENCE_THRESHOLD = 0.2  # Detection sensitivity (0.0 to 1.0)
CHECK_INTERVAL = 5          # Time delay between checks in seconds
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
            # verbose=False reduces console clutter
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

                # Save detection metadata to PostgreSQL
                db = SessionLocal()
                try:
                    new_detection = Detection(
                        photo_url=file_path,
                        confidence_score=max_conf
                    )
                    db.add(new_detection)
                    db.commit()
                except Exception as e:
                    logging.error(f"Database error: {e}")
                finally:
                    db.close()

                # Trigger Telegram notification
                try:
                    asyncio.run(send_cat_notification(file_path, max_conf))
                except Exception as e:
                    logging.error(f"Notification error: {e}")

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
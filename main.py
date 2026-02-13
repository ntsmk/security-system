import subprocess
from datetime import datetime, time as dtime
from pathlib import Path
from supabase import create_client
from twilio.rest import Client
import os
import time
from gpiozero import Button, MotionSensor
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from twilio.http.http_client import TwilioHttpClient
import sys
import logging
from logging.handlers import RotatingFileHandler

door = Button(17, pull_up=True)
motion = MotionSensor(22)

PROJECT_ROOT = Path(__file__).parent

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)
bucket_name = "security-camera-images"

tw_account_id = os.getenv("account_sid")
tw_auth_token = os.getenv("auth_token")
tw_from_number = os.getenv("from_number")
tw_to_number = os.getenv("to_number")

# Configure retry logic
# 1. Define your retry strategy
retry_strategy = Retry(
    total=5,
    backoff_factor=1,  # Wait 1s, 2s, 4s, 8s, 16s...
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST"]
)

# 2. Setup the session and adapter
session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)

# 3. Inject this session into Twilio's HttpClient
custom_http_client = TwilioHttpClient(timeout=10)
custom_http_client.session = session

# 4 adding it to creating client
twilio = Client(tw_account_id, tw_auth_token, http_client=custom_http_client)

# Configure images dir
images_dir = PROJECT_ROOT / "images"
images_dir.mkdir(exist_ok=True)  # creates folders if not exist

# Define the log directory
logs_dir = PROJECT_ROOT / "logs"
logs_dir.mkdir(exist_ok=True)  # creates folders if not exist
log_file = logs_dir / f"security_system.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=10
        ),
        logging.StreamHandler(sys.stdout)
    ]
)


def is_active_time():
    """
    :return: If the current time is desired active time, return True
    """
    now = datetime.now().time()

    start = dtime(17, 20)
    end = dtime(17, 50)

    return start <= now <= end


def is_door_open():
    """
    :return: If door is open, return True
    """
    return not door.is_pressed


def is_motion():
    """
    :return: if motion is detected, return True
    """
    time.sleep(1)
    return motion.motion_detected


def capture_image():
    """
    :return: The image path of taken picture
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = images_dir / f"capture_{timestamp}.jpg"

    try:
        subprocess.run(
            ["rpicam-still", "-o", str(image_path)],
            check=True
        )
        logging.info(f"Image captured successfuly: {image_path}")
    except Exception as e:
        logging.error(f"Failed to capture image: {e}")

    return image_path


def upload_image(image_path, bucket_name):
    """
    :param image_path: Saved taken picture image path
    :param bucket_name: Supabase bucket name
    :return: Uploaded supabase public URL for the picture and file name to delete
    """
    file_name = image_path.name

    try:
        with open(image_path, "rb") as f:
            supabase.storage.from_(bucket_name).upload(
                file_name,
                f,
                file_options={
                    "content-type": "image/jpeg",
                    "upsert": False
                }
            )

        # Get public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        logging.info(f"Uploaded image: {file_name}")
        return public_url, file_name
    except Exception as e:
        logging.error(f"Failed to upload image on supabase: {e}")
        return None, None


def delete_image(bucket_name, file_name, image_path):
    """
    Cleaning up the pic data on the bucket as the bucket has limit. Also delete from local SD card
    """
    try:
        supabase.storage.from_(bucket_name).remove([file_name])
        logging.info(f"Removed from Supabase: {file_name}")
    except Exception as e:
        logging.error(f"Failed to delete image {file_name} on supabase: {e}")

    try:
        if os.path.exists(image_path):
            os.remove(image_path)  # delete from local SD card
            logging.info(f"Deleted local file: {image_path}")
    except Exception as e:
        logging.error(f"Local deletion failed for {image_path}:{e}")


def send_whatsapp_message(public_url):
    """
    Send the whatsapp message along with supabase uploaded public URL to attach the picture
    :param public_url: Supabase uploaded picture URL
    """
    try:
        twilio.messages.create(
            from_=tw_from_number,
            to=tw_to_number,
            body="Motion detected!",
            media_url=[public_url]
        )
        logging.info("Sent whatsapp message")

    except Exception as e:
        logging.error(f"Failed to send message after retry. Error:{e}")


if __name__ == "__main__":
    while True:
        if is_active_time():
            if is_door_open() or is_motion():
                try:
                    image_path = capture_image()
                    public_url, file_name = upload_image(image_path, bucket_name)

                    if public_url:  # if uploading image to Supabase success
                        send_whatsapp_message(public_url)
                        time.sleep(20)  # Wait for Twilio to fetch the image
                        delete_image(bucket_name, file_name, image_path)
                    else:  # if uploading image to Supabase failed
                        logging.warning("Skipping deleting Supabase deleting because upload failed.")
                        if os.path.exists(image_path):
                            os.remove(image_path)
                            logging.info("Cleaned up local file")

                except Exception as e:
                    logging.exception(f"Critical error happened: {e}")

                time.sleep(10)  # Small delay to avoid busy looping
        else:
            time.sleep(60)  # Sleep longer when inactive to save CPU

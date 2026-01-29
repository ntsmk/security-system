import subprocess
from datetime import datetime, time as dtime
from pathlib import Path
from supabase import create_client
from twilio.rest import Client
import os
from dotenv import load_dotenv
load_dotenv()
import time
from gpiozero import Button, MotionSensor

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)
bucket_name = "security-camera-images"

tw_account_id = os.getenv("account_sid")
tw_auth_token = os.getenv("auth_token")
tw_from_number = os.getenv("from_number")
tw_to_number = os.getenv("to_number")
twilio = Client(tw_account_id, tw_auth_token)

PROJECT_ROOT = Path(__file__).parent
images_dir = PROJECT_ROOT / "images"
images_dir.mkdir(exist_ok=True)
door = Button(17, pull_up=True)
motion = MotionSensor(22)

def is_active_time():
    """
    :return: If the current time is desired active time, return True
    """
    now = datetime.now().time()

    start = dtime(18, 0)  # 6:00 PM
    end = dtime(8, 0)     # 8:00 AM

    # Time window crosses midnight
    return now >= start or now <= end # catches time > 1800 (1801-2359) or time < 0800 (0000-0759)

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
    subprocess.run(
        ["rpicam-still", "-o", str(image_path)],
        check=True
    )

    return image_path

def upload_image(image_path, bucket_name):
    """
    :param image_path: Saved taken picture image path
    :param bucket_name: Supabase bucket name
    :return: Uploaded supabase public URL for the picture and file name to delete
    """
    file_name = image_path.name

    with open(image_path, "rb") as f:
        supabase.storage.from_(bucket_name).upload(
            file_name,
            f,
            file_options={
                "content-type": "image/jpeg",
                "upsert": False
            }
        )

    public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)

    return public_url, file_name

def delete_image(bucket_name, file_name, image_path):
    """
    Cleaning up the pic data on the bucket as the bucket has limit. Also delete from local SD card
    """
    supabase.storage.from_(bucket_name).remove([file_name]) # delete from supabase bucket

    if os.path.exists(image_path):
        os.remove(image_path) # delete from local SD card
        print(f"Deleted local file: {image_path}")
    else:
        print(f"Local file not found: {image_path}")

    print("Cleanup completed (Supabase + local)")

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
        print("Sent whatsapp message")
    except Exception as e:
        print(e)

if __name__ == "__main__":
    while True:
        if is_active_time():
            if is_door_open() or is_motion():
                image_path = capture_image()
                public_url, file_name = upload_image(image_path, bucket_name)

                time.sleep(3) # Let Supabase settle
                send_whatsapp_message(public_url)

                time.sleep(20) # Wait for Twilio to fetch the image
                delete_image(bucket_name, file_name, image_path)

                time.sleep(10)  # Small delay to avoid busy looping
        else:
            # Sleep longer when inactive to save CPU
            time.sleep(60)
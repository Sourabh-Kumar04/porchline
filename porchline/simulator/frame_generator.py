"""Synthetic scenario snapshot frame generator."""
import os
import io
import base64
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

def generate_scene_image(
    title: str,
    subtitle: str,
    timestamp_str: str,
    visitor_type: str,
    badge_color: str = "#2563eb",
    package_present: bool = False,
    scenario_type: str = "delivery",
) -> bytes:
    """Generate a realistic 640x360 simulated doorbell snapshot frame with visual annotations."""
    width, height = 640, 360
    # Background representing front door porch (doorway, siding, floor mat)
    img = Image.new("RGB", (width, height), color="#1e293b")
    draw = ImageDraw.Draw(img)

    # Porch wall background gradient effect
    draw.rectangle([0, 0, width, height], fill="#1e293b")
    # Front door frame
    draw.rectangle([340, 40, 580, 360], fill="#334155", outline="#475569", width=4)
    # Door panel
    draw.rectangle([360, 60, 560, 360], fill="#0f172a")
    # Door knob
    draw.ellipse([375, 200, 395, 220], fill="#f59e0b")

    # Porch floor & mat
    draw.rectangle([0, 270, width, height], fill="#334155")
    draw.rectangle([280, 290, 520, 350], fill="#78350f", outline="#92400e", width=2)
    draw.text((360, 310), "WELCOME", fill="#d97706")

    # Specific Scenario Visuals
    if package_present or scenario_type in ["package_delivery", "lingering_package"]:
        # Draw parcel box on porch
        draw.rectangle([310, 250, 410, 315], fill="#b45309", outline="#78350f", width=2)
        draw.rectangle([350, 250, 370, 315], fill="#d97706") # Tape
        draw.text((320, 275), "PARCEL", fill="#ffffff")

    if scenario_type == "package_delivery":
        # Draw courier figure silhouette
        draw.ellipse([180, 90, 260, 170], fill="#2563eb") # head
        draw.rectangle([160, 170, 280, 300], fill="#1d4ed8") # body
        draw.text((185, 210), "COURIER", fill="#ffffff")
    elif scenario_type == "neighbor_visit":
        # Friendly neighbor figure
        draw.ellipse([200, 100, 270, 170], fill="#10b981")
        draw.rectangle([180, 170, 290, 300], fill="#059669")
        draw.text((205, 210), "VISITOR", fill="#ffffff")
    elif scenario_type == "pet_detected":
        # Golden retriever / dog
        draw.ellipse([160, 220, 270, 290], fill="#d97706")
        draw.ellipse([140, 200, 190, 250], fill="#b45309")
        draw.polygon([(140, 200), (160, 170), (180, 200)], fill="#78350f")
        draw.text((180, 250), "PET", fill="#ffffff")
    elif scenario_type == "late_night_lingering":
        # Shadowy figure late at night
        draw.rectangle([0, 0, width, height], fill="#090d16")
        draw.ellipse([220, 100, 290, 170], fill="#475569")
        draw.rectangle([200, 170, 310, 310], fill="#334155")
        draw.text((220, 220), "PERSON", fill="#94a3b8")

    # Camera HUD Overlay (Timestamp, Device ID, Ring-style watermark)
    draw.rectangle([10, 10, 320, 75], fill=(15, 23, 42))
    draw.text((20, 16), f"RING SIMULATOR // CAM-FRONT-01", fill="#38bdf8")
    draw.text((20, 34), f"TIME: {timestamp_str}", fill="#f8fafc")
    draw.text((20, 52), f"SCENARIO: {title.upper()}", fill="#a855f7")

    # Badge in bottom corner
    draw.rectangle([ width - 210, height - 45, width - 10, height - 10 ], fill=badge_color)
    draw.text((width - 195, height - 35), f"{subtitle[:24]}", fill="#ffffff")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

def get_base64_scene_image(**kwargs) -> str:
    """Return image as base64 encoded string."""
    raw = generate_scene_image(**kwargs)
    return base64.b64encode(raw).decode("utf-8")

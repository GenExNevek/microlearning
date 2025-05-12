"""Configuration settings for the extraction pipeline."""

import os
from dotenv import load_dotenv

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.env"))

# Load environment variables from .env file
load_dotenv()

# API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"

# Base directory is the microlearning folder
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# File paths - make them relative to the BASE_DIR
PDF_SOURCE_DIR = os.path.join(BASE_DIR, "original_content_pdf")
MARKDOWN_TARGET_DIR = os.path.join(BASE_DIR, "original_content_markdown")
IMAGE_ASSETS_SUFFIX = "-img-assets"

print(f"ENV file path: {ENV_PATH}")
print(f"ENV file exists: {os.path.exists(ENV_PATH)}")
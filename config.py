"""Configuration settings for the metagenomics pipeline."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GCP Configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "")
GCP_ZONE = os.getenv("GCP_ZONE", "us-central1-a")
GCP_SERVICE_ACCOUNT_KEY = os.getenv("GCP_SERVICE_ACCOUNT_KEY", "")

# Repository Configuration
REPOSITORY_URL = os.getenv("REPOSITORY_URL", "https://github.com/sathishthangasamy/metagenomics.git")

# VM Configuration
VM_CONFIGS = {
    "standard": {
        "machine_type": "n1-standard-16",
        "boot_disk_size_gb": 100,
        "preemptible": True,
    },
    "highmem": {
        "machine_type": "n1-highmem-16",
        "boot_disk_size_gb": 100,
        "preemptible": True,
    }
}

# Pipeline Defaults
DEFAULT_THREADS = 16
DEFAULT_MIN_CONTIG_LEN = 1000

# Pipeline Steps
PIPELINE_STEPS = {
    "fastqc": {"name": "FastQC", "enabled": True, "emoji": "🔍"},
    "trimmomatic": {"name": "Trimmomatic", "enabled": True, "emoji": "✂️"},
    "megahit": {"name": "MEGAHIT Assembly", "enabled": True, "emoji": "🧬"},
    "prodigal": {"name": "Prodigal", "enabled": True, "emoji": "🔬"},
    "hmmscan": {"name": "HMMscan (Pfam)", "enabled": True, "emoji": "🎯"},
    "binning": {"name": "MetaBAT2 Binning", "enabled": True, "emoji": "📦"},
    "checkm": {"name": "CheckM Quality", "enabled": True, "emoji": "✓"},
}

# Cost Estimation (per hour in USD)
COST_PER_HOUR = {
    "n1-standard-16": 0.38,  # Preemptible price
    "n1-highmem-16": 0.47,   # Preemptible price
}

# File size limits
MAX_FILE_SIZE_GB = 30
CHUNK_SIZE_MB = 256  # For chunked uploads

# Paths
BASE_DIR = Path(__file__).parent
UI_DIR = BASE_DIR / "ui"
GCP_DIR = BASE_DIR / "gcp"
PIPELINE_DIR = BASE_DIR / "pipeline"

# Gradio Configuration
GRADIO_SERVER_NAME = "0.0.0.0"
GRADIO_SERVER_PORT = 7860
GRADIO_SHARE = False

# Status emojis
STATUS_EMOJIS = {
    "pending": "⏳",
    "running": "🔄",
    "complete": "✅",
    "failed": "❌",
    "cancelled": "🚫",
}

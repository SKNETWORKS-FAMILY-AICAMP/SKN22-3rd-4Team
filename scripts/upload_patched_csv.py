import os
import pandas as pd
import numpy as np
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_KEY missing in .env")
    exit(1)

client = create_client(url, key)

CSV_PATH = "data/annual_reports_patched.csv"


def upload_patched_data():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found. Please run patch_csv_revenue.py first.")
        return

    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)

    # Replace NaN with None for JSON compatibility
    df = df.replace({np.nan: None})

    # Prepare records
    records = df.to_dict(orient="records")
    print(f"Prepared {len(records)} records for upload.")

    # Upsert in chunks to avoid request size limits
    CHUNK_SIZE = 100
    total_chunks = (len(records) + CHUNK_SIZE - 1) // CHUNK_SIZE

    print("Starting Upsert...")
    for i in range(0, len(records), CHUNK_SIZE):
        chunk = records[i : i + CHUNK_SIZE]
        try:
            # Upsert will Insert or Update if ID exists
            client.table("annual_reports").upsert(chunk).execute()
            print(f"Uploaded chunk {i//CHUNK_SIZE + 1}/{total_chunks}")
        except Exception as e:
            print(f"Error uploading chunk {i//CHUNK_SIZE + 1}: {e}")

    print("Upload Complete.")


if __name__ == "__main__":
    upload_patched_data()

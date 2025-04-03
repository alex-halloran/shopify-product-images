#!/usr/bin/env python3
"""
Simplified script to download images from Dropbox and upload them to GitHub.
This version requires fewer dependencies and is easier to run.

Requirements:
- requests

Installation:
pip install requests
"""

import os
import csv
import requests
import hashlib
import time
import json
from urllib.parse import urlparse

# Configuration
GITHUB_TOKEN = "your_github_token"  # Create a GitHub personal access token
GITHUB_REPO = "alex-halloran/shopify-product-images"
GITHUB_USER = GITHUB_REPO.split('/')[0]
GITHUB_REPO_NAME = GITHUB_REPO.split('/')[1]
BATCH_SIZE = 10  # Process images in small batches to avoid rate limits

# Function to convert Dropbox URL to direct download URL
def get_download_url(url):
    if 'dropbox.com' in url and 'dl=0' in url:
        return url.replace('dl=0', 'dl=1')
    return url

# Function to get a safe filename from a URL
def get_safe_filename(url):
    # Get the filename from the URL
    parsed_url = urlparse(url)
    path = parsed_url.path
    filename = os.path.basename(path).split('?')[0]
    
    # If filename is too long or contains special characters, hash it
    if len(filename) > 100 or '?' in filename or '&' in filename:
        hash_object = hashlib.md5(url.encode())
        file_ext = os.path.splitext(filename)[1] or '.jpg'  # Default to .jpg if no extension
        filename = hash_object.hexdigest() + file_ext
    
    return filename

# Function to download an image from Dropbox
def download_image(url):
    try:
        download_url = get_download_url(url)
        response = requests.get(download_url, stream=True, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading {url}: {str(e)}")
        return None

# Function to upload an image to GitHub using REST API
def upload_to_github(url):
    try:
        # Get a safe filename for GitHub
        filename = get_safe_filename(url)
        
        # Path in the repo
        path = f"images/{filename}"
        
        # Download the image
        print(f"Downloading {url}...")
        image_data = download_image(url)
        if not image_data:
            return url, None
            
        # GitHub API URL for creating/updating files
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # First check if the file exists
        print(f"Checking if {filename} exists in repository...")
        response = requests.get(api_url, headers=headers)
        
        # Prepare the request data
        import base64
        content_b64 = base64.b64encode(image_data).decode('utf-8')
        data = {
            "message": f"Add image {filename}",
            "content": content_b64,
            "branch": "main"
        }
        
        # If file exists, include its SHA for updating
        if response.status_code == 200:
            file_info = response.json()
            data["sha"] = file_info["sha"]
            print(f"Updating existing file {filename}...")
        else:
            print(f"Creating new file {filename}...")
            
        # Upload the file
        response = requests.put(api_url, headers=headers, data=json.dumps(data))
        
        if response.status_code in [200, 201]:
            # Generate GitHub Pages URL
            github_pages_url = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO_NAME}/images/{filename}"
            print(f"Successfully uploaded to {github_pages_url}")
            return url, github_pages_url
        else:
            print(f"Error uploading to GitHub: {response.status_code} - {response.text}")
            return url, None
    except Exception as e:
        print(f"Error uploading {url} to GitHub: {str(e)}")
        return url, None

def process_csv(csv_file):
    # Dictionary to store URL mappings
    url_mappings = {}
    
    # Read the CSV file and extract Dropbox URLs
    print(f"Reading {csv_file}...")
    dropbox_urls = set()
    
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if 'Image Src' in row and row['Image Src'] and 'dropbox.com' in row['Image Src']:
                dropbox_urls.add(row['Image Src'])
            if 'Variant Image' in row and row['Variant Image'] and 'dropbox.com' in row['Variant Image']:
                dropbox_urls.add(row['Variant Image'])
    
    dropbox_urls = list(dropbox_urls)
    print(f"Found {len(dropbox_urls)} unique Dropbox image URLs")
    
    # Create images directory if it doesn't exist locally
    os.makedirs('images', exist_ok=True)
    
    # Process URLs in batches to avoid rate limits
    for batch_index, i in enumerate(range(0, len(dropbox_urls), BATCH_SIZE)):
        batch = dropbox_urls[i:i+BATCH_SIZE]
        print(f"\nProcessing batch {batch_index+1}/{(len(dropbox_urls) + BATCH_SIZE - 1) // BATCH_SIZE}...")
        
        for url in batch:
            original_url, github_url = upload_to_github(url)
            if github_url:
                url_mappings[original_url] = github_url
        
        # Sleep between batches to avoid rate limits
        if batch_index < (len(dropbox_urls) + BATCH_SIZE - 1) // BATCH_SIZE - 1:
            print(f"Waiting 10 seconds to avoid rate limits...")
            time.sleep(10)
    
    # Create a new CSV with GitHub URLs
    output_csv = os.path.splitext(csv_file)[0] + '_with_github_urls.csv'
    mappings_csv = 'dropbox_to_github_mappings.csv'
    
    print(f"\nCreating updated CSV at {output_csv}...")
    with open(csv_file, 'r', encoding='utf-8') as infile, \
         open(output_csv, 'w', encoding='utf-8', newline='') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ['GitHub_Image_Src', 'GitHub_Variant_Image']
        
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in reader:
            # Add GitHub URLs to the row
            if 'Image Src' in row and row['Image Src'] in url_mappings:
                row['GitHub_Image_Src'] = url_mappings[row['Image Src']]
            else:
                row['GitHub_Image_Src'] = ''
                
            if 'Variant Image' in row and row['Variant Image'] in url_mappings:
                row['GitHub_Variant_Image'] = url_mappings[row['Variant Image']]
            else:
                row['GitHub_Variant_Image'] = ''
                
            writer.writerow(row)
    
    # Write just the mappings to a separate CSV
    print(f"Creating URL mappings at {mappings_csv}...")
    with open(mappings_csv, 'w', encoding='utf-8', newline='') as mapfile:
        map_writer = csv.writer(mapfile)
        map_writer.writerow(['Dropbox_URL', 'GitHub_URL'])
        for dropbox_url, github_url in url_mappings.items():
            map_writer.writerow([dropbox_url, github_url])
    
    print(f"\nProcess complete!")
    print(f"Processed {len(url_mappings)} images.")
    print(f"Updated CSV saved to {output_csv}")
    print(f"URL mappings saved to {mappings_csv}")
    
    # Remind about GitHub Pages
    print("\nIMPORTANT: Make sure to enable GitHub Pages for your repository:")
    print("1. Go to https://github.com/alex-halloran/shopify-product-images/settings/pages")
    print("2. Select 'Deploy from a branch' under Source")
    print("3. Select 'main' branch and '/ (root)' folder")
    print("4. Click Save")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python simple_upload.py your_shopify_import.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    process_csv(csv_file)

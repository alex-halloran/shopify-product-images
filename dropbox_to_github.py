#!/usr/bin/env python3
"""
Script to transfer images from Dropbox links to GitHub Pages and generate URL mappings.

Requirements:
- pandas
- requests
- PyGithub

Installation:
pip install pandas requests PyGithub
"""

import os
import pandas as pd
import requests
import time
import hashlib
from github import Github
from urllib.parse import urlparse, quote
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
GITHUB_TOKEN = "your_github_token"  # Create a personal access token with repo scope
GITHUB_REPO = "alex-halloran/shopify-product-images"
BATCH_SIZE = 50  # Number of files to upload in each batch (to avoid rate limits)
MAX_WORKERS = 5  # Maximum number of concurrent threads

# Initialize GitHub API
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

# Get the default branch
default_branch = repo.default_branch

# Make sure the 'images' directory exists
try:
    repo.get_contents("images", ref=default_branch)
except Exception:
    repo.create_file(
        "images/.gitkeep", 
        "Create images directory", 
        "", 
        branch=default_branch
    )
    print("Created 'images' directory in the repository")

# Create the gh-pages branch if it doesn't exist
try:
    repo.get_branch("gh-pages")
    print("gh-pages branch already exists")
except Exception:
    # Create gh-pages branch from the default branch
    sb = repo.get_branch(default_branch)
    repo.create_git_ref(ref=f"refs/heads/gh-pages", sha=sb.commit.sha)
    print("Created gh-pages branch")

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

# Function to upload an image to GitHub
def upload_to_github(url, batch_index):
    try:
        # Get a safe filename for GitHub
        filename = get_safe_filename(url)
        
        # Path in the repo
        path = f"images/{filename}"
        
        # Download the image
        image_data = download_image(url)
        if not image_data:
            return url, None
            
        # Upload to GitHub
        content = base64.b64encode(image_data).decode()
        commit_message = f"Add image {filename} [batch {batch_index}]"
        
        try:
            # Try to get the file first to update it
            file = repo.get_contents(path, ref=default_branch)
            repo.update_file(path, commit_message, content, file.sha, branch=default_branch)
        except Exception:
            # File doesn't exist, create it
            repo.create_file(path, commit_message, content, branch=default_branch)
        
        # Generate GitHub Pages URL
        github_pages_url = f"https://{repo.owner.login}.github.io/{repo.name}/images/{quote(filename)}"
        
        return url, github_pages_url
    except Exception as e:
        print(f"Error uploading {url} to GitHub: {str(e)}")
        return url, None

def process_csv(csv_file):
    # Read the Shopify CSV
    df = pd.read_csv(csv_file)
    
    # Create a list of all unique Dropbox URLs
    dropbox_urls = []
    
    if 'Image Src' in df.columns:
        dropbox_urls.extend(df.loc[df['Image Src'].str.contains('dropbox.com', na=False), 'Image Src'].unique())
    
    if 'Variant Image' in df.columns:
        dropbox_urls.extend(df.loc[df['Variant Image'].str.contains('dropbox.com', na=False), 'Variant Image'].unique())
    
    # Remove duplicates
    dropbox_urls = list(set(dropbox_urls))
    
    print(f"Found {len(dropbox_urls)} unique Dropbox image URLs")
    
    # Create a dictionary to store URL mappings
    url_mappings = {}
    
    # Process URLs in batches with multiple threads to handle rate limits
    for batch_index, i in enumerate(range(0, len(dropbox_urls), BATCH_SIZE)):
        batch = dropbox_urls[i:i+BATCH_SIZE]
        print(f"Processing batch {batch_index+1}/{(len(dropbox_urls) + BATCH_SIZE - 1) // BATCH_SIZE}...")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Upload images in parallel
            future_to_url = {executor.submit(upload_to_github, url, batch_index): url for url in batch}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    original_url, github_url = future.result()
                    if github_url:
                        url_mappings[original_url] = github_url
                        print(f"Uploaded: {original_url} → {github_url}")
                    else:
                        print(f"Failed to upload: {url}")
                except Exception as e:
                    print(f"Error processing {url}: {str(e)}")
        
        # Sleep between batches to avoid rate limits
        if batch_index < (len(dropbox_urls) + BATCH_SIZE - 1) // BATCH_SIZE - 1:
            print(f"Waiting to avoid rate limits...")
            time.sleep(10)
    
    # Update the CSV with GitHub URLs
    if 'Image Src' in df.columns:
        df['GitHub_Image_Src'] = df['Image Src'].map(lambda x: url_mappings.get(x, x))
    
    if 'Variant Image' in df.columns:
        df['GitHub_Variant_Image'] = df['Variant Image'].map(lambda x: url_mappings.get(x, x))
    
    # Save the updated CSV
    output_csv = os.path.splitext(csv_file)[0] + '_with_github_urls.csv'
    df.to_csv(output_csv, index=False)
    
    # Save just the mappings
    mappings_df = pd.DataFrame({
        'Dropbox_URL': list(url_mappings.keys()),
        'GitHub_URL': list(url_mappings.values())
    })
    mappings_csv = 'dropbox_to_github_mappings.csv'
    mappings_df.to_csv(mappings_csv, index=False)
    
    print(f"Processed {len(url_mappings)} images.")
    print(f"Updated CSV saved to {output_csv}")
    print(f"URL mappings saved to {mappings_csv}")
    
    # Check if we need to publish to the gh-pages branch
    try:
        # Create a file in the gh-pages branch to enable GitHub Pages
        index_content = """<!DOCTYPE html>
<html>
<head>
    <title>GitHub Pages Image Hosting</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
    </style>
</head>
<body>
    <h1>GitHub Pages Image Hosting</h1>
    <p>This repository hosts images for Shopify import.</p>
</body>
</html>"""
        
        try:
            file = repo.get_contents("index.html", ref="gh-pages")
            repo.update_file("index.html", "Update index.html", index_content, file.sha, branch="gh-pages")
        except Exception:
            repo.create_file("index.html", "Create index.html", index_content, branch="gh-pages")
        
        # Copy the images directory to gh-pages
        contents = repo.get_contents("images", ref=default_branch)
        for content in contents:
            if content.path == "images/.gitkeep":
                continue
                
            try:
                file_content = repo.get_contents(content.path, ref=default_branch)
                
                try:
                    dest_file = repo.get_contents(content.path, ref="gh-pages")
                    repo.update_file(
                        content.path,
                        f"Update {content.path}",
                        file_content.content,
                        dest_file.sha,
                        branch="gh-pages"
                    )
                except Exception:
                    repo.create_file(
                        content.path,
                        f"Add {content.path}",
                        file_content.content,
                        branch="gh-pages"
                    )
            except Exception as e:
                print(f"Error copying {content.path} to gh-pages: {str(e)}")
        
        print("Updated gh-pages branch for GitHub Pages")
    except Exception as e:
        print(f"Error updating gh-pages branch: {str(e)}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python dropbox_to_github.py your_shopify_import.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    process_csv(csv_file)

# Shopify Product Images Hosting

This repository hosts product images for Shopify imports, serving them through GitHub Pages.

## Usage Instructions

### 1. Set Up Your Environment

```bash
# Clone the repository
git clone https://github.com/alex-halloran/shopify-product-images.git
cd shopify-product-images

# Install required packages
pip install pandas requests PyGithub
```

### 2. Create a GitHub Personal Access Token

1. Go to [GitHub Settings > Developer Settings > Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token" (classic)
3. Name it something like "Shopify Image Upload"
4. Select the "repo" scope (full control of private repositories)
5. Click "Generate token" and copy the token (you'll need it for the script)

### 3. Configure the Script

Edit the `dropbox_to_github.py` file and update these variables:

```python
# Configuration
GITHUB_TOKEN = "your_github_token"  # Paste your token here
GITHUB_REPO = "alex-halloran/shopify-product-images"  # Use your GitHub username
```

### 4. Run the Script

```bash
python dropbox_to_github.py your_shopify_import.csv
```

The script will:
1. Extract all Dropbox image URLs from your CSV
2. Download each image from Dropbox
3. Upload it to this GitHub repository
4. Generate a new CSV with GitHub Pages URLs
5. Create a mapping file showing original Dropbox URLs and their GitHub Pages equivalents

### 5. Use the Updated CSV

The script generates two output files:
- `your_shopify_import_with_github_urls.csv` - Your original CSV with new columns for GitHub URLs
- `dropbox_to_github_mappings.csv` - Just the URL mappings

### Important Notes

- GitHub has storage limits (recommended to stay under 5GB per repository)
- The script processes images in batches with pauses to avoid GitHub API rate limits
- Images are available at https://your-username.github.io/shopify-product-images/images/filename

## Troubleshooting

If you encounter any issues:

- Check GitHub's status at [status.github.com](https://status.github.com)
- Make sure your personal access token has not expired
- Verify that GitHub Pages is enabled for this repository (Settings > Pages)

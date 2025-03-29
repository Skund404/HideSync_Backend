# Media Asset Management System

## Overview

The Media Asset Management System provides a comprehensive solution for storing, organizing, and retrieving digital media files within the HideSync application. It enables users to upload various file types, categorize them with tags, and efficiently search through the media library.

## Key Features

- **File Upload & Storage**: Securely store digital files with proper metadata tracking
- **Tagging System**: Organize and categorize media assets with customizable tags
- **Search & Filter**: Find media assets by name, type, tags, or general search terms
- **Direct File Access**: Stream or download media files directly from the API
- **Tag Management**: Create, update, and delete tags with color coding support
- **Asset-Tag Association**: Add or remove tags from assets as needed

## Data Models

### MediaAsset

Represents a digital file stored in the system.

| Field | Type | Description |
|-------|------|-------------|
| id | String (UUID) | Unique identifier for the media asset |
| file_name | String | Name of the file |
| file_type | String | Type or extension of the file |
| storage_location | String | Where the file is physically stored |
| content_type | String | MIME type of the file |
| file_size_bytes | Integer | Size of the file in bytes |
| uploaded_at | DateTime | When the file was uploaded |
| uploaded_by | String | User who uploaded the file |
| created_at | DateTime | When the record was created |
| updated_at | DateTime | When the record was last updated |

### Tag

Represents a category label that can be applied to media assets.

| Field | Type | Description |
|-------|------|-------------|
| id | String (UUID) | Unique identifier for the tag |
| name | String | Name of the tag (unique) |
| description | String | Optional description of the tag |
| color | String | Optional color code (hex format) |
| created_at | DateTime | When the tag was created |

### MediaAssetTag

Associates media assets with tags in a many-to-many relationship.

| Field | Type | Description |
|-------|------|-------------|
| id | String (UUID) | Unique identifier for the association |
| media_asset_id | String (UUID) | Reference to the media asset |
| tag_id | String (UUID) | Reference to the tag |

## API Endpoints

### Media Assets

#### List Media Assets

```
GET /api/media-assets
```

Query parameters:
- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Maximum number of records to return (default: 100)
- `sort_by` (string): Field to sort by (default: "uploaded_at")
- `sort_dir` (string): Sort direction ("asc" or "desc", default: "desc")
- `file_name` (string): Filter by file name
- `file_type` (string): Filter by file type
- `tag_ids` (array): Filter by tag IDs
- `uploaded_by` (string): Filter by uploader
- `search` (string): General search term

Returns:
- Paginated list of media assets with metadata

#### Get Media Asset

```
GET /api/media-assets/{asset_id}
```

Parameters:
- `asset_id` (UUID): The ID of the media asset

Returns:
- Detailed information about the specified media asset

#### Create Media Asset

```
POST /api/media-assets
```

Request body:
- `file_name` (string): Name of the file
- `file_type` (string): Type or extension of the file
- `content_type` (string): MIME type of the file
- `uploaded_by` (string): User who uploaded the file
- `tag_ids` (array, optional): List of tag IDs to assign

Returns:
- Created media asset information

#### Upload Media Asset

```
POST /api/media-assets/upload
```

Form data:
- `file` (file): The file to upload
- `tag_ids` (array, optional): List of tag IDs to assign

Returns:
- Created media asset information

#### Download Media Asset

```
GET /api/media-assets/{asset_id}/download
```

Parameters:
- `asset_id` (UUID): The ID of the media asset

Returns:
- Streaming response with the file content

#### Update Media Asset

```
PUT /api/media-assets/{asset_id}
```

Parameters:
- `asset_id` (UUID): The ID of the media asset

Request body:
- `file_name` (string, optional): New name of the file
- `tag_ids` (array, optional): New list of tag IDs to assign

Returns:
- Updated media asset information

#### Update Media Asset File

```
POST /api/media-assets/{asset_id}/upload
```

Parameters:
- `asset_id` (UUID): The ID of the media asset

Form data:
- `file` (file): The new file to upload

Returns:
- Updated media asset information

#### Delete Media Asset

```
DELETE /api/media-assets/{asset_id}
```

Parameters:
- `asset_id` (UUID): The ID of the media asset

Returns:
- No content (204)

#### Add Tags to Asset

```
POST /api/media-assets/{asset_id}/tags
```

Parameters:
- `asset_id` (UUID): The ID of the media asset

Request body:
- `tag_ids` (array): List of tag IDs to add

Returns:
- Updated media asset information

#### Remove Tags from Asset

```
DELETE /api/media-assets/{asset_id}/tags
```

Parameters:
- `asset_id` (UUID): The ID of the media asset

Request body:
- `tag_ids` (array): List of tag IDs to remove

Returns:
- Updated media asset information

### Tags

#### List Tags

```
GET /api/tags
```

Query parameters:
- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Maximum number of records to return (default: 100)
- `sort_by` (string): Field to sort by (default: "name")
- `sort_dir` (string): Sort direction ("asc" or "desc", default: "asc")
- `name` (string): Filter by tag name
- `search` (string): General search term

Returns:
- Paginated list of tags

#### Get Tag

```
GET /api/tags/{tag_id}
```

Parameters:
- `tag_id` (UUID): The ID of the tag

Returns:
- Detailed information about the specified tag

#### Create Tag

```
POST /api/tags
```

Request body:
- `name` (string): Name of the tag (must be unique)
- `description` (string, optional): Description of the tag
- `color` (string, optional): Color code for the tag (hex format)

Returns:
- Created tag information

#### Update Tag

```
PUT /api/tags/{tag_id}
```

Parameters:
- `tag_id` (UUID): The ID of the tag

Request body:
- `name` (string, optional): New name of the tag
- `description` (string, optional): New description of the tag
- `color` (string, optional): New color code for the tag

Returns:
- Updated tag information

#### Delete Tag

```
DELETE /api/tags/{tag_id}
```

Parameters:
- `tag_id` (UUID): The ID of the tag

Returns:
- No content (204)

#### Get Tag Assets

```
GET /api/tags/{tag_id}/assets
```

Parameters:
- `tag_id` (UUID): The ID of the tag
- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Maximum number of records to return (default: 100)

Returns:
- List of media asset IDs associated with the tag

#### Get Asset Count by Tag

```
GET /api/tags/{tag_id}/count
```

Parameters:
- `tag_id` (UUID): The ID of the tag

Returns:
- Number of media assets associated with the tag

## Usage Examples

### Uploading a Media Asset

```python
import requests

# API endpoint
url = "https://api.example.com/api/media-assets/upload"

# File to upload
files = {"file": open("product_image.jpg", "rb")}

# Optional tags
data = {"tag_ids": ["tag-uuid-1", "tag-uuid-2"]}

# Authentication headers
headers = {"Authorization": "Bearer YOUR_ACCESS_TOKEN"}

# Upload the file
response = requests.post(url, files=files, data=data, headers=headers)

# Check if successful
if response.status_code == 201:
    media_asset = response.json()
    print(f"Uploaded successfully. Asset ID: {media_asset['id']}")
else:
    print(f"Upload failed: {response.text}")
```

### Creating a Tag and Adding it to Assets

```python
import requests

# API endpoint for creating a tag
tag_url = "https://api.example.com/api/tags"

# Tag data
tag_data = {
    "name": "Product Photos",
    "description": "Official product photography",
    "color": "#FF5733"
}

# Authentication headers
headers = {
    "Authorization": "Bearer YOUR_ACCESS_TOKEN",
    "Content-Type": "application/json"
}

# Create the tag
tag_response = requests.post(tag_url, json=tag_data, headers=headers)

if tag_response.status_code == 201:
    tag = tag_response.json()
    tag_id = tag["id"]
    print(f"Tag created successfully. Tag ID: {tag_id}")
    
    # Now add this tag to an existing asset
    asset_id = "existing-asset-uuid"
    tag_asset_url = f"https://api.example.com/api/media-assets/{asset_id}/tags"
    
    tag_asset_data = {
        "tag_ids": [tag_id]
    }
    
    # Add tag to asset
    tag_asset_response = requests.post(tag_asset_url, json=tag_asset_data, headers=headers)
    
    if tag_asset_response.status_code == 200:
        print("Tag added to asset successfully")
    else:
        print(f"Failed to add tag to asset: {tag_asset_response.text}")
else:
    print(f"Tag creation failed: {tag_response.text}")
```

### Searching for Media Assets by Tags

```python
import requests

# API endpoint
url = "https://api.example.com/api/media-assets"

# Query parameters
params = {
    "tag_ids": ["tag-uuid-1", "tag-uuid-2"],
    "file_type": ".jpg",
    "limit": 50,
    "sort_by": "uploaded_at",
    "sort_dir": "desc"
}

# Authentication headers
headers = {"Authorization": "Bearer YOUR_ACCESS_TOKEN"}

# Search for assets
response = requests.get(url, params=params, headers=headers)

if response.status_code == 200:
    result = response.json()
    assets = result["items"]
    print(f"Found {len(assets)} assets out of {result['total']} total")
    for asset in assets:
        print(f"Asset: {asset['file_name']} (ID: {asset['id']})")
else:
    print(f"Search failed: {response.text}")
```

## Integration with Other Modules

The Media Asset Management System integrates with several other modules in the HideSync platform:

### Projects Module

Media assets can be associated with projects for design files, progress photos, and documentation.

### Products Module

Product images and related media can be managed through the Media Asset Management System.

### Documentation Module

Technical documents, manuals, and guides can be stored and categorized as media assets.

### Customer Module

Customer-specific files like design approvals and custom order references can be stored as media assets.

## Best Practices

1. **Tagging Strategy**: Develop a consistent tagging taxonomy to make finding assets easier
2. **File Naming**: Use clear, descriptive file names that follow a consistent pattern
3. **Metadata Management**: Keep file metadata accurate and up-to-date
4. **Regular Cleanup**: Periodically remove unused or outdated assets
5. **Permission Control**: Use appropriate access controls to protect sensitive assets
6. **Batch Operations**: Use batch uploads and tag assignments for efficiency

## Limitations and Considerations

- **File Size Limits**: Maximum file size is 100MB per upload
- **Supported File Types**: Common image, document, and media formats (jpg, png, gif, pdf, doc, docx, xlsx, csv, svg)
- **Storage Considerations**: Large media libraries may require storage planning
- **Performance**: Querying by multiple tags can impact performance on very large collections
- 
https://claude.ai/chat/0ec1f80c-2f37-4c65-9a20-e4859c3699a4
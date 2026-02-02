"""
Cloud Storage Integration

Supports streaming media from:
- Google Drive
- Dropbox
- Amazon S3 / Backblaze B2
- OneDrive
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import httpx

logger = logging.getLogger(__name__)


class CloudProvider(str, Enum):
    """Supported cloud storage providers."""
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    S3 = "s3"
    ONEDRIVE = "onedrive"


@dataclass
class CloudFile:
    """A file in cloud storage."""
    
    id: str
    name: str
    path: str
    size: int
    mime_type: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    
    # Media info
    duration: Optional[int] = None
    is_video: bool = False
    is_folder: bool = False
    
    # Provider-specific
    provider: Optional[CloudProvider] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "mime_type": self.mime_type,
            "is_video": self.is_video,
            "is_folder": self.is_folder,
            "provider": self.provider.value if self.provider else None,
        }


@dataclass
class CloudStorageConfig:
    """Base configuration for cloud storage."""
    
    name: str
    provider: CloudProvider
    is_enabled: bool = True
    
    # Scan settings
    root_folder: str = "/"
    file_extensions: List[str] = field(default_factory=lambda: [
        ".mp4", ".mkv", ".avi", ".mov", ".m4v", ".ts"
    ])


class CloudStorageProvider(ABC):
    """Abstract base for cloud storage providers."""
    
    def __init__(self, config: CloudStorageConfig):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self._http_client = httpx.AsyncClient(timeout=60.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._http_client:
            await self._http_client.aclose()
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the provider."""
        pass
    
    @abstractmethod
    async def list_files(
        self,
        folder_id: Optional[str] = None,
    ) -> List[CloudFile]:
        """List files in a folder."""
        pass
    
    @abstractmethod
    async def get_stream_url(
        self,
        file_id: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Get a streaming URL for a file."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test the connection."""
        pass
    
    def is_video_file(self, filename: str) -> bool:
        """Check if file is a video based on extension."""
        ext = Path(filename).suffix.lower()
        return ext in self.config.file_extensions


# ============================================================================
# Google Drive
# ============================================================================

@dataclass
class GoogleDriveConfig(CloudStorageConfig):
    """Google Drive configuration."""
    
    provider: CloudProvider = CloudProvider.GOOGLE_DRIVE
    
    # OAuth credentials
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    
    # Cached access token
    access_token: Optional[str] = None
    token_expires: Optional[datetime] = None


class GoogleDriveProvider(CloudStorageProvider):
    """Google Drive storage provider."""
    
    API_BASE = "https://www.googleapis.com/drive/v3"
    AUTH_URL = "https://oauth2.googleapis.com/token"
    
    def __init__(self, config: GoogleDriveConfig):
        super().__init__(config)
        self.gdrive_config = config
    
    async def authenticate(self) -> bool:
        """Refresh OAuth access token."""
        try:
            response = await self._http_client.post(
                self.AUTH_URL,
                data={
                    "client_id": self.gdrive_config.client_id,
                    "client_secret": self.gdrive_config.client_secret,
                    "refresh_token": self.gdrive_config.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            
            data = response.json()
            self.gdrive_config.access_token = data["access_token"]
            self.gdrive_config.token_expires = datetime.now() + timedelta(
                seconds=data.get("expires_in", 3600)
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Google Drive auth failed: {e}")
            return False
    
    async def list_files(
        self,
        folder_id: Optional[str] = None,
    ) -> List[CloudFile]:
        """List files in Google Drive."""
        if not await self._ensure_authenticated():
            return []
        
        try:
            folder = folder_id or self.config.root_folder
            if folder == "/":
                folder = "root"
            
            # Query for files
            query = f"'{folder}' in parents and trashed = false"
            
            params = {
                "q": query,
                "fields": "files(id,name,mimeType,size,createdTime,modifiedTime)",
                "pageSize": 1000,
            }
            
            response = await self._http_client.get(
                f"{self.API_BASE}/files",
                params=params,
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            
            data = response.json()
            files = []
            
            for item in data.get("files", []):
                is_folder = item["mimeType"] == "application/vnd.google-apps.folder"
                is_video = (
                    not is_folder and 
                    (item["mimeType"].startswith("video/") or
                     self.is_video_file(item["name"]))
                )
                
                cloud_file = CloudFile(
                    id=item["id"],
                    name=item["name"],
                    path=f"/{item['name']}",
                    size=int(item.get("size", 0)),
                    mime_type=item["mimeType"],
                    is_video=is_video,
                    is_folder=is_folder,
                    provider=CloudProvider.GOOGLE_DRIVE,
                    raw_data=item,
                )
                files.append(cloud_file)
            
            return files
        
        except Exception as e:
            logger.error(f"Failed to list Google Drive files: {e}")
            return []
    
    async def get_stream_url(
        self,
        file_id: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Get streaming URL for a file."""
        if not await self._ensure_authenticated():
            return None
        
        # Google Drive direct download URL
        return (
            f"https://www.googleapis.com/drive/v3/files/{file_id}"
            f"?alt=media&access_token={self.gdrive_config.access_token}"
        )
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test Google Drive connection."""
        try:
            if not await self.authenticate():
                return False, "Authentication failed"
            
            # Get drive info
            response = await self._http_client.get(
                f"{self.API_BASE}/about",
                params={"fields": "user(displayName,emailAddress)"},
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            
            data = response.json()
            email = data.get("user", {}).get("emailAddress", "unknown")
            
            return True, f"Connected as {email}"
        
        except Exception as e:
            return False, str(e)
    
    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token."""
        if (self.gdrive_config.access_token and 
            self.gdrive_config.token_expires and
            datetime.now() < self.gdrive_config.token_expires):
            return True
        
        return await self.authenticate()
    
    def _auth_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.gdrive_config.access_token}",
        }


# ============================================================================
# Dropbox
# ============================================================================

@dataclass
class DropboxConfig(CloudStorageConfig):
    """Dropbox configuration."""
    
    provider: CloudProvider = CloudProvider.DROPBOX
    access_token: str = ""


class DropboxProvider(CloudStorageProvider):
    """Dropbox storage provider."""
    
    API_BASE = "https://api.dropboxapi.com/2"
    CONTENT_BASE = "https://content.dropboxapi.com/2"
    
    def __init__(self, config: DropboxConfig):
        super().__init__(config)
        self.dropbox_config = config
    
    async def authenticate(self) -> bool:
        """Verify Dropbox token."""
        try:
            response = await self._http_client.post(
                f"{self.API_BASE}/users/get_current_account",
                headers=self._auth_headers(),
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def list_files(
        self,
        folder_id: Optional[str] = None,
    ) -> List[CloudFile]:
        """List files in Dropbox."""
        try:
            path = folder_id or self.config.root_folder
            if path == "/":
                path = ""
            
            response = await self._http_client.post(
                f"{self.API_BASE}/files/list_folder",
                headers=self._auth_headers(),
                json={"path": path},
            )
            response.raise_for_status()
            
            data = response.json()
            files = []
            
            for entry in data.get("entries", []):
                is_folder = entry[".tag"] == "folder"
                is_video = not is_folder and self.is_video_file(entry["name"])
                
                cloud_file = CloudFile(
                    id=entry.get("id", entry["path_lower"]),
                    name=entry["name"],
                    path=entry["path_lower"],
                    size=entry.get("size", 0),
                    is_video=is_video,
                    is_folder=is_folder,
                    provider=CloudProvider.DROPBOX,
                    raw_data=entry,
                )
                files.append(cloud_file)
            
            return files
        
        except Exception as e:
            logger.error(f"Failed to list Dropbox files: {e}")
            return []
    
    async def get_stream_url(
        self,
        file_id: str,
        expires_in: int = 14400,
    ) -> Optional[str]:
        """Get temporary streaming link."""
        try:
            response = await self._http_client.post(
                f"{self.API_BASE}/files/get_temporary_link",
                headers=self._auth_headers(),
                json={"path": file_id},
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("link")
        
        except Exception as e:
            logger.error(f"Failed to get Dropbox stream URL: {e}")
            return None
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test Dropbox connection."""
        try:
            response = await self._http_client.post(
                f"{self.API_BASE}/users/get_current_account",
                headers=self._auth_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                email = data.get("email", "unknown")
                return True, f"Connected as {email}"
            
            return False, f"HTTP {response.status_code}"
        
        except Exception as e:
            return False, str(e)
    
    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.dropbox_config.access_token}",
            "Content-Type": "application/json",
        }


# ============================================================================
# S3/B2 Compatible
# ============================================================================

@dataclass
class S3Config(CloudStorageConfig):
    """S3-compatible storage configuration."""
    
    provider: CloudProvider = CloudProvider.S3
    
    # S3 settings
    endpoint_url: str = ""  # e.g., https://s3.amazonaws.com or B2 endpoint
    bucket_name: str = ""
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    
    # Path prefix
    prefix: str = ""


class S3Provider(CloudStorageProvider):
    """S3-compatible storage provider."""
    
    def __init__(self, config: S3Config):
        super().__init__(config)
        self.s3_config = config
        self._s3_client = None
    
    async def authenticate(self) -> bool:
        """Initialize S3 client."""
        try:
            import boto3
            from botocore.config import Config
            
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.s3_config.endpoint_url or None,
                aws_access_key_id=self.s3_config.access_key,
                aws_secret_access_key=self.s3_config.secret_key,
                region_name=self.s3_config.region,
                config=Config(signature_version="s3v4"),
            )
            
            return True
        
        except ImportError:
            logger.error("boto3 package required for S3 support")
            return False
        except Exception as e:
            logger.error(f"S3 auth failed: {e}")
            return False
    
    async def list_files(
        self,
        folder_id: Optional[str] = None,
    ) -> List[CloudFile]:
        """List files in S3 bucket."""
        if not self._s3_client:
            if not await self.authenticate():
                return []
        
        try:
            prefix = folder_id or self.s3_config.prefix
            
            response = self._s3_client.list_objects_v2(
                Bucket=self.s3_config.bucket_name,
                Prefix=prefix,
                MaxKeys=1000,
            )
            
            files = []
            for obj in response.get("Contents", []):
                key = obj["Key"]
                name = key.split("/")[-1]
                
                if not name:  # Skip folder markers
                    continue
                
                is_video = self.is_video_file(name)
                
                cloud_file = CloudFile(
                    id=key,
                    name=name,
                    path=f"/{key}",
                    size=obj["Size"],
                    modified_at=obj["LastModified"],
                    is_video=is_video,
                    is_folder=False,
                    provider=CloudProvider.S3,
                )
                files.append(cloud_file)
            
            return files
        
        except Exception as e:
            logger.error(f"Failed to list S3 files: {e}")
            return []
    
    async def get_stream_url(
        self,
        file_id: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Generate presigned URL for streaming."""
        if not self._s3_client:
            if not await self.authenticate():
                return None
        
        try:
            url = self._s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.s3_config.bucket_name,
                    "Key": file_id,
                },
                ExpiresIn=expires_in,
            )
            return url
        
        except Exception as e:
            logger.error(f"Failed to generate S3 presigned URL: {e}")
            return None
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test S3 connection."""
        try:
            if not await self.authenticate():
                return False, "Authentication failed"
            
            self._s3_client.head_bucket(Bucket=self.s3_config.bucket_name)
            return True, f"Connected to bucket: {self.s3_config.bucket_name}"
        
        except Exception as e:
            return False, str(e)


# ============================================================================
# Cloud Storage Manager
# ============================================================================

class CloudStorageManager:
    """
    Manages cloud storage providers.
    
    Features:
    - Multiple provider support
    - File discovery and scanning
    - Stream URL generation
    - Caching
    """
    
    def __init__(self):
        self._providers: Dict[str, CloudStorageProvider] = {}
        self._files_cache: Dict[str, List[CloudFile]] = {}
    
    def add_provider(
        self,
        name: str,
        provider: CloudStorageProvider,
    ) -> None:
        """Add a storage provider."""
        self._providers[name] = provider
        logger.info(f"Added cloud storage provider: {name}")
    
    def remove_provider(self, name: str) -> bool:
        """Remove a storage provider."""
        if name in self._providers:
            del self._providers[name]
            self._files_cache.pop(name, None)
            return True
        return False
    
    async def scan_provider(self, name: str) -> List[CloudFile]:
        """Scan a provider for files."""
        provider = self._providers.get(name)
        if not provider:
            return []
        
        async with provider:
            files = await provider.list_files()
        
        # Filter to video files only
        video_files = [f for f in files if f.is_video]
        self._files_cache[name] = video_files
        
        logger.info(f"Found {len(video_files)} video files in {name}")
        return video_files
    
    async def scan_all(self) -> Dict[str, List[CloudFile]]:
        """Scan all providers."""
        results = {}
        for name in self._providers:
            results[name] = await self.scan_provider(name)
        return results
    
    async def get_stream_url(
        self,
        provider_name: str,
        file_id: str,
    ) -> Optional[str]:
        """Get stream URL from a provider."""
        provider = self._providers.get(provider_name)
        if not provider:
            return None
        
        async with provider:
            return await provider.get_stream_url(file_id)
    
    async def test_provider(self, name: str) -> tuple[bool, str]:
        """Test a provider connection."""
        provider = self._providers.get(name)
        if not provider:
            return False, "Provider not found"
        
        async with provider:
            return await provider.test_connection()
    
    def get_files(
        self,
        provider_name: Optional[str] = None,
    ) -> List[CloudFile]:
        """Get cached files."""
        if provider_name:
            return self._files_cache.get(provider_name, [])
        
        all_files = []
        for files in self._files_cache.values():
            all_files.extend(files)
        return all_files
    
    def get_providers(self) -> List[str]:
        """Get list of configured providers."""
        return list(self._providers.keys())


# Global manager instance
cloud_storage_manager = CloudStorageManager()

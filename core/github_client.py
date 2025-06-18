"""
GitHub API client for fetching EKS AMI release information.
"""

import requests
import sys
from typing import List, Dict, Optional


class GitHubAPIError(Exception):
    """Exception raised for GitHub API errors."""
    pass


class GitHubReleaseClient:
    """Client for interacting with GitHub releases API."""
    
    def __init__(self, repo: str = "awslabs/amazon-eks-ami", verbose: bool = False):
        """
        Initialize GitHub release client.
        
        Args:
            repo: GitHub repository in format "owner/repo"
            verbose: Enable verbose logging
        """
        self.repo = repo
        self.api_url = f"https://api.github.com/repos/{repo}/releases"
        self.session = requests.Session()
        self.verbose = verbose
        self._setup_session()
    
    def _setup_session(self):
        """Configure the requests session with appropriate headers."""
        self.session.headers.update({
            'User-Agent': 'EKS-AMI-Parser/2.0',
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def log(self, message: str):
        """Print verbose logging messages."""
        if self.verbose:
            print(f"[GITHUB-DEBUG] {message}")
    
    def get_releases(self, limit: int = 50, include_drafts: bool = False, 
                    include_prereleases: bool = False) -> List[Dict]:
        """
        Fetch releases from the GitHub API.
        
        Args:
            limit: Maximum number of releases to fetch
            include_drafts: Whether to include draft releases
            include_prereleases: Whether to include prerelease versions
        
        Returns:
            List of release dictionaries from GitHub API
        
        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            params = {'per_page': limit}
            response = self.session.get(self.api_url, params=params)
            response.raise_for_status()
            releases = response.json()
            
            self.log(f"Fetched {len(releases)} releases from {self.repo}")
            
            # Filter releases based on parameters
            filtered_releases = []
            for release in releases:
                if not include_drafts and release.get('draft', False):
                    self.log(f"Skipping draft release: {release.get('tag_name', 'unknown')}")
                    continue
                
                if not include_prereleases and release.get('prerelease', False):
                    self.log(f"Skipping prerelease: {release.get('tag_name', 'unknown')}")
                    continue
                
                filtered_releases.append(release)
            
            self.log(f"Returning {len(filtered_releases)} filtered releases")
            return filtered_releases
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching releases from {self.repo}: {e}"
            self.log(error_msg)
            raise GitHubAPIError(error_msg)
    
    def get_release_by_tag(self, tag: str) -> Optional[Dict]:
        """
        Get a specific release by tag name.
        
        Args:
            tag: Release tag name (e.g., "v20241121")
        
        Returns:
            Release dictionary or None if not found
        
        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            url = f"{self.api_url.rstrip('/releases')}/releases/tags/{tag}"
            response = self.session.get(url)
            
            if response.status_code == 404:
                self.log(f"Release not found: {tag}")
                return None
            
            response.raise_for_status()
            release = response.json()
            self.log(f"Found release: {tag}")
            return release
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching release {tag} from {self.repo}: {e}"
            self.log(error_msg)
            raise GitHubAPIError(error_msg)
    
    def get_latest_release(self, include_prereleases: bool = False) -> Optional[Dict]:
        """
        Get the latest release.
        
        Args:
            include_prereleases: Whether to consider prereleases
        
        Returns:
            Latest release dictionary or None if no releases found
        
        Raises:
            GitHubAPIError: If API request fails
        """
        releases = self.get_releases(limit=10, include_prereleases=include_prereleases)
        if not releases:
            return None
        
        # Releases are typically sorted by date (newest first) by GitHub API
        return releases[0]
    
    def search_releases_by_content(self, search_term: str, limit: int = 50) -> List[Dict]:
        """
        Search releases by content in release body.
        
        Args:
            search_term: Term to search for in release bodies
            limit: Maximum number of releases to search through
        
        Returns:
            List of releases containing the search term
        
        Raises:
            GitHubAPIError: If API request fails
        """
        releases = self.get_releases(limit=limit)
        matching_releases = []
        
        for release in releases:
            body = release.get('body', '')
            if body and search_term.lower() in body.lower():
                self.log(f"Found search term '{search_term}' in release {release.get('tag_name', 'unknown')}")
                matching_releases.append(release)
        
        self.log(f"Found {len(matching_releases)} releases containing '{search_term}'")
        return matching_releases
    
    def get_release_info(self, release: Dict) -> Dict:
        """
        Extract key information from a release dictionary.
        
        Args:
            release: Release dictionary from GitHub API
        
        Returns:
            Dictionary with key release information
        """
        return {
            'tag_name': release.get('tag_name', ''),
            'name': release.get('name', ''),
            'published_at': release.get('published_at', ''),
            'created_at': release.get('created_at', ''),
            'body': release.get('body', ''),
            'draft': release.get('draft', False),
            'prerelease': release.get('prerelease', False),
            'html_url': release.get('html_url', ''),
            'assets_count': len(release.get('assets', [])),
        }
    
    def validate_release_structure(self, release: Dict) -> tuple[bool, List[str]]:
        """
        Validate that a release has the expected structure.
        
        Args:
            release: Release dictionary from GitHub API
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        if not release.get('tag_name'):
            issues.append("Missing tag_name")
        
        if not release.get('published_at'):
            issues.append("Missing published_at")
        
        body = release.get('body', '')
        if not body:
            issues.append("Missing or empty body")
        elif len(body.strip()) < 10:
            issues.append("Body is too short (likely incomplete)")
        
        return len(issues) == 0, issues
    
    def get_rate_limit_info(self) -> Dict:
        """
        Get current GitHub API rate limit information.
        
        Returns:
            Dictionary with rate limit information
        
        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            response = self.session.get("https://api.github.com/rate_limit")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching rate limit info: {e}"
            self.log(error_msg)
            raise GitHubAPIError(error_msg)
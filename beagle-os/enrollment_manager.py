"""Beagle Endpoint Enrollment Manager.

Handles enrollment token generation, validation, and short-code assignment
for endpoints during first-boot pairing flow.
"""

import hashlib
import random
import string
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import json


@dataclass
class EnrollmentToken:
    """Represents a single enrollment token for endpoint pairing."""
    
    token_id: str  # Unique token identifier
    short_code: str  # User-friendly 4-char alphanumeric code (e.g. "ABCD-1234")
    enrollment_url: str  # Full enrollment URL for QR code
    created_at: str  # ISO 8601 timestamp
    expires_at: str  # ISO 8601 timestamp (24 hours from creation)
    endpoint_hostname: Optional[str] = None  # Hostname endpoint reports after pairing
    paired_at: Optional[str] = None  # When endpoint successfully paired
    cluster_endpoint: str = "https://beagle-server"  # Cluster endpoint URL for QR
    
    
    def is_expired(self) -> bool:
        """Check if token has expired."""
        expires = datetime.fromisoformat(self.expires_at)
        now = datetime.now(timezone.utc)
        return expires < now
    def is_paired(self) -> bool:
        """Check if endpoint has completed pairing."""
        return self.paired_at is not None
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class EnrollmentManager:
    """Manages endpoint enrollment tokens and pairing flow."""
    
    def __init__(self, tokens_dir: str = "enrollment_tokens"):
        """Initialize enrollment manager with persistent token storage."""
        self.tokens_dir = Path(tokens_dir)
        self.tokens_dir.mkdir(exist_ok=True)
        self.tokens: dict[str, EnrollmentToken] = {}
        self._load_tokens()
    
    def _load_tokens(self):
        """Load all tokens from persistent storage."""
        for token_file in self.tokens_dir.glob("*.json"):
            try:
                with open(token_file) as f:
                    data = json.load(f)
                    token = EnrollmentToken(**data)
                    self.tokens[token.token_id] = token
            except Exception as e:
                print(f"Warning: Failed to load token {token_file}: {e}")
    
    def _save_token(self, token: EnrollmentToken):
        """Save token to persistent storage."""
        token_file = self.tokens_dir / f"{token.token_id}.json"
        with open(token_file, 'w') as f:
            json.dump(token.to_dict(), f, indent=2)
    
    def _generate_short_code(self) -> str:
        """Generate a human-friendly 4+4 digit short code like ABCD-1234."""
        # 4 random uppercase letters
        letters = ''.join(random.choices(string.ascii_uppercase, k=4))
        # 4 random digits
        digits = ''.join(random.choices(string.digits, k=4))
        return f"{letters}-{digits}"
    
    def _generate_token_id(self) -> str:
        """Generate unique token identifier (hex-encoded random bytes)."""
        return hashlib.sha256(
            f"{time.time()}{random.random()}".encode()
        ).hexdigest()[:16]
    
    def create_token(
        self,
        cluster_endpoint: str = "https://beagle-server"
    ) -> EnrollmentToken:
        """Create new enrollment token for endpoint pairing.
        
        Returns:
            EnrollmentToken with 24-hour validity window.
        """
        token_id = self._generate_token_id()
        short_code = self._generate_short_code()
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=24)
        
        # Enrollment URL that endpoint can scan via QR code
        # Format: https://cluster/enroll?token=SHORTCODE
        enrollment_url = f"{cluster_endpoint}/ui/enroll?code={short_code}"
        
        token = EnrollmentToken(
            token_id=token_id,
            short_code=short_code,
            enrollment_url=enrollment_url,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            cluster_endpoint=cluster_endpoint
        )
        
        self.tokens[token_id] = token
        self._save_token(token)
        
        return token
    
    def get_token_by_short_code(self, short_code: str) -> Optional[EnrollmentToken]:
        """Retrieve token by short code (used during Web Console enrollment)."""
        for token in self.tokens.values():
            if token.short_code == short_code and not token.is_expired():
                return token
        return None
    
    def get_token_by_id(self, token_id: str) -> Optional[EnrollmentToken]:
        """Retrieve token by token ID."""
        return self.tokens.get(token_id)
    
    def mark_paired(self, short_code: str, endpoint_hostname: str) -> bool:
        """Mark token as paired when endpoint reports during enrollment.
        
        Args:
            short_code: Short code from enrollment token
            endpoint_hostname: Hostname reported by endpoint
        
        Returns:
            True if successful, False if token not found or expired
        """
        token = self.get_token_by_short_code(short_code)
        if not token:
            return False
        
        token.endpoint_hostname = endpoint_hostname
        token.paired_at = datetime.now(timezone.utc).isoformat()
        self._save_token(token)
        return True
    
    def list_active_tokens(self) -> list[EnrollmentToken]:
        """List all non-expired tokens."""
        return [
            token for token in self.tokens.values()
            if not token.is_expired()
        ]
    
    def list_paired_tokens(self) -> list[EnrollmentToken]:
        """List all tokens with completed pairings."""
        return [
            token for token in self.tokens.values()
            if token.is_paired()
        ]
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens from memory and storage."""
        expired = [
            token_id for token_id, token in self.tokens.items()
            if token.is_expired()
        ]
        
        for token_id in expired:
            token = self.tokens.pop(token_id)
            token_file = self.tokens_dir / f"{token_id}.json"
            if token_file.exists():
                token_file.unlink()
    
    def tokens_as_json(self) -> str:
        """Export all tokens as JSON."""
        return json.dumps(
            [token.to_dict() for token in self.tokens.values()],
            indent=2
        )


if __name__ == "__main__":
    # Simple demo
    import sys
    sys.path.insert(0, ".")
    
    manager = EnrollmentManager()
    
    # Create a new enrollment token
    token = manager.create_token()
    print(f"\n=== New Enrollment Token ===")
    print(f"Short Code: {token.short_code}")
    print(f"Token ID: {token.token_id}")
    print(f"Enrollment URL: {token.enrollment_url}")
    print(f"Valid until: {token.expires_at}")
    
    # List active tokens
    active = manager.list_active_tokens()
    print(f"\n=== Active Tokens ({len(active)}) ===")
    for t in active:
        status = "✓ Paired" if t.is_paired() else "⏳ Waiting"
        print(f"  {t.short_code}: {status}")

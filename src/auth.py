"""
Authentication and Authorization Module.

Supports:
- JWT token generation and verification
- Firebase Auth integration
- Role-based access control (RBAC)
- Permission management

Roles:
- recruiter: Can search candidates and upload resumes
- admin: Full access including analytics and user management
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import jwt
import os
from functools import wraps

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


# Role-based permissions
ROLE_PERMISSIONS = {
    "recruiter": [
        "search:candidates",
        "upload:resume",
        "view:candidates",
        "view:candidate_details"
    ],
    "admin": [
        "search:candidates",
        "upload:resume",
        "view:candidates",
        "view:candidate_details",
        "view:analytics",
        "delete:candidate",
        "manage:users",
        "rebuild:index"
    ]
}


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""
    pass


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Payload data (should include user_id, email, role)
        expires_delta: Token expiration time
    
    Returns:
        Encoded JWT token
    
    Example:
        >>> token = create_access_token({
        ...     "user_id": "user_123",
        ...     "email": "john@company.com",
        ...     "role": "recruiter"
        ... })
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload
    
    Raises:
        AuthenticationError: If token is invalid or expired
    
    Example:
        >>> payload = verify_token(token)
        >>> print(payload["email"])
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check token type
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        
        # Check expiration (jwt library does this automatically)
        return payload
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def get_user_permissions(role: str) -> List[str]:
    """
    Get permissions for a given role.
    
    Args:
        role: User role (recruiter, admin)
    
    Returns:
        List of permission strings
    
    Example:
        >>> permissions = get_user_permissions("recruiter")
        >>> "search:candidates" in permissions
        True
    """
    return ROLE_PERMISSIONS.get(role, [])


def has_permission(user_role: str, required_permission: str) -> bool:
    """
    Check if a role has a specific permission.
    
    Args:
        user_role: User's role
        required_permission: Permission to check
    
    Returns:
        True if role has permission
    
    Example:
        >>> has_permission("recruiter", "search:candidates")
        True
        >>> has_permission("recruiter", "delete:candidate")
        False
    """
    permissions = get_user_permissions(user_role)
    return required_permission in permissions


def require_permission(permission: str):
    """
    Decorator to require a specific permission.
    
    Example:
        @require_permission("view:analytics")
        def view_analytics(user):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get user from kwargs (assuming it's passed)
            user = kwargs.get('user')
            if not user:
                raise AuthorizationError("No user context")
            
            user_role = user.get('role')
            if not has_permission(user_role, permission):
                raise AuthorizationError(
                    f"Permission denied: {permission} required"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ==================== Firebase Auth Integration ====================

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    
    FIREBASE_ENABLED = True
except ImportError:
    FIREBASE_ENABLED = False


def verify_firebase_token(id_token: str) -> Dict:
    """
    Verify Firebase ID token.
    
    Args:
        id_token: Firebase ID token from client
    
    Returns:
        Decoded token with user info
    
    Raises:
        AuthenticationError: If token is invalid
    
    Note:
        Requires firebase_admin to be installed and initialized
    """
    if not FIREBASE_ENABLED:
        raise AuthenticationError("Firebase authentication not available")
    
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        
        # Extract user info
        user_data = {
            "user_id": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "email_verified": decoded_token.get("email_verified", False),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
        }
        
        # Get role from custom claims
        # You need to set custom claims via Firebase Admin SDK
        custom_claims = decoded_token.get("claims", {})
        user_data["role"] = custom_claims.get("role", "recruiter")
        
        return user_data
        
    except Exception as e:
        raise AuthenticationError(f"Firebase token verification failed: {str(e)}")


def create_firebase_user(email: str, password: str, role: str = "recruiter") -> Dict:
    """
    Create a new Firebase user with custom role claim.
    
    Args:
        email: User email
        password: User password
        role: User role (default: recruiter)
    
    Returns:
        User data
    
    Note:
        Admin-only function
    """
    if not FIREBASE_ENABLED:
        raise AuthenticationError("Firebase authentication not available")
    
    try:
        # Create user
        user = firebase_auth.create_user(
            email=email,
            password=password,
            email_verified=False
        )
        
        # Set custom claims (role)
        firebase_auth.set_custom_user_claims(user.uid, {"role": role})
        
        return {
            "user_id": user.uid,
            "email": user.email,
            "role": role
        }
        
    except Exception as e:
        raise AuthenticationError(f"User creation failed: {str(e)}")


# ==================== Mock Authentication (Development) ====================

# Mock users for development/testing
MOCK_USERS = {
    "recruiter@company.com": {
        "user_id": "user_001",
        "email": "recruiter@company.com",
        "password": "recruiter123",  # Never do this in production!
        "role": "recruiter",
        "name": "Jane Recruiter"
    },
    "admin@company.com": {
        "user_id": "admin_001",
        "email": "admin@company.com",
        "password": "admin123",
        "role": "admin",
        "name": "Admin User"
    }
}


def authenticate_mock_user(email: str, password: str) -> Dict:
    """
    Mock authentication for development.
    
    Args:
        email: User email
        password: User password
    
    Returns:
        User data with token
    
    Raises:
        AuthenticationError: If credentials invalid
    
    Example:
        >>> user = authenticate_mock_user("recruiter@company.com", "recruiter123")
        >>> print(user["token"])
    """
    user = MOCK_USERS.get(email)
    
    if not user or user["password"] != password:
        raise AuthenticationError("Invalid email or password")
    
    # Create token
    token_data = {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"]
    }
    token = create_access_token(token_data)
    
    # Return user data with token
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
        "token": token,
        "token_type": "Bearer"
    }


# ==================== Utility Functions ====================

def get_current_user_from_token(token: str) -> Dict:
    """
    Extract user info from token.
    
    Args:
        token: JWT or Firebase token
    
    Returns:
        User data
    """
    try:
        # Try JWT first
        payload = verify_token(token)
        return payload
    except AuthenticationError:
        # Try Firebase if available
        if FIREBASE_ENABLED:
            return verify_firebase_token(token)
        raise


def check_user_permissions(user: Dict, required_permissions: List[str]) -> bool:
    """
    Check if user has all required permissions.
    
    Args:
        user: User data with role
        required_permissions: List of required permissions
    
    Returns:
        True if user has all permissions
    """
    user_role = user.get('role')
    user_permissions = get_user_permissions(user_role)
    
    return all(perm in user_permissions for perm in required_permissions)


# ==================== Testing ====================

if __name__ == "__main__":
    print("=" * 60)
    print("Authentication Module Test")
    print("=" * 60)
    
    # Test JWT token creation
    print("\n1. Creating JWT token...")
    token = create_access_token({
        "user_id": "test_123",
        "email": "test@example.com",
        "role": "recruiter"
    })
    print(f"Token: {token[:50]}...")
    
    # Test token verification
    print("\n2. Verifying token...")
    payload = verify_token(token)
    print(f"Payload: {payload}")
    
    # Test permissions
    print("\n3. Testing permissions...")
    print(f"Recruiter can search: {has_permission('recruiter', 'search:candidates')}")
    print(f"Recruiter can delete: {has_permission('recruiter', 'delete:candidate')}")
    print(f"Admin can delete: {has_permission('admin', 'delete:candidate')}")
    
    # Test mock authentication
    print("\n4. Testing mock authentication...")
    user = authenticate_mock_user("recruiter@company.com", "recruiter123")
    print(f"User authenticated: {user['email']} ({user['role']})")
    print(f"Token: {user['token'][:50]}...")
    
    print("\n✅ All tests passed!")

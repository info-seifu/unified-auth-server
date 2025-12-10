"""Test setup script for initial configuration"""

import secrets
import sys
from pathlib import Path

def generate_jwt_secret():
    """Generate a secure JWT secret key"""
    return secrets.token_urlsafe(32)

def create_test_env():
    """Create a test .env file for development"""
    env_content = f"""# Environment
ENVIRONMENT=development

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Google OAuth Configuration (TEST CREDENTIALS - REPLACE WITH REAL ONES)
GOOGLE_CLIENT_ID=test-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-test-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/callback/{{project_id}}

# JWT Configuration
JWT_SECRET_KEY={generate_jwt_secret()}
JWT_ALGORITHM=HS256
JWT_EXPIRY_DAYS=30

# Google Cloud Configuration
GCP_PROJECT_ID=test-project
USE_FIREBASE_EMULATOR=false
FIREBASE_EMULATOR_HOST=localhost:8080

# Secret Manager Configuration (production)
SECRET_MANAGER_ENABLED=false
OAUTH_CREDENTIALS_SECRET_NAME=google-oauth-credentials
JWT_KEY_SECRET_NAME=jwt-secret-key

# API Proxy Server Configuration
API_PROXY_SERVER_URL=https://api-key-server.run.app

# Allowed Domains (comma-separated)
ALLOWED_DOMAINS=i-seifu.jp,i-seifu.ac.jp,gmail.com

# CORS Settings
CORS_ORIGINS=http://localhost:3000,http://localhost:8501,http://localhost:8000
CORS_ALLOW_CREDENTIALS=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Development Mode
USE_LOCAL_CONFIG=true
"""

    env_file = Path(".env")
    if env_file.exists():
        print("⚠️  .env file already exists!")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return False

    env_file.write_text(env_content)
    print("✅ Created test .env file")
    print("\n⚠️  IMPORTANT: The .env file contains test credentials!")
    print("You need to replace them with real Google OAuth credentials.")
    print("\nTo get real credentials:")
    print("1. Go to https://console.cloud.google.com/apis/credentials")
    print("2. Create an OAuth 2.0 Client ID")
    print("3. Add authorized redirect URIs:")
    print("   - http://localhost:8000/callback/test-project")
    print("   - http://localhost:8000/callback/slide-video")
    print("4. Update GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env")

    return True

def test_imports():
    """Test that all required modules can be imported"""
    print("\n🔍 Testing imports...")

    try:
        import fastapi
        print("✅ FastAPI")
    except ImportError:
        print("❌ FastAPI not installed")
        return False

    try:
        import uvicorn
        print("✅ Uvicorn")
    except ImportError:
        print("❌ Uvicorn not installed")
        return False

    try:
        import jwt
        print("✅ PyJWT")
    except ImportError:
        print("❌ PyJWT not installed")
        return False

    try:
        import authlib
        print("✅ Authlib")
    except ImportError:
        print("❌ Authlib not installed")
        return False

    try:
        import google.cloud.firestore
        print("✅ Google Cloud Firestore")
    except ImportError:
        print("⚠️  Google Cloud Firestore not installed (optional)")

    try:
        from dotenv import load_dotenv
        print("✅ Python-dotenv")
    except ImportError:
        print("❌ Python-dotenv not installed")
        return False

    return True

def main():
    """Main setup function"""
    print("\n" + "="*60)
    print("🔧 Unified Auth Server - Test Setup")
    print("="*60)

    # Test imports
    if not test_imports():
        print("\n❌ Some required packages are missing!")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)

    # Create test .env file
    print("\n📝 Setting up environment file...")
    if not create_test_env():
        sys.exit(1)

    # Test that the app can be imported
    print("\n🔍 Testing app import...")
    try:
        from app.main import app
        print("✅ App imported successfully")
    except Exception as e:
        print(f"❌ Failed to import app: {e}")
        sys.exit(1)

    print("\n" + "="*60)
    print("✅ Setup complete!")
    print("="*60)
    print("\n📋 Next steps:")
    print("1. Update .env with real Google OAuth credentials")
    print("2. Run the development server: python run_dev.py")
    print("3. Visit http://localhost:8000/docs for API documentation")
    print("4. Test login at http://localhost:8000/login/test-project")
    print("\n💡 Tip: The test-project allows Gmail addresses for testing")

if __name__ == "__main__":
    main()
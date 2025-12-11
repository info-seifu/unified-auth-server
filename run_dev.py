"""Development server runner"""

import uvicorn
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Set default environment variables for development
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("USE_LOCAL_CONFIG", "true")
os.environ.setdefault("LOG_LEVEL", "INFO")

# Check if .env file exists
env_file = Path(__file__).parent / ".env"
if not env_file.exists():
    print("\n⚠️  Warning: .env file not found!")
    print("Creating .env from .env.example...")

    example_file = Path(__file__).parent / ".env.example"
    if example_file.exists():
        import shutil
        shutil.copy(example_file, env_file)
        print("✅ Created .env file. Please update it with your credentials.\n")
        print("Required settings:")
        print("  - GOOGLE_CLIENT_ID: Your Google OAuth client ID")
        print("  - GOOGLE_CLIENT_SECRET: Your Google OAuth client secret")
        print("  - JWT_SECRET_KEY: A random secret key for JWT signing")
        print("\nYou can get Google OAuth credentials from:")
        print("https://console.cloud.google.com/apis/credentials\n")
        sys.exit(1)
    else:
        print("❌ .env.example not found!")
        sys.exit(1)

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(override=True)  # Override existing environment variables

# Check required environment variables
required_vars = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "JWT_SECRET_KEY"]
missing_vars = []

for var in required_vars:
    if not os.environ.get(var) or os.environ.get(var).startswith("your-"):
        missing_vars.append(var)

if missing_vars:
    print("\n❌ Missing required environment variables:")
    for var in missing_vars:
        print(f"  - {var}")
    print("\nPlease update your .env file with valid credentials.")
    print("\nYou can get Google OAuth credentials from:")
    print("https://console.cloud.google.com/apis/credentials")
    print("\nFor JWT_SECRET_KEY, generate a random string:")
    print("  python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    sys.exit(1)

def main():
    """Run the development server"""
    print("\n" + "="*60)
    print("🚀 Starting Unified Auth Server (Development Mode)")
    print("="*60)
    print(f"\n📁 Working Directory: {Path.cwd()}")
    print(f"🔧 Environment: {os.environ.get('ENVIRONMENT', 'development')}")
    print(f"🔑 Google Client ID: {os.environ.get('GOOGLE_CLIENT_ID', 'NOT SET')[:30]}...")
    print(f"🌐 Server URL: http://localhost:8000")
    print("\n" + "="*60)
    print("\n📚 Available Endpoints:")
    print("  - Homepage: http://localhost:8000/")
    print("  - API Docs: http://localhost:8000/docs")
    print("  - Login: http://localhost:8000/login/{project_id}")
    print("  - Health: http://localhost:8000/health")

    if os.environ.get("USE_LOCAL_CONFIG") == "true":
        print("\n📋 Available Test Projects:")
        print("  - test-project (for testing)")
        print("  - slide-video (for Slide Video app)")
        print("\n🔗 Example Login URL:")
        print("  http://localhost:8000/login/test-project")

    print("\n" + "="*60)
    print("\n✋ Press CTRL+C to stop the server\n")

    # Run the server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        reload_dirs=["app"],
        reload_includes=["*.py", "*.yaml", "*.yml", "*.json"],
        reload_excludes=["*.pyc", "__pycache__", ".git", ".env"]
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
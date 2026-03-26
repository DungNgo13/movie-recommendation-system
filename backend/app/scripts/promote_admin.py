import argparse
import sys
import os

# Đảm bảo python hiểu được thư mục gốc backend (chứa module 'app') dù đứng ở bất kỳ CWD nào
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.models.user import User

def promote_user(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Error: User with email '{email}' not found.")
            sys.exit(1)
        
        user.role = "admin"
        db.commit()
        print(f"Success: User '{email}' has been promoted to 'admin' role.")
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote a user to admin role.")
    parser.add_argument("--email", required=True, help="Email address of the user to promote.")
    args = parser.parse_args()
    
    promote_user(args.email)

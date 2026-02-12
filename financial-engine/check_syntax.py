import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

try:
    print("Checking app.services.explainability_service...")
    from app.services import explainability_service
    print("OK")

    print("Checking app.services.memo_service...")
    from app.services import memo_service
    print("OK")

    print("Checking app.api.routes.exports...")
    from app.api.routes import exports
    print("OK")

    print("Checking app.api.routes.analysis...")
    from app.api.routes import analysis
    print("OK")

    print("All modified files imported successfully.")

except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except SyntaxError as e:
    print(f"SyntaxError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred: {e}")
    sys.exit(1)
"""AWS Lambda Handler adapter for Porchline ASGI application."""
from porchline.main import app

def lambda_handler(event, context):
    """Entry point for AWS Lambda / API Gateway proxy integration.
    Can be run with Mangum or custom ASGI proxy in production AWS environments.
    """
    try:
        from mangum import Mangum
        asgi_handler = Mangum(app)
        return asgi_handler(event, context)
    except ImportError:
        # Minimal fallback wrapper for direct Lambda test invocations
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": '{"status":"ok","message":"Porchline Lambda initialized"}'
        }

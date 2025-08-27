#!/bin/bash

# fly.io Deployment Script for TickTick MCP Server

set -e

APP_NAME="ticktick-mcp"
REGION="sjc"  # San Jose, California

echo "🚀 Deploying TickTick MCP Server to fly.io"

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl is not installed. Please install it first:"
    echo "   macOS: brew install flyctl"
    echo "   Linux: curl -L https://fly.io/install.sh | sh"
    echo "   Windows: iwr https://fly.io/install.ps1 -useb | iex"
    exit 1
fi

# Check if user is logged in
if ! flyctl auth whoami &> /dev/null; then
    echo "🔐 Please log in to fly.io"
    flyctl auth login
fi

# Check if app exists, if not create it
if ! flyctl apps show $APP_NAME &> /dev/null; then
    echo "📱 Creating new fly.io app: $APP_NAME"
    flyctl apps create $APP_NAME --org personal
fi

# Set secrets from .env file if it exists
if [ -f ".env" ]; then
    echo "🔑 Setting secrets from .env file"
    
    # Read .env file and set secrets
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        if [[ $key && $key != \#* ]]; then
            # Remove quotes from value if present
            value=$(echo "$value" | sed 's/^["'\'']*//;s/["'\'']*$//')
            echo "Setting secret: $key"
            flyctl secrets set "$key=$value" --app $APP_NAME
        fi
    done < .env
else
    echo "⚠️  No .env file found. You'll need to set secrets manually:"
    echo "   flyctl secrets set TICKTICK_CLIENT_ID=your_client_id --app $APP_NAME"
    echo "   flyctl secrets set TICKTICK_CLIENT_SECRET=your_client_secret --app $APP_NAME"
    echo "   See fly.env.template for all required secrets"
fi

# Set fly.io specific secrets
echo "🌐 Setting fly.io specific configuration"
flyctl secrets set FLY_APP_NAME=$APP_NAME --app $APP_NAME
flyctl secrets set FASTMCP_SERVER_AUTH_OAUTH_PROXY_BASE_URL=https://$APP_NAME.fly.dev --app $APP_NAME

echo "🚀 Deploying application"
flyctl deploy --app $APP_NAME

echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update your TickTick OAuth app callback URL to: https://$APP_NAME.fly.dev/auth/callback"
echo "2. Test your deployment: https://$APP_NAME.fly.dev/.well-known/oauth-authorization-server"
echo "3. Test with mcp-remote: npx -p mcp-remote@latest mcp-remote-client https://$APP_NAME.fly.dev/sse --transport sse-only"
echo ""
echo "🔧 Useful commands:"
echo "  flyctl logs --app $APP_NAME           # View logs"
echo "  flyctl ssh console --app $APP_NAME    # SSH into container"
echo "  flyctl status --app $APP_NAME         # Check app status"

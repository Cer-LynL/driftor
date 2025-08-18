#!/bin/bash

echo "🔧 Setting up Driftor Local Environment"
echo "======================================"

# Check if .env already exists
if [ -f .env ]; then
    echo "⚠️  .env file already exists. Backing up to .env.backup"
    cp .env .env.backup
fi

# Copy template
echo "📝 Creating .env from template..."
cp .env.example .env

echo "🔑 Generating secure credentials..."

# Generate secure passwords and keys
DB_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
ENCRYPTION_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
JWT_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
REDIS_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(16))')

# Update .env file with generated credentials
sed -i.bak "s/your-secret-key-here-minimum-32-characters/$SECRET_KEY/g" .env
sed -i.bak "s/your-encryption-key-here-32-bytes-base64/$ENCRYPTION_KEY/g" .env  
sed -i.bak "s/your-jwt-secret-key-here-minimum-32-chars/$JWT_SECRET_KEY/g" .env
sed -i.bak "s/secure_password/$DB_PASSWORD/g" .env
sed -i.bak "s/secure_redis_password/$REDIS_PASSWORD/g" .env

# Update database URL with generated password
sed -i.bak "s|postgresql+asyncpg://driftor:secure_password@localhost:5432/driftor|postgresql+asyncpg://driftor:$DB_PASSWORD@localhost:5432/driftor_db|g" .env

# Clean up backup file
rm .env.bak

echo "✅ Environment configured successfully!"
echo ""
echo "📋 Generated Credentials:"
echo "   Database Password: $DB_PASSWORD"
echo "   Secret Key: ${SECRET_KEY:0:10}..."
echo "   Encryption Key: ${ENCRYPTION_KEY:0:10}..."  
echo "   JWT Secret: ${JWT_SECRET_KEY:0:10}..."
echo ""
echo "🔐 All credentials saved to .env file"
echo ""
echo "🚀 Next steps:"
echo "   1. Run: ./start_driftor.sh"
echo "   2. Wait for services to start"
echo "   3. Run: python scripts/test_api.py"
echo ""
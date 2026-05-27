#!/usr/bin/env bash

echo "-----> Running post_compile hook"
echo "-----> Building the React frontend in the client/ directory..."

cd client
npm install
npm run build
cd ..

echo "-----> Frontend build complete!"
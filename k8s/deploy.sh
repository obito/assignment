#!/bin/bash

# Voice Agent Kubernetes Deployment Script
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_status() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment parameter
ENVIRONMENT="${1:-local}"
if [[ ! "$ENVIRONMENT" =~ ^[a-z0-9-]+$ ]]; then
    print_error "Invalid environment name. Use only lowercase letters, numbers, and hyphens."
    exit 1
fi

NAMESPACE="voice-agent-${ENVIRONMENT}"

print_status "Deploying Voice Agent to environment: $ENVIRONMENT"
print_status "Namespace: $NAMESPACE"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Check if kustomize is available
if ! command -v kustomize &> /dev/null; then
    print_error "kustomize is not installed or not in PATH"
    exit 1
fi

# Validate overlay exists
OVERLAY_PATH="overlays/${ENVIRONMENT}"
if [[ ! -d "$OVERLAY_PATH" ]]; then
    print_error "Overlay directory $OVERLAY_PATH does not exist"
    exit 1
fi

print_status "Building Kustomize configuration..."
kustomize build "$OVERLAY_PATH" > /tmp/voice-agent-manifests.yaml

print_status "Applying manifests to namespace: $NAMESPACE"
kubectl apply -f /tmp/voice-agent-manifests.yaml

print_status "Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment --all -n "$NAMESPACE"

print_success "Voice Agent deployed successfully!"
print_status "To check status: kubectl get all -n $NAMESPACE"
print_status "To view logs: kubectl logs -f deployment/voice-agent -n $NAMESPACE"

# Clean up temporary file
rm -f /tmp/voice-agent-manifests.yaml

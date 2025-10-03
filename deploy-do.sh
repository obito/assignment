#!/bin/bash

# DigitalOcean Voice Agent Deployment Script
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="voice-agent-cluster"
REGION="nyc1"
NODE_SIZE="s-4vcpu-8gb"
NODE_COUNT=3
NAMESPACE="voice-agent-do"

# Functions
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command -v doctl &> /dev/null; then
        print_error "doctl is not installed. Please install it first:"
        echo "  curl -sL https://github.com/digitalocean/doctl/releases/download/v1.94.0/doctl-1.94.0-linux-amd64.tar.gz | tar -xzv"
        echo "  sudo mv doctl /usr/local/bin/"
        exit 1
    fi
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v kustomize &> /dev/null; then
        print_error "kustomize is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v helm &> /dev/null; then
        print_error "helm is not installed. Please install it first:"
        echo "  curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
        exit 1
    fi
    
    # Check if doctl is authenticated
    if ! doctl account get &> /dev/null; then
        print_error "doctl is not authenticated. Please run: doctl auth init"
        exit 1
    fi
    
    print_success "All prerequisites met!"
}

# Create DOKS cluster
create_cluster() {
    print_status "Creating DigitalOcean Kubernetes cluster: $CLUSTER_NAME"
    
    # Check if cluster already exists
    if doctl kubernetes cluster get "$CLUSTER_NAME" &> /dev/null; then
        print_warning "Cluster $CLUSTER_NAME already exists. Skipping creation."
        return 0
    fi
    
    doctl kubernetes cluster create "$CLUSTER_NAME" \
        --region "$REGION" \
        --node-pool "name=worker-pool;size=$NODE_SIZE;count=$NODE_COUNT;auto-scale=true;min-nodes=2;max-nodes=10" \
        --wait
    
    print_success "Cluster created successfully!"
}

# Configure kubectl
configure_kubectl() {
    print_status "Configuring kubectl for DOKS cluster..."
    
    doctl kubernetes cluster kubeconfig save "$CLUSTER_NAME"
    
    # Verify connection
    if kubectl cluster-info &> /dev/null; then
        print_success "kubectl configured successfully!"
    else
        print_error "Failed to configure kubectl"
        exit 1
    fi
}

# Install Nginx Ingress Controller
install_ingress_controller() {
    print_status "Installing Nginx Ingress Controller..."
    
    # Add Helm repository
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo update
    
    # Install Nginx Ingress Controller
    helm install nginx-ingress ingress-nginx/ingress-nginx \
        --set controller.publishService.enabled=true \
        --set controller.service.type=LoadBalancer \
        --wait
    
    print_success "Nginx Ingress Controller installed successfully!"
}

# Install Cert Manager
install_cert_manager() {
    print_status "Installing Cert Manager..."
    
    # Create namespace
    kubectl create namespace cert-manager --dry-run=client -o yaml | kubectl apply -f -
    
    # Add Helm repository
    helm repo add jetstack https://charts.jetstack.io
    helm repo update
    
    # Install Cert Manager
    helm install cert-manager jetstack/cert-manager \
        --namespace cert-manager \
        --version v1.8.0 \
        --set installCRDs=true \
        --wait
    
    print_success "Cert Manager installed successfully!"
}

# Create ClusterIssuer
create_cluster_issuer() {
    print_status "Creating Let's Encrypt ClusterIssuer..."
    
    # Prompt for email if not set
    if [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
        read -p "Enter your email address for Let's Encrypt: " LETSENCRYPT_EMAIL
    fi
    
    # Create ClusterIssuer
    cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    email: $LETSENCRYPT_EMAIL
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-prod-private-key
    solvers:
      - http01:
          ingress:
            class: nginx
EOF
    
    print_success "ClusterIssuer created successfully!"
}

# Create TURN certificate
create_turn_certificate() {
    print_status "Creating TURN server certificate..."
    
    # Create Certificate for TURN server
    cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: livekit-turn-tls
  namespace: $NAMESPACE
spec:
  secretName: livekit-turn-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - livekit.bnkd.me
EOF
    
    print_success "TURN certificate created successfully!"
}

# Deploy LiveKit Server
deploy_livekit() {
    print_status "Deploying LiveKit Server with official Helm chart..."
    
    # Add LiveKit Helm repository
    helm repo add livekit https://helm.livekit.io
    helm repo update
    
    # Create namespace if it doesn't exist
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    # Install LiveKit Server
    helm install livekit-server livekit/livekit-server \
        --namespace "$NAMESPACE" \
        --values livekit-values-do.yaml \
        --wait
    
    print_success "LiveKit Server deployed successfully!"
}

# Deploy voice agent application
deploy_voice_agent() {
    print_status "Deploying voice agent application..."
    
    # Apply secrets first (from base configuration)
    kubectl apply -f k8s/base/secrets.yaml -n "$NAMESPACE"
    
    # Apply voice agent only manifests
    kubectl apply -f k8s/overlays/digitalocean/voice-agent-only.yaml
    
    print_success "Voice agent application deployed successfully!"
}

# Wait for deployments
wait_for_deployments() {
    print_status "Waiting for deployments to be ready..."
    
    kubectl wait --for=condition=available --timeout=300s deployment --all -n "$NAMESPACE"
    
    print_success "All deployments are ready!"
}

# Get service endpoints
get_endpoints() {
    print_status "Getting service endpoints..."
    
    echo ""
    echo "🌐 Service Endpoints:"
    echo "===================="
    
    # LiveKit Server
    LIVEKIT_IP=$(kubectl get svc livekit-server -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    echo "LiveKit Server: http://$LIVEKIT_IP"
    
    # Prometheus
    PROMETHEUS_IP=$(kubectl get svc prometheus-service -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    echo "Prometheus: http://$PROMETHEUS_IP:9090"
    
    # Grafana
    GRAFANA_IP=$(kubectl get svc grafana-service -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    echo "Grafana: http://$GRAFANA_IP:3000"
    
    echo ""
    echo "📊 Monitoring Commands:"
    echo "======================"
    echo "kubectl get pods -n $NAMESPACE"
    echo "kubectl get svc -n $NAMESPACE"
    echo "kubectl logs -f deployment/voice-agent -n $NAMESPACE"
}

# Main deployment flow
main() {
    echo "🚀 DigitalOcean Voice Agent Deployment with Official LiveKit Helm Chart"
    echo "====================================================================="
    echo ""
    
    check_prerequisites
    create_cluster
    configure_kubectl
    install_ingress_controller
    install_cert_manager
    create_cluster_issuer
    create_turn_certificate
    deploy_livekit
    deploy_voice_agent
    wait_for_deployments
    get_endpoints
    
    echo ""
    print_success "🎉 Deployment completed successfully!"
    echo ""
    echo "💰 Estimated Monthly Cost: ~$195"
    echo "   - 3x s-4vcpu-8gb nodes: $144"
    echo "   - Load Balancers: $36"
    echo "   - Managed Redis: $15"
    echo ""
    echo "🔧 Next Steps:"
    echo "   1. Update your secrets in k8s/base/secrets.yaml"
    echo "   2. Configure your Twilio SIP trunk with livekit.bnkd.me"
    echo "   3. Test the voice agent with a phone call"
    echo "   4. SSL certificates will be automatically provisioned"
    echo ""
    echo "📚 Documentation: https://docs.livekit.io/home/self-hosting/kubernetes/"
}

# Run main function
main "$@"

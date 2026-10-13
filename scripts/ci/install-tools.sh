#!/usr/bin/env bash
# Install pinned CI tools into $HOME/.local/bin, verifying each download against the release's
# published checksums (COMPATIBILITY.md risk 3: never install Trivy or other scanners by mutable tag).
# Usage: install-tools.sh tflint conftest trivy gitleaks kubelogin
set -euo pipefail

BIN="${HOME}/.local/bin"
mkdir -p "${BIN}"
echo "${BIN}" >> "${GITHUB_PATH:-/dev/null}"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

TFLINT_VERSION="0.64.0"
CONFTEST_VERSION="0.71.1"
TRIVY_VERSION="0.75.0"
GITLEAKS_VERSION="8.30.1"
KUBELOGIN_VERSION="0.2.21"
KIND_VERSION="0.33.0"

fetch_verified() { # url checksums_url filename
  local url="$1" sums_url="$2" file="$3"
  curl -fsSL "${url}" -o "${WORK}/${file}"
  curl -fsSL "${sums_url}" -o "${WORK}/sums.txt"
  (cd "${WORK}" && grep -E "[[:space:]]\*?${file}\$" sums.txt | sha256sum -c -)
}

for tool in "$@"; do
  case "${tool}" in
    tflint)
      f="tflint_linux_amd64.zip"
      fetch_verified "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/${f}" \
        "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/checksums.txt" "${f}"
      unzip -o -q "${WORK}/${f}" -d "${BIN}" ;;
    conftest)
      f="conftest_${CONFTEST_VERSION}_Linux_x86_64.tar.gz"
      fetch_verified "https://github.com/open-policy-agent/conftest/releases/download/v${CONFTEST_VERSION}/${f}" \
        "https://github.com/open-policy-agent/conftest/releases/download/v${CONFTEST_VERSION}/checksums.txt" "${f}"
      tar -xzf "${WORK}/${f}" -C "${BIN}" conftest ;;
    trivy)
      if [[ "${TRIVY_VERSION}" == "0.69.4" ]]; then echo "refusing compromised Trivy 0.69.4" >&2; exit 1; fi
      f="trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz"
      fetch_verified "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/${f}" \
        "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_checksums.txt" "${f}"
      tar -xzf "${WORK}/${f}" -C "${BIN}" trivy ;;
    gitleaks)
      f="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
      fetch_verified "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${f}" \
        "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_checksums.txt" "${f}"
      tar -xzf "${WORK}/${f}" -C "${BIN}" gitleaks ;;
    kubelogin)
      f="kubelogin-linux-amd64.zip"
      fetch_verified "https://github.com/Azure/kubelogin/releases/download/v${KUBELOGIN_VERSION}/${f}" \
        "https://github.com/Azure/kubelogin/releases/download/v${KUBELOGIN_VERSION}/${f}.sha256" "${f}"
      unzip -o -q "${WORK}/${f}" -d "${WORK}/kl" && install -m 0755 "${WORK}/kl/bin/linux_amd64/kubelogin" "${BIN}/kubelogin" ;;
    kind)
      f="kind-linux-amd64"
      fetch_verified "https://github.com/kubernetes-sigs/kind/releases/download/v${KIND_VERSION}/${f}" \
        "https://github.com/kubernetes-sigs/kind/releases/download/v${KIND_VERSION}/${f}.sha256sum" "${f}"
      install -m 0755 "${WORK}/${f}" "${BIN}/kind" ;;
    *) echo "unknown tool: ${tool}" >&2; exit 2 ;;
  esac
  echo "installed ${tool}"
done

{{/*
Public host on the shared Gateway, from .Values.dns.mode:
  auto    (default) read from the Gateway at deploy time: its idp.io/public-host annotation (the Azure
          DNS label 30-cluster-config sets, the same across provisions), else platform-hooks.<gateway-ip>.nip.io
  domain  platform-hooks.<dns.domain>, an own domain (e.g. an Azure DNS zone)
  host    dns.host as given
helm template has no cluster to read, so auto falls back to platform-hooks.localhost there.
*/}}
{{- define "provisioning-orchestrator.host" -}}
{{- $d := .Values.dns -}}
{{- if eq $d.mode "auto" -}}
{{- $gw := lookup "gateway.networking.k8s.io/v1" "Gateway" .Values.hooks.gateway.namespace .Values.hooks.gateway.name | default dict -}}
{{- $addresses := dig "status" "addresses" list $gw -}}
{{- $host := dig "metadata" "annotations" "idp.io/public-host" "" $gw -}}
{{- if and (not $host) $addresses }}{{ $host = printf "platform-hooks.%s.nip.io" (index $addresses 0).value }}{{ end -}}
{{- $host | default "platform-hooks.localhost" -}}
{{- else if eq $d.mode "domain" -}}
{{- printf "platform-hooks.%s" (required "dns.domain" $d.domain) -}}
{{- else if eq $d.mode "host" -}}
{{- required "dns.host" $d.host -}}
{{- else -}}
{{- fail "dns.mode must be auto, domain or host" -}}
{{- end -}}
{{- end -}}

{{- define "provisioning-orchestrator.url" -}}
{{ ternary "https" "http" (default false .Values.dns.tls) }}://{{ include "provisioning-orchestrator.host" . }}
{{- end -}}

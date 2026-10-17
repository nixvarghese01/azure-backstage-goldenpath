{{/*
Public host on the shared Gateway, from .Values.dns.mode:
  auto    (default) read from the Gateway at deploy time: its idp.io/public-host annotation (the Azure
          DNS label 30-cluster-config sets, the same across provisions), else platform-hooks.<gateway-ip>.nip.io
  domain  platform-hooks.<dns.domain>, an own domain (e.g. an Azure DNS zone)
  host    dns.host as given (Backstage's public host: dns.backstageHost, default the same)
helm template has no cluster to read, so auto falls back to platform-hooks.localhost there.
*/}}
{{- define "provisioning-orchestrator.hostFor" -}}
{{- $d := .ctx.Values.dns -}}
{{- if eq $d.mode "auto" -}}
{{- $gw := lookup "gateway.networking.k8s.io/v1" "Gateway" .ctx.Values.hooks.gateway.namespace .ctx.Values.hooks.gateway.name | default dict -}}
{{- $addresses := dig "status" "addresses" list $gw -}}
{{- $host := dig "metadata" "annotations" "idp.io/public-host" "" $gw -}}
{{- if and (not $host) $addresses }}{{ $host = printf "%s.%s.nip.io" .prefix (index $addresses 0).value }}{{ end -}}
{{- $host | default (printf "%s.localhost" .prefix) -}}
{{- else if eq $d.mode "domain" -}}
{{- printf "%s.%s" .prefix (required "dns.domain" $d.domain) -}}
{{- else if eq $d.mode "host" -}}
{{- if eq .prefix "backstage" }}{{ $d.backstageHost | default $d.host }}{{ else }}{{ required "dns.host" $d.host }}{{ end -}}
{{- else -}}
{{- fail "dns.mode must be auto, domain or host" -}}
{{- end -}}
{{- end -}}

{{- define "provisioning-orchestrator.host" -}}
{{- include "provisioning-orchestrator.hostFor" (dict "ctx" . "prefix" "platform-hooks") -}}
{{- end -}}

{{/* Backstage's public URL (its chart resolves the same way), for links on the Provisioning tab. */}}
{{- define "provisioning-orchestrator.backstageUrl" -}}
{{ ternary "https" "http" (default false .Values.dns.tls) }}://{{ include "provisioning-orchestrator.hostFor" (dict "ctx" . "prefix" "backstage") }}
{{- end -}}

{{- define "provisioning-orchestrator.url" -}}
{{ ternary "https" "http" (default false .Values.dns.tls) }}://{{ include "provisioning-orchestrator.host" . }}
{{- end -}}

{{/*
Public host on the shared Gateway, from .Values.dns.mode:
  auto    (default) read from the Gateway at deploy time: its idp.io/public-host annotation (the Azure
          DNS label 30-cluster-config sets, the same across provisions), else backstage.<gateway-ip>.nip.io
  domain  backstage.<dns.domain>, an own domain (e.g. an Azure DNS zone)
  host    dns.host as given
helm template has no cluster to read, so auto falls back to backstage.localhost there.
*/}}
{{- define "backstage.host" -}}
{{- $d := .Values.dns -}}
{{- if eq $d.mode "auto" -}}
{{- $gw := lookup "gateway.networking.k8s.io/v1" "Gateway" .Values.gateway.namespace .Values.gateway.name | default dict -}}
{{- $addresses := dig "status" "addresses" list $gw -}}
{{- $host := dig "metadata" "annotations" "idp.io/public-host" "" $gw -}}
{{- if and (not $host) $addresses }}{{ $host = printf "backstage.%s.nip.io" (index $addresses 0).value }}{{ end -}}
{{- $host | default "backstage.localhost" -}}
{{- else if eq $d.mode "domain" -}}
{{- printf "backstage.%s" (required "dns.domain" $d.domain) -}}
{{- else if eq $d.mode "host" -}}
{{- required "dns.host" $d.host -}}
{{- else -}}
{{- fail "dns.mode must be auto, domain or host" -}}
{{- end -}}
{{- end -}}

{{- define "backstage.url" -}}
{{ ternary "https" "http" (default false .Values.dns.tls) }}://{{ include "backstage.host" . }}
{{- end -}}

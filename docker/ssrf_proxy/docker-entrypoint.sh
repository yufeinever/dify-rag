#!/bin/bash

# Modified based on Squid OCI image entrypoint

# This entrypoint aims to forward the squid logs to stdout to assist users of
# common container related tooling (e.g., kubernetes, docker-compose, etc) to
# access the service logs.

# Moreover, it invokes the squid binary, leaving all the desired parameters to
# be provided by the "command" passed to the spawned container. If no command
# is provided by the user, the default behavior (as per the CMD statement in
# the Dockerfile) will be to use Ubuntu's default configuration [1] and run
# squid with the "-NYC" options to mimic the behavior of the Ubuntu provided
# systemd unit.

# [1] The default configuration is changed in the Dockerfile to allow local
# network connections. See the Dockerfile for further information.

echo "[ENTRYPOINT] re-create snakeoil self-signed certificate removed in the build process"
if [ ! -f /etc/ssl/private/ssl-cert-snakeoil.key ]; then
    /usr/sbin/make-ssl-cert generate-default-snakeoil --force-overwrite > /dev/null 2>&1
fi

tail -F /var/log/squid/access.log 2>/dev/null &
tail -F /var/log/squid/error.log 2>/dev/null &
tail -F /var/log/squid/store.log 2>/dev/null &
tail -F /var/log/squid/cache.log 2>/dev/null &

# Replace environment variables in the template and output to the squid.conf
echo "[ENTRYPOINT] replacing environment variables in the template"
awk '{
    while(match($0, /\${[A-Za-z_][A-Za-z_0-9]*}/)) {
        var = substr($0, RSTART+2, RLENGTH-3)
        val = ENVIRON[var]
        $0 = substr($0, 1, RSTART-1) val substr($0, RSTART+RLENGTH)
    }
    print
}' /etc/squid/squid.conf.template > /etc/squid/squid.conf


mkdir -p /etc/squid/conf.d
: > /etc/squid/conf.d/direct_hosts.conf
if [ -n "${SSRF_DIRECT_HOSTS:-}" ]; then
    echo "[ENTRYPOINT] configuring direct hosts ${SSRF_DIRECT_HOSTS}"
    DIRECT_HOSTS="$(echo "${SSRF_DIRECT_HOSTS}" | tr ',' ' ')"
    cat > /etc/squid/conf.d/direct_hosts.conf <<EOF
acl direct_hosts dstdomain ${DIRECT_HOSTS}
always_direct allow direct_hosts
never_direct deny direct_hosts
EOF
fi

: > /etc/squid/conf.d/upstream_proxy.conf
if [ -n "${SSRF_UPSTREAM_PROXY_HOST:-}" ] && [ -n "${SSRF_UPSTREAM_PROXY_PORT:-}" ]; then
    echo "[ENTRYPOINT] configuring upstream proxy ${SSRF_UPSTREAM_PROXY_HOST}:${SSRF_UPSTREAM_PROXY_PORT}"
    cat > /etc/squid/conf.d/upstream_proxy.conf <<EOF
cache_peer ${SSRF_UPSTREAM_PROXY_HOST} parent ${SSRF_UPSTREAM_PROXY_PORT} 0 no-query no-digest no-netdb-exchange default
never_direct allow all
EOF
fi

/usr/sbin/squid -Nz
echo "[ENTRYPOINT] starting squid"
/usr/sbin/squid -f /etc/squid/squid.conf -NYC 1

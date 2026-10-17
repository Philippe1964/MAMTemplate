#!/bin/sh
set -e

mkdir -p /usr/share/nginx/html/internal

collect_metrics() {
     NGINX_VER=$(nginx -v 2>&1 | sed 's/.*nginx\//nginx\//')
    OS_PRETTY="Alpine Linux"
    if [ -f /etc/os-release ]; then
        OS_PRETTY=$(grep '^PRETTY_NAME=' /etc/os-release | cut -d= -f2- | tr -d '"' | tr -d "'")
    fi
    KERNEL_REL=$(uname -r)
    ARCH=$(uname -m)
    CPU_MODEL=$(grep -m1 -i 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | sed 's/^[ \t]*//')
    if [ -z "$CPU_MODEL" ]; then
        CPU_MODEL="$ARCH Container vCPU"
    fi
    LOGICAL_CORES=$(grep -c '^processor' /proc/cpuinfo 2>/dev/null || echo 1)
    [ "$LOGICAL_CORES" -lt 1 ] && LOGICAL_CORES=1

    PREV_TOTAL=0
    PREV_IDLE=0

    while true; do
        HOST_NAME=$(hostname)
        UPTIME_SEC=$(awk '{print $1}' /proc/uptime 2>/dev/null || echo 0)

        # CPU usage from /proc/stat
        CPU_LINE=$(head -n1 /proc/stat 2>/dev/null || echo "")
        if [ -n "$CPU_LINE" ]; then
            set -- $CPU_LINE
            USER=$2; NICE=$3; SYSTEM=$4; IDLE=$5; IOWAIT=${6:-0}; IRQ=${7:-0}; SOFTIRQ=${8:-0}; STEAL=${9:-0}
            IDLE_ALL=$((IDLE + IOWAIT))
            TOTAL=$((USER + NICE + SYSTEM + IDLE_ALL + IRQ + SOFTIRQ + STEAL))
            DIFF_TOTAL=$((TOTAL - PREV_TOTAL))
            DIFF_IDLE=$((IDLE_ALL - PREV_IDLE))
            if [ "$DIFF_TOTAL" -gt 0 ] && [ "$PREV_TOTAL" -gt 0 ]; then
                CPU_PCT=$(awk -v dt="$DIFF_TOTAL" -v di="$DIFF_IDLE" 'BEGIN { printf "%.2f", ((dt - di) * 100.0) / dt }')
            else
                CPU_PCT="1.50"
            fi
            PREV_TOTAL=$TOTAL
            PREV_IDLE=$IDLE_ALL
        else
            CPU_PCT="0.00"
        fi

        # Memory from /proc/meminfo (in kB -> bytes)
        MEM_TOTAL_KB=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
        MEM_AVAIL_KB=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
        MEM_USED_KB=$((MEM_TOTAL_KB - MEM_AVAIL_KB))
        [ "$MEM_USED_KB" -lt 0 ] && MEM_USED_KB=0
        MEM_TOTAL_B=$((MEM_TOTAL_KB * 1024))
        MEM_USED_B=$((MEM_USED_KB * 1024))
        if [ "$MEM_TOTAL_KB" -gt 0 ]; then
            MEM_PCT=$(awk -v u="$MEM_USED_KB" -v t="$MEM_TOTAL_KB" 'BEGIN { printf "%.2f", (u * 100.0) / t }')
        else
            MEM_PCT="0.00"
        fi

        # Disk from df -k /
        DISK_LINE=$(df -k / 2>/dev/null | tail -n1)
        DISK_TOTAL_KB=$(echo "$DISK_LINE" | awk '{print $2}')
        DISK_USED_KB=$(echo "$DISK_LINE" | awk '{print $3}')
        DISK_TOTAL_B=$(( ${DISK_TOTAL_KB:-0} * 1024 ))
        DISK_USED_B=$(( ${DISK_USED_KB:-0} * 1024 ))
        if [ "${DISK_TOTAL_KB:-0}" -gt 0 ]; then
            DISK_PCT=$(awk -v u="$DISK_USED_KB" -v t="$DISK_TOTAL_KB" 'BEGIN { printf "%.2f", (u * 100.0) / t }')
        else
            DISK_PCT="0.00"
        fi

        WORKERS=$(ps aux 2>/dev/null | grep -c '[n]ginx: worker' || echo 1)

        cat <<EOF > /usr/share/nginx/html/internal/presentation-metrics.json.tmp
{
  "hardware": {
    "cpu_model": "$CPU_MODEL",
    "cpu_logical_cores": $LOGICAL_CORES,
    "cpu_physical_cores": $LOGICAL_CORES,
    "cpu_usage_percent": $CPU_PCT,
    "memory_total_bytes": $MEM_TOTAL_B,
    "memory_used_bytes": $MEM_USED_B,
    "memory_usage_percent": $MEM_PCT,
    "disk_total_bytes": $DISK_TOTAL_B,
    "disk_used_bytes": $DISK_USED_B,
    "disk_usage_percent": $DISK_PCT
  },
  "software": {
    "hostname": "$HOST_NAME",
    "os_name": "$OS_PRETTY",
    "os_release": "$KERNEL_REL",
    "architecture": "$ARCH",
    "service_name": "Nginx Reverse Proxy + React 19 SPA",
    "service_version": "$NGINX_VER • React 19.0",
    "uptime_seconds": $UPTIME_SEC,
    "details": {
      "nginx_version": "$NGINX_VER",
      "frontend_framework": "React 19 + TypeScript + Vite",
      "nginx_worker_processes": "$WORKERS",
      "listening_port": "80 (Host 8080)",
      "upstream_target": "mamtemplate-business:8000"
    }
  }
}
EOF
        mv /usr/share/nginx/html/internal/presentation-metrics.json.tmp /usr/share/nginx/html/internal/presentation-metrics.json
        sleep 2
    done
}

collect_metrics &

exec nginx -g "daemon off;"


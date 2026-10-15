FROM nginx:alpine

LABEL org.opencontainers.image.title="Online Food Ordering Portal"
LABEL org.opencontainers.image.description="HTML and CSS food ordering application"

COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O - http://127.0.0.1/ >/dev/null || exit 1
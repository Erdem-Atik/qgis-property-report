# Headless PyQGIS runtime for the property report generator.
# Pinned to an exact LTR patch tag for reproducible builds.
FROM qgis/qgis:3.44.15

# Run Qt without a display server (no X11/Wayland inside the container).
ENV QT_QPA_PLATFORM=offscreen \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    XDG_RUNTIME_DIR=/tmp/runtime-root

RUN mkdir -p -m 0700 /tmp/runtime-root

WORKDIR /app
COPY . /app

CMD ["python3", "test_qgis.py"]

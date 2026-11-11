# Headless PyQGIS runtime for the property report generator.
# Pinned to an exact LTR patch tag for reproducible builds.
FROM qgis/qgis:3.44.15

# Run Qt without a display server (no X11/Wayland inside the container).
ENV QT_QPA_PLATFORM=offscreen \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    XDG_RUNTIME_DIR=/tmp/runtime-root

RUN mkdir -p -m 0700 /tmp/runtime-root

# Extra packages go into a venv that still sees the system site-packages (PyQGIS),
# so Debian-managed packages are never modified.
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv --system-site-packages /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY . /app

CMD ["python3", "test_qgis.py"]

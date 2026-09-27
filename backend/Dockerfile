# Heroes Tracker backend — Flask app + APScheduler in one process.
# Multi-arch base, so this builds natively on x86-64 and on arm64 boards
# (the Jetson TX2 / bastion). No compiler toolchain needed — every dep ships
# aarch64 wheels.
FROM python:3.11-slim

WORKDIR /app

# Install deps first so code changes don't bust the dependency layer cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PORT=3001

# Created so it exists even before the volume mounts.
RUN mkdir -p /app/data

EXPOSE 3001

# Run exactly one instance — the scheduler is in-process, so a second worker
# would double-poll HeroesProfile and double-count rate-limited calls.
CMD ["python3", "app.py"]

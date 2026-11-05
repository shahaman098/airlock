FROM python:3.12-slim

# Minimal hardened analysis image for the Airlock sandbox.
# - non-root user (nobody, uid 65534)
# - only python3 + the analysis stack; no curl/wget/shell comforts beyond slim base
# - matplotlib headless via MPLBACKEND=Agg

ENV MPLBACKEND=Agg \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
    "pandas>=2.2" \
    "numpy>=2.1" \
    "matplotlib>=3.9"

WORKDIR /work
USER 65534:65534

# Default: run a job script mounted at /work/job.py
CMD ["python3", "/work/job.py"]

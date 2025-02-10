ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.0.2
FROM ${BUILD_FROM}

# Install required packages
RUN \
    apk add --no-cache \
        python3 \
        py3-pip \
        gcc \
        musl-dev \
        linux-headers

# Set workdir
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy scripts
COPY rootfs /
COPY *.py ./

# Create data directory
RUN mkdir -p /data

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Your Name <your@email.com>"

# Copy your script
COPY industry.py .

# Run the script
CMD ["python", "industry.py"] 
# Build environment for the Rocky Debian live ISO.
# Used on Windows or macOS through Docker, so you do not need a Debian host.
#
# The source is copied into the image and the whole build happens inside the
# container. Only the finished ISO is copied out to a mounted folder, so the
# large build tree never lands on your Windows disk. Build context is the rocky
# directory (the ISO script passes it), so "COPY . /rocky" gets the full tree.
FROM debian:bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      live-build \
      ca-certificates \
      xorriso \
      debootstrap \
 && rm -rf /var/lib/apt/lists/*

COPY . /rocky
WORKDIR /rocky
CMD ["sh", "/rocky/packaging/iso/build-iso.sh"]

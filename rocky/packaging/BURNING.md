# Making a burnable image and writing it to a USB or SD card

This covers two things: building the image, and writing it to media you can boot.

## What to build

You have two options depending on what you want.

1. A bootable Debian live ISO with Rocky preinstalled. Build it with
   `iso/build-iso.sh` on a Debian host. Output is `live-image-amd64.hybrid.iso`.
   This is the normal "burnable file".

2. Just the Debian package, to add Rocky to a machine that already runs Debian.
   Build it with `deb/build-deb.sh`. Output is `rocky_1.0.0_all.deb`. Install it
   with `sudo apt install ./rocky_1.0.0_all.deb`. No ISO needed.

Most people want option 2, because Rocky is an add-on to an existing Debian
system. Build the ISO only if you want a fresh bootable install or a live demo
stick.

## Build the ISO on a Debian or Ubuntu host

```sh
sudo apt install live-build
cd rocky/packaging/iso
sudo ./build-iso.sh
```

The script builds the .deb, drops it into the image, adds python3 and sqlite3,
and runs live-build. The build downloads packages, so it needs network and a few
GB of disk. When it finishes you have an `.iso` file in the `iso/` directory.

## Build the ISO on Windows

You cannot build a Debian ISO with native Windows tools. The build needs Linux
programs (live-build, debootstrap, chroot, loop mounts), so you run it inside
Linux. Pick one of these.

### Docker Desktop (simplest on Windows)

Install Docker Desktop and start it, then:

```powershell
cd rocky\packaging\iso
.\build-iso.ps1                 # ISO lands in your Downloads folder
.\build-iso.ps1 -Clean         # also delete the build image and cache afterward
.\build-iso.ps1 -OutDir D:\isos
```

The whole build runs inside a throwaway container, so the large build tree never
touches your Windows disk. Only the finished ISO is copied out, by default to your
Downloads folder, named `rocky-bookworm-amd64.iso`.

Cleanup: the container is removed when it finishes (`--rm`), so nothing is left
running. The build image is kept so later runs are faster; add `-Clean` to delete
that image and the build cache too. Only Rocky's own container and image are
affected. Your other containers, images, and volumes are not touched. The
container needs `--privileged` because live-build uses loop mounts; the script
sets this for you.

### WSL2 (Windows Subsystem for Linux)

Install a Debian or Ubuntu distribution from the Microsoft Store, open it, then
run the Debian steps above:

```sh
sudo apt update && sudo apt install live-build
cd /mnt/c/Users/<you>/Documents/GitHub/DroidOs/rocky/packaging/iso
sudo ./build-iso.sh
```

The repo is reachable under `/mnt/c/...`. Build output stays on the Windows disk.

### A Debian or Ubuntu virtual machine

Install Debian or Ubuntu in VirtualBox, VMware, or Hyper-V, copy the `rocky`
folder in, and run the Debian steps above.

## Verify the file before writing it

Record a checksum so you can confirm the write later.

```sh
sha256sum live-image-amd64.hybrid.iso
```

## Write it to a USB stick

Writing an image erases the target device. Identify the device carefully.

### Raspberry Pi Imager (Windows, macOS, Linux; also good for SD cards)

Install Raspberry Pi Imager. Choose "Use custom", pick the `.iso`, pick the USB
device, then write. This is the safest option because it names the target device
clearly.

### balenaEtcher (Windows, macOS, Linux)

Open Etcher, select the `.iso`, select the USB device, click Flash. Etcher hides
system disks, which lowers the risk of writing to the wrong one.

### Rufus (Windows)

Open Rufus, select the device under "Device", select the `.iso` under "Boot
selection", keep the default DD image mode if asked, then Start.

### dd (Linux or macOS)

List disks first and find the device node for your USB stick. On Linux it looks
like `/dev/sdX`; on macOS it looks like `/dev/rdiskN`. Get it wrong and you can
overwrite your own disk, so check the size and label.

```sh
lsblk                          # Linux: find the USB device, for example /dev/sdb
sudo dd if=live-image-amd64.hybrid.iso of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

Replace `/dev/sdX` with the real device node. Do not add a partition number.

## Boot it

Insert the USB stick, enter the boot menu (often F12, F10, or Esc during power on),
and pick the USB device. In the live session, open a terminal and run:

```sh
rockyctl init
rockyctl capabilities
rockyctl ask "check disk space"
```

## Writing a device image instead of an ISO

If you build a raw device image elsewhere (for example a Raspberry Pi `.img` or a
`.wic`), the write step is the same. Use Raspberry Pi Imager or Etcher, or use
`dd` with `if=your-image.img`. Decompress first if the file ends in `.xz` or
`.gz`:

```sh
xz -d your-image.img.xz
sudo dd if=your-image.img of=/dev/sdX bs=4M status=progress conv=fsync
```

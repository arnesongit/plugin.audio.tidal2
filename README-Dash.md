## How to play MPEG-Dash with FLAC content on Linux platforms

If you want to play Hi-Res audio with TIDAL2 on a Linux platform, you have to compile the inputstream.ffmpegdirect addon by yourself.

By default the inputstream.ffmpegdirect doesn't play MPEG-Dash streams on Linux platforms. The TIDAL2 addon uses
an internal MPEG-Dash-to-HLS converter to play FLAC content in Dash streams.
This is only a workaround to fix the problem with the missing Dash demultiplexer.
Otherwise those streams will not play at all.

If you compiled the inputstream.ffmpegdirect addon for Linux, it will be able to demultiplex MPEG-Dash streams.<br>
To use it, you have to enable the setting "inputstream.ffmpegdirect plays MPD" in the addon settings of TIDAL2.

Here is is short description how I compiled the addon for my LibreELEC systems which I use for PC and Raspberry Pi 4B.

I used the build instructions from this pages to compile it:<p>
https://github.com/xbmc/xbmc/blob/master/docs/README.Linux.md<br>
https://github.com/xbmc/inputstream.ffmpegdirect

### Compile inputstream.ffmpegdirect for 64-Bit PC Linux

- Distribution: [Ubuntu 20.04.3 LTS](https://ubuntu.com/download/desktop)
- Fresh installation on my Proxmox server. You can use any PC or Virtual machine (VMware, VirtualBox, etc).
- Install all updates and reboot:
  ```
  sudo apt update
  sudo apt upgrade
  sudo reboot
  ```
- Install all needed packages to compile the addon:
  ```
  sudo apt install autoconf automake autopoint gettext autotools-dev cmake curl default-jre gawk gcc g++ cpp gdc gperf libasound2-dev libass-dev libavahi-client-dev libavahi-common-dev libbluetooth-dev libbluray-dev libbz2-dev libcdio-dev libcec-dev libp8-platform-dev libcrossguid-dev libcwiid-dev libdbus-1-dev libegl1-mesa-dev libenca-dev libflac-dev libfontconfig-dev libfmt-dev libfreetype6-dev libfribidi-dev libfstrcmp-dev libgcrypt-dev libgif-dev libgl-dev libglew-dev libglu-dev libgnutls28-dev libgpg-error-dev libgtest-dev libiso9660-dev libjpeg-dev liblcms2-dev liblirc-dev libltdl-dev liblzo2-dev libmicrohttpd-dev libmysqlclient-dev libnfs-dev libogg-dev libpcre3-dev libplist-dev libpng-dev libpulse-dev libshairplay-dev libsmbclient-dev libspdlog-dev libsqlite3-dev libssl-dev libtag1-dev libtiff-dev  libtinyxml-dev libtinyxml2-dev libtool libudev-dev libunistring-dev libva-dev libvdpau-dev libvorbis-dev libxkbcommon-dev libxmu-dev libxrandr-dev libxslt-dev libxt-dev waylandpp-dev wayland-protocols lsb-release meson nasm ninja-build python3-dev python3-pil python3-pil python3-minimal rapidjson-dev swig unzip uuid-dev zip zlib1g-dev libcurl4-gnutls-dev git
  ```
- Get all sources (here for Kodi Nexus) into my home directory:<br>
  You can also use Matrix or Omega to build the addon for other Kodi version (the Omega branch for xbmc is the master branch).
  ```
  cd
  git clone --branch Nexus https://github.com/xbmc/xbmc.git
  git clone --branch Nexus https://github.com/xbmc/inputstream.ffmpegdirect.git
  ```
- Create the makefiles:
  ```
  cd inputstream.ffmpegdirect && mkdir build && cd build
  cmake -DADDONS_TO_BUILD=inputstream.ffmpegdirect -DADDON_SRC_PREFIX=../.. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=../../xbmc/build/addons -DPACKAGE_ZIP=1 ../../xbmc/cmake/addons
  ```
- Compile the addon: (it takes 10 minutes on my system)
  ```
  make
  ```
- Go to the compiled addon folder:
  ```
  cd ~/xbmc/build/addons/inputstream.ffmpegdirect
  ```
- Delete the links to the library:
  ```
  find . -type l -exec rm {} \;
  ```
- Strip debug info from the library to reduce its size: (I built the version 20.5.0 for Nexus)
  ```
  strip inputstream.ffmpegdirect.so.20.5.0
  ```
- Create the Zip file of the addon which can be used with the "Install from Zip" method in Kodi:
  ```
  cd ..
  zip -r ~/Desktop/inputstream.ffmpegdirect-linux-20.5.0.zip inputstream.ffmpegdirect/*
  ```
- This Zip file on the Desktop can now be used to install the inputstream-ffmpegdirect addon on a Linux PC 64-Bit in Kodi Nexus.

### Compile inputstream.ffmpegdirect for 32-Bit Linux on a Raspberry Pi 4B

- Distribution: [Raspberry Pi OS with desktop and recommended software 32 Bit](https://www.raspberrypi.com/software/operating-systems/#raspberry-pi-os-32-bit)<br>
  Be sure to download the 32-Bit edition!
- Install it on a microSD card (I used Etcher).
- Add the following line to the config.txt file on the SD card to switch the CPU into the 32-Bit mode. This is important!
  ```
  arm_64bit=0
  ```
- Boot the Raspberry Pi OS on a Raspberry Pi 4B and configure the system.
- Install all updates and reboot:
  ```
  sudo apt update
  sudo apt upgrade
  sudo reboot
  ```
- Install all needed packages to compile the addon:
  ```
  sudo apt install autoconf automake autopoint gettext autotools-dev cmake curl default-jre gawk gcc g++ cpp gdc gperf libasound2-dev libass-dev libavahi-client-dev libavahi-common-dev libbluetooth-dev libbluray-dev libbz2-dev libcdio-dev libcec-dev libp8-platform-dev libcrossguid-dev libcwiid-dev libdbus-1-dev libegl1-mesa-dev libenca-dev libflac-dev libfontconfig-dev libfmt-dev libfreetype6-dev libfribidi-dev libfstrcmp-dev libgcrypt-dev libgif-dev libgl-dev libglew-dev libglu-dev libgnutls28-dev libgpg-error-dev libgtest-dev libiso9660-dev libjpeg-dev liblcms2-dev liblirc-dev libltdl-dev liblzo2-dev libmicrohttpd-dev libmmariadb-dev libnfs-dev libogg-dev libpcre3-dev libplist-dev libpng-dev libpulse-dev libshairplay-dev libsmbclient-dev libspdlog-dev libsqlite3-dev libssl-dev libtag1-dev libtiff-dev  libtinyxml-dev libtinyxml2-dev libtool libudev-dev libunistring-dev libva-dev libvdpau-dev libvorbis-dev libxkbcommon-dev libxmu-dev libxrandr-dev libxslt-dev libxt-dev waylandpp-dev wayland-protocols lsb-release meson nasm ninja-build python3-dev python3-pil python3-pil python3-minimal rapidjson-dev swig unzip uuid-dev zip zlib1g-dev libcurl4-openssl-dev git
  ```
- Proceed with "Get all sources" like above.<br>
  The build process is the same, but takes even longer on a Raspberry Pi ;-)
- This compiled version can be used on LibreELEC 11 on a Raspberry Pi 4B.

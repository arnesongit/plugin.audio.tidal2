# plugin.audio.tidal2

This is a modified version of the TIDAL Addon for Kodi.

See [changelog.txt](https://github.com/arnesongit/plugin.audio.tidal2/blob/master/changelog.txt) for information.

## Manual Installation

1. Download the zip file from the repository folder [for Kodi 19 and 20](https://github.com/arnesongit/repository.tidal2/tree/main/plugin.audio.tidal2)
   or [for Kodi 17 and 18](https://github.com/arnesongit/repository.tidal2/tree/until-leia/plugin.audio.tidal2).
2. Use "Install from Zip" Method to install the addon. You have to allow third party addon installation in the Kodi settings!
3. The Addon is shown as "TIDAL2".
4. Have fun.

## Installation with TIDAL2 Repository

With this method you will get updates automatically.

1. Download the Repository zip file [for Kodi 19 and 20](https://github.com/arnesongit/repository.tidal2/blob/main/repository.tidal2/repository.tidal2-0.2.1.zip?raw=true)
   or [for Kodi 17 and 18](https://github.com/arnesongit/repository.tidal2/blob/until-leia/repository.tidal2/repository.tidal2-0.1.0.zip?raw=true).
2. Use "Install from Zip" Method to install the repository. You have to allow third party addon installation in the Kodi settings!
3. Install the "TIDAL2" addon from this repository.
4. Have fun.

## Update from Kodi 18 to Kodi 19/20

If you use my TIDAL2 repository, please uninstall this repository before upgrading to Kodi 19 or 20.

After the Kodi update to 19 or 20 you can install the new TIDAL2 addon from zip file as described above,
or you can install my [new TIDAL2 Repository for Kodi >= 19](https://github.com/arnesongit/repository.tidal2/blob/main/repository.tidal2/repository.tidal2-0.2.1.zip?raw=true)
and upgrade the TIDAL2 addon from this repository.

## How to log in to play music

The TIDAL2 addon uses the TIDAL web API to browse through your music library and play music and videos.
To use this API the addon has to use specific client credential to identify, which kind of device is using the API.
This credentials (client ID and client secret) has to be used to log in to TIDAL via the OAuth2 login method.
<p>
Because the TIDAL2 addon doesn't contain any IDs and secrets, the user has to provide them to the addon.
The easiest way to find a client ID is to select one from the TIDAL Android app (the original TIDAL APK installation file for Android).

### Prepare the addon for login

1. Download the latest version of the original TIDAL APK file from the internet. To find it, search for "TIDAL apk mirror" in the web.
   If you find more than one variant of the APK, use the normal APK version and not the BUNDLE version!
2. Copy the APK file into a folder or on an USB flash drive where your Kodi platform can access this file.
3. Open the addon settings dialog of TIDAL2 and choose "Select device type from TIDAL APK file".
4. A file selector dialog appears where you search for you downloaded TIDAL APK file.
5. After you've selected the APK file, the addon reads the device types out of the APK file and shows them in a selection dialog.
   It can take a few seconds on slower platforms until the selection dialog appears, please wait.
6. Select the device type you want to use.

### Use the login page of the TIDAL2 addon

1. Open the addon settings again and go to the "Extended" settings folder.
   Remember the value for "IP-Port for internal HTTP Server". The default value is 5555.
2. Close the addon settings.
3. Open the login page on a web browser of your choice (on the same PC or a different device).
   Use the IP and the port number of the Kodi device for the URL:  http://ip-address:port-no<br>
   If Kodi runs on your local PC, you can use http://localhost:5555
4. If you don't known the IP address of your Kodi device, go to the "system info" page of Kodi.
   There you will find the network IP address.

The short method:
1. Open the music addon TIDAL2 on Kodi.
2. Select the "Login" item on the home page of the TIDAL2 addon to display the login URL.
3. Open this URL on a web browser of your choice (on the same PC or a different device).

The next actions depend on your selected device type, because they can use different OAuth2 authentication methods.

1. The "Device Code Link" method.<p>
   This is the easiest login method. You will get a link like https://link.tidal.com/ACODE which you have to open in a browser.
   This link will redirect you to a TIDAL web page where you can log in with your username and password.
   The TIDAL2 addon will detect the successful login and resumes the login session automatically.
   But you have to know that the code link URL is only valid for 30 seconds. You will get a timeout message if you're not fast enough with your login!
   <p>
2. The "PKCE" method: (PKCE = Proof Key for Code Exchange)<p>
   This method uses a link to open the login page on the TIDAL web site where you have to provide your username and password.
   Then the TIDAL web site sends a redirect URL back to the browser which contains a one-time-authorization code to complete the login session.
   Your browser can't redirect to this point and shows an "Oops" page.
   To complete the login you have to copy the URL from this "Oops" page and paste it to the input field of the TIDAL2 login page.
   Then press the login button on the the TIDAL2 web page to complete the login session.

After successful login the TIDAL2 addon will refresh its home page and begins to load all your favorites and playlist entries into a cache.
This will be shown in a progress window. Please wait until the cache is completely build.

### Choosing the right device type (client ID)

There are many device types available, but only a few are truly useful.<br>
This are the device types I prefer:

| Device Type            | Login Method     | AAC/FLAC<br>Streams | MQA<br>Streams | Atmos<br>played as | Sony 360<br>played as | Plays HiRes<br>up to 192kHz |
| ---------------------- | ---------------- | ------------------- | -------------- | ------------------ | --------------------- | --------------------------- |
| Automotive             | Device Code Link | https               | https          | MQA                | MQA/FLAC              | No                          |
| Automotive Dolby Atmos | Device Code Link | https               | https          | Dolby-AC3          | MQA/FLAC              | No                          |
| Default                | PKCE             | MPEG-Dash           | https          | MQA                | --                    | No                          |
| Hi Res                 | PKCE             | MPEG-Dash           | https          | FLAC               | --                    | Yes                         |

## How to play Hi-Res audio up to 192kHz sample rate

If you want to play Hi-Res audio, which TIDAL supports since the APK version 2.87, you have to select the "Hi Res" device type from the TIDAL APK.
Of course, your playback hardware must be able to play these audio formats. Otherwise it doesn't make any sense.

I've tested this USB-DACs which work well for Hi-Res playback:

- Meridian Explorer 2
- Lotoo PAW S2
- FiiO BTR7


## How to play MPEG-Dash with FLAC content on Linux platforms

I found out that the imputstream.ffmpegdirect addon for Linux platforms isn't able to play MPEG-Dash streams.<br>
The Dash demultiplexer seems not to be compiled into this addon.<br>
This seems to affect all Linux platforms like Ubuntu for PC, Raspi OS for Raspberry Pi 4 or LibreELEC for PC or Raspberry.
<p>
Windows, MacOS and Android platforms are not affected and MPEG-Dash streams will work on this platforms with FLAC content.
<p>
If you want to play Hi-Res audio with TIDAL2 on a Linux platform, you have to compile the inputstream.ffmpegdirect addon by yourself.<br>
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
  You can also use Matrix or Omega to build the addon for other Kodi version.
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
  zip ~/Desktop/inputstream.ffmpegdirect-linux-20.5.0.zip inputstream.ffmpegdirect/*
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






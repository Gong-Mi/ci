#!/usr/bin/env python3

# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Script to install everything needed to build chromium
# including items requiring sudo privileges.
# See https://chromium.googlesource.com/chromium/src/+/main/docs/linux/build_instructions.md

import argparse
import functools
import os
import re
import shutil
import subprocess
import sys


@functools.lru_cache(maxsize=1)
def build_apt_package_list():
  print("Building apt package list.", file=sys.stderr)
  output = subprocess.check_output(["apt-cache", "dumpavail"]).decode()
  arch_map = {"i386": ":i386"}
  package_regex = re.compile(r"^Package: (.+?)$.+?^Architecture: (.+?)$",
                             re.M | re.S)
  return set(package + arch_map.get(arch, "")
             for package, arch in re.findall(package_regex, output))


def package_exists(package_name: str) -> bool:
  return package_name in build_apt_package_list()


def parse_args(argv):
  parser = argparse.ArgumentParser(
      description="Install Chromium build dependencies.")
  parser.add_argument("--syms",
                      action="store_true",
                      help="Enable installation of debugging symbols")
  parser.add_argument(
      "--no-syms",
      action="store_false",
      dest="syms",
      help="Disable installation of debugging symbols",
  )
  parser.add_argument(
      "--lib32",
      action="store_true",
      help="Enable installation of 32-bit libraries, e.g. for V8 snapshot",
  )
  parser.add_argument(
      "--android",
      action="store_true",
      # Deprecated flag retained as functional for backward compatibility:
      # Enable installation of android dependencies
      help=argparse.SUPPRESS)
  parser.add_argument(
      "--no-android",
      action="store_false",
      dest="android",
      # Deprecated flag retained as functional for backward compatibility:
      # Enable installation of android dependencies
      help=argparse.SUPPRESS)
  parser.add_argument("--arm",
                      action="store_true",
                      help="Enable installation of arm cross toolchain")
  parser.add_argument(
      "--no-arm",
      action="store_false",
      dest="arm",
      help="Disable installation of arm cross toolchain",
  )
  parser.add_argument(
      "--chromeos-fonts",
      action="store_true",
      help="Enable installation of Chrome OS fonts",
  )
  parser.add_argument(
      "--no-chromeos-fonts",
      action="store_false",
      dest="chromeos_fonts",
      help="Disable installation of Chrome OS fonts",
  )
  parser.add_argument(
      "--nacl",
      action="store_true",
      help="Enable installation of prerequisites for building NaCl",
  )
  parser.add_argument(
      "--no-nacl",
      action="store_false",
      dest="nacl",
      help="Disable installation of prerequisites for building NaCl",
  )
  parser.add_argument(
      "--backwards-compatible",
      action="store_true",
      help=
      "Enable installation of packages that are no longer currently needed and"
      + "have been removed from this script. Useful for bisection.",
  )
  parser.add_argument(
      "--no-backwards-compatible",
      action="store_false",
      dest="backwards_compatible",
      help=
      "Disable installation of packages that are no longer currently needed and"
      + "have been removed from this script.",
  )
  parser.add_argument("--no-prompt",
                      action="store_true",
                      help="Automatic yes to prompts")
  parser.add_argument(
      "--quick-check",
      action="store_true",
      help="Quickly try to determine if dependencies are installed",
  )
  parser.add_argument(
      "--unsupported",
      action="store_true",
      help="Attempt installation even on unsupported systems",
  )

  options = parser.parse_args(argv)

  if options.arm or options.android:
    options.lib32 = True

  return options


def check_lsb_release():
  if not shutil.which("lsb_release"):
    print("ERROR: lsb_release not found in $PATH", file=sys.stderr)
    print("try: sudo apt-get install lsb-release", file=sys.stderr)
    sys.exit(1)


@functools.lru_cache(maxsize=1)
def distro_codename():
  return subprocess.check_output(["lsb_release", "--codename",
                                  "--short"]).decode().strip()


@functools.lru_cache(maxsize=1)
def requires_pinned_linux_libc():
  # See: https://crbug.com/403291652 and b/408002335
  name = subprocess.check_output(["uname", "-r"]).decode().strip()
  return name == '6.12.12-1rodete2-amd64'


def add_version_workaround(packages):
  if 'linux-libc-dev:i386' in packages:
    idx = packages.index('linux-libc-dev:i386')
    packages[idx] += '=5.8.14-1'
    packages += ['linux-libc-dev=5.8.14-1']


def check_distro(options):
  if options.unsupported or options.quick_check:
    return

  distro_id = subprocess.check_output(["lsb_release", "--id",
                                       "--short"]).decode().strip()

  supported_codenames = ["focal", "jammy", "noble"]
  supported_ids = ["Debian"]

  if (distro_codename() not in supported_codenames
      and distro_id not in supported_ids):
    print(
        "WARNING: The following distributions are supported,",
        "but distributions not in the list below can also try to install",
        "dependencies by passing the `--unsupported` parameter.",
        "EoS refers to end of standard support and does not include",
        "extended security support.",
        "\tUbuntu 20.04 LTS (focal with EoS April 2025)",
        "\tUbuntu 22.04 LTS (jammy with EoS June 2027)",
        "\tUbuntu 24.04 LTS (noble with EoS June 2029)",
        "\tDebian 11 (bullseye) or later",
        sep="\n",
        file=sys.stderr,
    )
    sys.exit(1)


def check_architecture():
  architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
  if architecture not in ["i686", "x86_64", 'aarch64']:
    print("Only x86 and ARM64 architectures are currently supported",
          file=sys.stderr)
    sys.exit(1)


def check_root():
  if os.geteuid() != 0:
    print("Running as non-root user.", file=sys.stderr)
    print("You might have to enter your password one or more times for 'sudo'.",
          file=sys.stderr)
    print(file=sys.stderr)


def apt_update(options):
  if options.lib32 or options.nacl:
    subprocess.check_call(["sudo", "dpkg", "--add-architecture", "i386"])
  subprocess.check_call(["sudo", "apt-get", "update"])


# Packages needed for development
def dev_list():
  packages = [
      "binutils",
      "bison",
      "bzip2",
      "cdbs",
      "curl",
      "dbus-x11",
      "devscripts",
      "dpkg-dev",
      "elfutils",
      "fakeroot",
      "flex",
      "git-core",
      "gperf",
      "libasound2-dev",
      "libatspi2.0-dev",
      "libbrlapi-dev",
      "libbz2-dev",
      "libc6-dev",
      "libcairo2-dev",
      "libcap-dev",
      "libcups2-dev",
      "libcurl4-gnutls-dev",
      "libdrm-dev",
      "libelf-dev",
      "libevdev-dev",
      "libffi-dev",
      "libfuse2",
      "libgbm-dev",
      "libglib2.0-dev",
      "libglu1-mesa-dev",
      "libgtk-3-dev",
      "libkrb5-dev",
      "libnspr4-dev",
      "libnss3-dev",
      "libpam0g-dev",
      "libpci-dev",
      "libpulse-dev",
      "libsctp-dev",
      "libspeechd-dev",
      "libsqlite3-dev",
      "libssl-dev",
      "libsystemd-dev",
      "libudev-dev",
      "libudev1",
      "libva-dev",
      "libwww-perl",
      "libxshmfence-dev",
      "libxslt1-dev",
      "libxss-dev",
      "libxt-dev",
      "libxtst-dev",
      "lighttpd",
      "locales",
      "openbox",
      "p7zip",
      "patch",
      "perl",
      "pkgconf",
      "rpm",
      "ruby",
      "uuid-dev",
      "wdiff",
      "x11-utils",
      "xcompmgr",
      "xz-utils",
      "zip",
  ]

  # Packages needed for chromeos only
  packages += [
      "libbluetooth-dev",
      "libxkbcommon-dev",
      "mesa-common-dev",
      "zstd",
  ]

  if package_exists("realpath"):
    packages.append("realpath")

  if package_exists("libjpeg-dev"):
    packages.append("libjpeg-dev")
  else:
    packages.append("libjpeg62-dev")

  if package_exists("libbrlapi0.8"):
    packages.append("libbrlapi0.8")
  elif package_exists("libbrlapi0.7"):
    packages.append("libbrlapi0.7")
  elif package_exists("libbrlapi0.6"):
    packages.append("libbrlapi0.6")
  else:
    packages.append("libbrlapi0.5")

  if package_exists("libav-tools"):
    packages.append("libav-tools")

  if package_exists("libvulkan-dev"):
    packages.append("libvulkan-dev")

  if package_exists("libinput-dev"):
    packages.append("libinput-dev")

  # So accessibility APIs work, needed for AX fuzzer
  if package_exists("at-spi2-core"):
    packages.append("at-spi2-core")

  # Cross-toolchain strip is needed for building the sysroots.
  if package_exists("binutils-arm-linux-gnueabihf"):
    packages.append("binutils-arm-linux-gnueabihf")
  if package_exists("binutils-aarch64-linux-gnu"):
    packages.append("binutils-aarch64-linux-gnu")
  if package_exists("binutils-mipsel-linux-gnu"):
    packages.append("binutils-mipsel-linux-gnu")
  if package_exists("binutils-mips64el-linux-gnuabi64"):
    packages.append("binutils-mips64el-linux-gnuabi64")

  # 64-bit systems need a minimum set of 32-bit compat packages for the
  # pre-built NaCl binaries.
  if "ELF 64-bit" in subprocess.check_output(["file", "-L",
                                              "/sbin/init"]).decode():
    # ARM64 may not support these.
    if package_exists("libc6-i386"):
      packages.append("libc6-i386")
    if package_exists("lib32stdc++6"):
      packages.append("lib32stdc++6")

    # lib32gcc-s1 used to be called lib32gcc1 in older distros.
    if package_exists("lib32gcc-s1"):
      packages.append("lib32gcc-s1")
    elif package_exists("lib32gcc1"):
      packages.append("lib32gcc1")

  return packages


# List of required run-time libraries
def lib_list():
  packages = [
      "libatk1.0-0",
      "libatspi2.0-0",
      "libc6",
      "libcairo2",
      "libcap2",
      "libcgi-session-perl",
      "libcups2",
      "libdrm2",
      "libegl1",
      "libevdev2",
      "libexpat1",
      "libfontconfig1",
      "libfreetype6",
      "libgbm1",
      "libglib2.0-0",
      "libgl1",
      "libgtk-3-0",
      "libpam0g",
      "libpango-1.0-0",
      "libpangocairo-1.0-0",
      "libpci3",
      "libpcre3",
      "libpixman-1-0",
      "libspeechd2",
      "libstdc++6",
      "libsqlite3-0",
      "libuuid1",
      "libwayland-egl1",
      "libwayland-egl1-mesa",
      "libx11-6",
      "libx11-xcb1",
      "libxau6",
      "libxcb1",
      "libxcomposite1",
      "libxcursor1",
      "libxdamage1",
      "libxdmcp6",
      "libxext6",
      "libxfixes3",
      "libxi6",
      "libxinerama1",
      "libxrandr2",
      "libxrender1",
      "libxtst6",
      "x11-utils",
      "x11-xserver-utils",
      "xserver-xorg-core",
      "xserver-xorg-video-dummy",
      "xvfb",
      "zlib1g",
  ]

  # Run-time libraries required by chromeos only
  packages += [
      "libpulse0",
      "libbz2-1.0",
  ]

  # May not exist (e.g. ARM64)
  if package_exists("lib32z1"):
    packages.append("lib32z1")

  if package_exists("libffi8"):
    packages.append("libffi8")
  elif package_exists("libffi7"):
    packages.append("libffi7")
  elif package_exists("libffi6"):
    packages.append("libffi6")

  if package_exists("libpng16-16t64"):
    packages.append("libpng16-16t64")
  elif package_exists("libpng16-16"):
    packages.append("libpng16-16")
  else:
    packages.append("libpng12-0")

  if package_exists("libnspr4"):
    packages.extend(["libnspr4", "libnss3"])
  else:
    packages.extend(["libnspr4-0d", "libnss3-1d"])

  if package_exists("appmenu-gtk"):
    packages.append("appmenu-gtk")
  if package_exists("libgnome-keyring0"):
    packages.append("libgnome-keyring0")
  if package_exists("libgnome-keyring-dev"):
    packages.append("libgnome-keyring-dev")
  if package_exists("libvulkan1"):
    packages.append("libvulkan1")
  if package_exists("libinput10"):
    packages.append("libinput10")

  if package_exists("libncurses6"):
    packages.append("libncurses6")
  else:
    packages.append("libncurses5")

  if package_exists("libasound2t64"):
    packages.append("libasound2t64")
  else:
    packages.append("libasound2")

  # Run-time packages required by interactive_ui_tests on mutter
  if package_exists("libgraphene-1.0-0"):
    packages.append("libgraphene-1.0-0")
  if package_exists("mutter-common"):
    packages.append("mutter-common")

  return packages


def lib32_list(options):
  if not options.lib32:
    print("Skipping 32-bit libraries.", file=sys.stderr)
    return []
  print("Including 32-bit libraries.", file=sys.stderr)

  packages = [
      # 32-bit libraries needed for a 32-bit build
      # includes some 32-bit libraries required by the Android SDK
      # See https://developer.android.com/sdk/installing/index.html?pkg=tools
      "libasound2:i386",
      "libatk-bridge2.0-0:i386",
      "libatk1.0-0:i386",
      "libatspi2.0-0:i386",
      "libdbus-1-3:i386",
      "libegl1:i386",
      "libgl1:i386",
      "libglib2.0-0:i386",
      "libnss3:i386",
      "libpango-1.0-0:i386",
      "libpangocairo-1.0-0:i386",
      "libstdc++6:i386",
      "libwayland-egl1:i386",
      "libx11-xcb1:i386",
      "libxcomposite1:i386",
      "libxdamage1:i386",
      "libxkbcommon0:i386",
      "libxrandr2:i386",
      "libxtst6:i386",
      "zlib1g:i386",
      # 32-bit libraries needed e.g. to compile V8 snapshot for Android or armhf
      "linux-libc-dev:i386",
      "libexpat1:i386",
      "libpci3:i386",
  ]

  # When cross building for arm/Android on 64-bit systems the host binaries
  # that are part of v8 need to be compiled with -m32 which means
  # that basic multilib support is needed.
  if "ELF 64-bit" in subprocess.check_output(["file", "-L",
                                              "/sbin/init"]).decode():
    # gcc-multilib conflicts with the arm cross compiler but
    # g++-X.Y-multilib gives us the 32-bit support that we need. Find out the
    # appropriate value of X and Y by seeing what version the current
    # distribution's g++-multilib package depends on.
    lines = subprocess.check_output(
        ["apt-cache", "depends", "g++-multilib", "--important"]).decode()
    pattern = re.compile(r"g\+\+-[0-9.]+-multilib")
    packages += re.findall(pattern, lines)

  if package_exists("libncurses6:i386"):
    packages.append("libncurses6:i386")
  else:
    packages.append("libncurses5:i386")

  return packages


# Packages that have been removed from this script. Regardless of configuration
# or options passed to this script, whenever a package is removed, it should be
# added here.
def backwards_compatible_list(options):
  if not options.backwards_compatible:
    print("Skipping backwards compatible packages.", file=sys.stderr)
    return []
  print("Including backwards compatible packages.", file=sys.stderr)

  packages = [
      "7za",
      "fonts-indic",
      "fonts-ipafont",
      "fonts-stix",
      "fonts-thai-tlwg",
      "fonts-tlwg-garuda",
      "g++",
      "g++-4.8-multilib-arm-linux-gnueabihf",
      "gcc-4.8-multilib-arm-linux-gnueabihf",
      "g++-9-multilib-arm-linux-gnueabihf",
      "gcc-9-multilib-arm-linux-gnueabihf",
      "gcc-arm-linux-gnueabihf",
      "g++-10-multilib-arm-linux-gnueabihf",
      "gcc-10-multilib-arm-linux-gnueabihf",
      "g++-10-arm-linux-gnueabihf",
      "gcc-10-arm-linux-gnueabihf",
      "git-svn",
      "language-pack-da",
      "language-pack-fr",
      "language-pack-he",
      "language-pack-zh-hant",
      "libappindicator-dev",
      "libappindicator1",
      "libappindicator3-1",
      "libappindicator3-dev",
      "libdconf-dev",
      "libdconf1",
      "libdconf1:i386",
      "libexif-dev",
      "libexif12",
      "libexif12:i386",
      "libgbm-dev",
      "libgbm-dev-lts-trusty",
      "libgbm-dev-lts-xenial",
      "libgconf-2-4:i386",
      "libgconf2-dev",
      "libgl1-mesa-dev",
      "libgl1-mesa-dev-lts-trusty",
      "libgl1-mesa-dev-lts-xenial",
      "libgl1-mesa-glx:i386",
      "libgl1-mesa-glx-lts-trusty:i386",
      "libgl1-mesa-glx-lts-xenial:i386",
      "libgles2-mesa-dev",
      "libgles2-mesa-dev-lts-trusty",
      "libgles2-mesa-dev-lts-xenial",
      "libgtk-3-0:i386",
      "libgtk2.0-0",
      "libgtk2.0-0:i386",
      "libgtk2.0-dev",
      "mesa-common-dev",
      "mesa-common-dev-lts-trusty",
      "mesa-common-dev-lts-xenial",
      "msttcorefonts",
      "python-dev",
      "python-setuptools",
      "snapcraft",
      "ttf-dejavu-core",
      "ttf-indic-fonts",
      "ttf-kochi-gothic",
      "ttf-kochi-mincho",
      "ttf-mscorefonts-installer",
      "xfonts-mathml",
  ]

  if package_exists("python-is-python2"):
    packages.extend(["python-is-python2", "python2-dev"])
  else:
    packages.append("python")

  if package_exists("python-crypto"):
    packages.append("python-crypto")

  if package_exists("python-numpy"):
    packages.append("python-numpy")

  if package_exists("python-openssl"):
    packages.append("python-openssl")

  if package_exists("python-psutil"):
    packages.append("python-psutil")

  if package_exists("python-yaml"):
    packages.append("python-yaml")

  if package_exists("apache2.2-bin"):
    packages.append("apache2.2-bin")
  else:
    packages.append("apache2-bin")

  php_versions = [
      ("php8.1-cgi", "libapache2-mod-php8.1"),
      ("php8.0-cgi", "libapache2-mod-php8.0"),
      ("php7.4-cgi", "libapache2-mod-php7.4"),
      ("php7.3-cgi", "libapache2-mod-php7.3"),
      ("php7.2-cgi", "libapache2-mod-php7.2"),
      ("php7.1-cgi", "libapache2-mod-php7.1"),
      ("php7.0-cgi", "libapache2-mod-php7.0"),
      ("php5-cgi", "libapache2-mod-php5"),
  ]

  for php_cgi, mod_php in php_versions:
    if package_exists(php_cgi):
      packages.extend([php_cgi, mod_php])
      break

  return [package for package in packages if package_exists(package)]


def arm_list(options):
  if not options.arm:
    print("Skipping ARM cross toolchain.", file=sys.stderr)
    return []
  print("Including ARM cross toolchain.", file=sys.stderr)

  # arm cross toolchain packages needed to build chrome on armhf
  packages = [
      "g++-arm-linux-gnueabihf",
      "gcc-arm-linux-gnueabihf",
      "libc6-dev-armhf-cross",
      "linux-libc-dev-armhf-cross",
  ]

  # Work around an Ubuntu dependency issue.
  # TODO(https://crbug.com/40549424): Remove this when support for Focal
  # and Jammy are dropped.
  if distro_codename() == "focal":
    packages.extend([
        "g++-10-multilib-arm-linux-gnueabihf",
        "gcc-10-multilib-arm-linux-gnueabihf",
    ])
  elif distro_codename() == "jammy":
    packages.extend([
        "g++-11-arm-linux-gnueabihf",
        "gcc-11-arm-linux-gnueabihf",
    ])

  return packages


def nacl_list(options):
  if not options.nacl:
    print("Skipping NaCl, NaCl toolchain, NaCl ports dependencies.",
          file=sys.stderr)
    return []

  packages = [
      "g++-mingw-w64-i686",
      "lib32z1-dev",
      "libasound2:i386",
      "libcap2:i386",
      "libelf-dev:i386",
      "libfontconfig1:i386",
      "libglib2.0-0:i386",
      "libgpm2:i386",
      "libncurses5:i386",
      "libnss3:i386",
      "libpango-1.0-0:i386",
      "libssl-dev:i386",
      "libtinfo-dev",
      "libtinfo-dev:i386",
      "libtool",
      "libudev1:i386",
      "libuuid1:i386",
      "libxcomposite1:i386",
      "libxcursor1:i386",
      "libxdamage1:i386",
      "libxi6:i386",
      "libxrandr2:i386",
      "libxss1:i386",
      "libxtst6:i386",
      "texinfo",
      "xvfb",
      # Packages to build NaCl, its toolchains, and its ports.
      "ant",
      "autoconf",
      "bison",
      "cmake",
      "gawk",
      "intltool",
      "libtinfo5",
      "xutils-dev",
      "xsltproc",
  ]

  for package in packages:
    if not
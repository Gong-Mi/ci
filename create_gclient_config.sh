#!/bin/bash

#  .gclient 文件内容
GCLIENT_CONFIG=$(cat <<EOF
solutions = [
  { "name": "angle", "url": "https://chromium.googlesource.com/angle/angle.git", "deps_file": "DEPS", "managed": False, "custom_deps": {}, "safesync_url": "" },
]
EOF
)

#  DEPS 文件内容
DEPS_CONFIG=$(cat <<EOF
vars = {
  "target_os": "android",
}

deps = {
  "src/angle": {
    "url": "https://chromium.googlesource.com/angle/angle.git",
    "managed": False,
  },
}
EOF
)

# 创建 .gclient 文件
echo "$GCLIENT_CONFIG" > .gclient

# 创建 DEPS 文件
echo "$DEPS_CONFIG" > DEPS

echo ".gclient and DEPS files created."
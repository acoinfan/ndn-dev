#!/bin/bash

# 处理带逗号的字节数参数
raw_bytes="$1"
target_bytes=$(echo "$raw_bytes" | tr -d ',')

# 目标文件名
output="testfile_${target_bytes}.txt"

# 每行内容
line="Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur."

# 估算每行字节数
line_bytes=$(echo -n "Line 1: $line" | wc -c)
# 需要的行数
lines=$((target_bytes / line_bytes))

# 生成文件
for i in $(seq 1 $lines); do
  echo "Line $i: $line"
done > "$output"
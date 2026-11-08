#!/bin/bash
# ChemAI Git 回滚脚本
# 用法: ./git_rollback.sh [version]
# 示例:
#   ./git_rollback.sh          # 查看所有版本
#   ./git_rollback.sh v1.0.0    # 回滚到v1.0.0
#   ./git_rollback.sh --latest # 回滚到最新版本

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "ChemAI Git 回滚工具"
echo "=========================================="

# 显示所有版本
show_versions() {
    echo -e "${GREEN}可用版本:${NC}"
    git log --oneline --decorate --all
    echo ""
    echo -e "${GREEN}标签:${NC}"
    git tag -l
}

# 回滚到指定版本
rollback_to() {
    local version=$1

    echo -e "${YELLOW}即将回滚到: $version${NC}"
    echo -e "${YELLOW}警告: 这将丢失当前未提交的所有更改!${NC}"
    read -p "确认继续? (y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git reset --hard "$version"
        echo -e "${GREEN}已成功回滚到: $version${NC}"
        git log --oneline -3
    else
        echo -e "${RED}取消回滚${NC}"
    fi
}

# 主逻辑
if [ -z "$1" ]; then
    show_versions
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "用法: $0 [version]"
    echo ""
    echo "选项:"
    echo "  (无参数)   显示所有版本"
    echo "  v1.0.0     回滚到指定版本"
    echo "  --latest   回滚到最新提交"
    echo "  --help     显示此帮助"
elif [ "$1" = "--latest" ]; then
    rollback_to HEAD
else
    rollback_to "$1"
fi

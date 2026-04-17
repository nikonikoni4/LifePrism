param (
    [Parameter(Mandatory=$false, Position=0)]
    [string]$Action
)

# 获取当前所在的分支名
$Branch = git branch --show-current

# 检查是否处于分离头指针状态
if ([string]::IsNullOrWhiteSpace($Branch)) {
    Write-Host "当前未处于任何分支上，无法构建 ref 路径。" -ForegroundColor Red
    exit 1
}

$RefName = "refs/ci-check/$Branch"

if ([string]::IsNullOrWhiteSpace($Action)) {
    Write-Host "缺少参数。请指定要执行的操作：update | list | delete" -ForegroundColor Yellow
    exit 1
}

switch ($Action.ToLower()) {
    "update" {
        # 1. 更新或创建当前分支的 ref 指向 HEAD
        git update-ref $RefName HEAD
        Write-Host "已将 $RefName 更新为指向当前 HEAD。" -ForegroundColor Green
    }
    
    "list" {
        # 2. 查看当前所有的 ci-check 引用
        Write-Host "=== 当前的 ci-check 引用 ===" -ForegroundColor Cyan
        $refs = git show-ref 2>$null | Select-String "refs/ci-check/"
        if ($refs) {
            $refs
        } else {
            Write-Host "(暂无相关的引用)" -ForegroundColor Gray
        }
    }
    
    "delete" {
        # 3. 删除当前分支点的 ref
        git show-ref --verify --quiet $RefName 2>$null
        if ($LASTEXITCODE -eq 0) {
            git update-ref -d $RefName
            Write-Host "已成功删除引用：$RefName" -ForegroundColor Green
        } else {
            Write-Host "未找到引用：$RefName，无需删除。" -ForegroundColor Yellow
        }
    }
    
    default {
        # 处理无效参数
        Write-Host "未知参数: $Action" -ForegroundColor Red
        Write-Host "支持的参数仅包含: update, list, delete" -ForegroundColor Yellow
        exit 1
    }
}
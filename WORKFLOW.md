# 工作流程

## 主分支
- `main` — 稳定版本，只接受已验证的合并

## 日常开发流程
每次新需求/新改动，按以下步骤操作：

### 1. 创建新分支
```bash
git checkout main
git pull origin main
git checkout -b feature/功能名称
```

### 2. 在分支上开发
- 修改代码
- 测试验证
- 提交：
```bash
git add -A
git commit -m "feat: 描述本次改动"
git push -u origin feature/功能名称
```

### 3. 合并到 main
验证无误后：
```bash
git checkout main
git merge feature/功能名称
git push origin main
git branch -d feature/功能名称  # 删除本地分支
```

## 分支命名规范
- `feature/xxx` — 新功能
- `fix/xxx` — Bug 修复
- `refactor/xxx` — 重构
